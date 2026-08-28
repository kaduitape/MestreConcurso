"""Fase 10: planos, assinatura, cupons, limites e indicadores.

Duas regras estruturam quase todos estes testes: **limite é dado, não código**, e
**cancelar não corta o que já foi pago**. A terceira, mais silenciosa, é a
distinção entre "sem acesso" e "sem teto" — confundi-las é como um sistema de
cobrança libera recurso pago por engano.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.billing.coupons import (
    Coupon,
    DiscountKind,
    apply,
)
from app.domain.billing.metrics import (
    SubscriptionSnapshot,
    arpu,
    build,
    churn,
    gross_margin,
    mrr,
)
from app.domain.billing.plans import (
    DEFAULT_PLANS,
    FALLBACK_PLAN_SLUG,
    Entitlement,
    EntitlementSet,
    FeatureKey,
    Period,
)
from app.domain.billing.quota import check, window_for
from app.domain.billing.subscription import (
    GRACE_DAYS,
    ChangeKind,
    SubscriptionState,
    SubscriptionStatus,
    decide_change,
    grace_deadline,
    is_entitled,
    next_status,
    period_end_for,
    remaining_credit,
)

TODAY = date(2026, 3, 15)


class TestPlans:
    def test_sem_acesso_e_sem_teto_sao_coisas_diferentes(self):
        sem_acesso = Entitlement(FeatureKey.AI_TUTOR, enabled=False)
        ilimitado = Entitlement(FeatureKey.AI_TUTOR, enabled=True, limit=None)

        assert sem_acesso.is_unlimited is False
        assert ilimitado.is_unlimited is True
        assert "não incluído" in sem_acesso.describe()
        assert "sem limite" in ilimitado.describe()

    def test_todo_direito_se_descreve_em_texto(self):
        for plan in DEFAULT_PLANS:
            for item in plan.entitlements:
                assert item.describe()
                assert item.label != item.feature, "todo recurso tem rótulo legível"

    def test_existe_um_plano_de_queda_para_quem_nao_assinou(self):
        assert any(plan.slug == FALLBACK_PLAN_SLUG for plan in DEFAULT_PLANS)
        gratuito = next(plan for plan in DEFAULT_PLANS if plan.slug == FALLBACK_PLAN_SLUG)
        assert gratuito.is_free

    def test_nenhum_plano_esconde_conteudo_de_estudo(self):
        """Simulados e desafios são limitados no gratuito, nunca bloqueados."""
        gratuito = next(plan for plan in DEFAULT_PLANS if plan.slug == FALLBACK_PLAN_SLUG)
        por_recurso = {item.feature: item for item in gratuito.entitlements}

        assert por_recurso[FeatureKey.SIMULATIONS].enabled is True
        assert por_recurso[FeatureKey.CHALLENGES].enabled is True
        assert por_recurso[FeatureKey.ANALYTICS].enabled is True

    def test_recurso_desconhecido_e_negado_e_nao_liberado(self):
        conjunto = EntitlementSet(plan_slug="x", plan_name="X", items={})
        resultado = conjunto.get("recurso.inexistente")

        assert resultado.enabled is False
        assert resultado.limit == 0


class TestSubscriptionLifecycle:
    def test_o_periodo_respeita_o_fim_do_mes(self):
        """Quem assina em 31 de janeiro não renova em 3 de março."""
        assert period_end_for(date(2026, 1, 31)) == date(2026, 2, 27)
        assert period_end_for(date(2026, 3, 15)) == date(2026, 4, 14)
        assert period_end_for(date(2026, 1, 15), months=12) == date(2027, 1, 14)

    def test_assinatura_ativa_dentro_do_periodo_da_acesso(self):
        state = SubscriptionState(SubscriptionStatus.ACTIVE, date(2026, 3, 31))
        assert is_entitled(state, today=TODAY) is True

    def test_assinatura_cancelada_mantem_acesso_ate_o_fim_do_periodo(self):
        """Quem pagou até o dia 31 tem acesso até o dia 31."""
        state = SubscriptionState(SubscriptionStatus.CANCELING, date(2026, 3, 31))

        assert is_entitled(state, today=TODAY) is True
        assert is_entitled(state, today=date(2026, 4, 1)) is False

    def test_inadimplencia_tem_tolerancia_declarada(self):
        prazo = grace_deadline(TODAY)
        state = SubscriptionState(
            SubscriptionStatus.PAST_DUE, date(2026, 3, 31), grace_ends_on=prazo
        )

        assert (prazo - TODAY).days == GRACE_DAYS
        assert is_entitled(state, today=prazo) is True
        assert is_entitled(state, today=prazo.replace(day=prazo.day + 1)) is False

    def test_cancelada_e_expirada_nao_dao_acesso(self):
        for status in (SubscriptionStatus.CANCELED, SubscriptionStatus.EXPIRED):
            state = SubscriptionState(status, date(2026, 12, 31))
            assert is_entitled(state, today=TODAY) is False

    def test_o_tempo_sozinho_move_o_estado(self):
        teste = SubscriptionState(
            SubscriptionStatus.TRIALING, date(2026, 3, 31), trial_ends_on=date(2026, 3, 10)
        )
        assert next_status(teste, today=TODAY) == SubscriptionStatus.PAST_DUE

        vencida = SubscriptionState(
            SubscriptionStatus.PAST_DUE, date(2026, 3, 31), grace_ends_on=date(2026, 3, 10)
        )
        assert next_status(vencida, today=TODAY) == SubscriptionStatus.EXPIRED

        cancelando = SubscriptionState(SubscriptionStatus.CANCELING, date(2026, 3, 10))
        assert next_status(cancelando, today=TODAY) == SubscriptionStatus.CANCELED

    def test_um_estado_que_ainda_vale_nao_e_alterado(self):
        state = SubscriptionState(SubscriptionStatus.ACTIVE, date(2026, 3, 31))
        assert next_status(state, today=TODAY) == SubscriptionStatus.ACTIVE


class TestPlanChange:
    def test_upgrade_vale_agora_com_credito_proporcional(self):
        decision = decide_change(
            current_price_cents=4990,
            new_price_cents=47900,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            today=date(2026, 3, 16),
        )

        assert decision.kind == ChangeKind.UPGRADE
        assert decision.immediate is True
        assert decision.credit_cents > 0
        assert decision.charge_cents == 47900 - decision.credit_cents

    def test_downgrade_vale_no_fim_do_periodo_e_nao_cobra(self):
        decision = decide_change(
            current_price_cents=47900,
            new_price_cents=4990,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            today=date(2026, 3, 16),
        )

        assert decision.kind == ChangeKind.DOWNGRADE
        assert decision.immediate is False
        assert decision.charge_cents == 0
        assert decision.credit_cents == 0

    def test_trocar_para_o_mesmo_plano_e_reconhecido(self):
        decision = decide_change(
            current_price_cents=4990,
            new_price_cents=4990,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            today=TODAY,
        )
        assert decision.kind == ChangeKind.SAME

    def test_o_credito_e_proporcional_aos_dias_restantes(self):
        metade = remaining_credit(
            price_cents=3000,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            today=date(2026, 3, 16),
        )
        fim = remaining_credit(
            price_cents=3000,
            period_start=date(2026, 3, 1),
            period_end=date(2026, 3, 31),
            today=date(2026, 3, 31),
        )

        assert 1400 <= metade <= 1600
        assert fim == 0

    def test_plano_gratuito_nao_gera_credito(self):
        assert (
            remaining_credit(
                price_cents=0,
                period_start=date(2026, 3, 1),
                period_end=date(2026, 3, 31),
                today=TODAY,
            )
            == 0
        )


class TestQuota:
    def test_janela_mensal_segue_o_aniversario_da_assinatura(self):
        janela = window_for(Period.MONTH, today=date(2026, 3, 25), anchor=date(2026, 1, 20))

        assert janela.starts_on == date(2026, 3, 20)
        assert janela.ends_on == date(2026, 4, 19)

    def test_antes_do_aniversario_a_janela_e_a_anterior(self):
        janela = window_for(Period.MONTH, today=date(2026, 3, 5), anchor=date(2026, 1, 20))
        assert janela.starts_on == date(2026, 2, 20)

    def test_sem_ancora_a_janela_e_o_mes_civil(self):
        janela = window_for(Period.MONTH, today=date(2026, 3, 15))
        assert (janela.starts_on, janela.ends_on) == (date(2026, 3, 1), date(2026, 3, 31))

    def test_janela_diaria_e_o_proprio_dia(self):
        janela = window_for(Period.DAY, today=TODAY)
        assert janela.starts_on == janela.ends_on == TODAY

    def test_janela_total_nunca_vira(self):
        janela = window_for(Period.TOTAL, today=TODAY, anchor=date(2026, 1, 1))
        assert janela.is_open is True
        assert janela.ends_on is None

    def test_recurso_sem_acesso_recusa_com_o_caminho(self):
        resultado = check(
            Entitlement(FeatureKey.AI_TUTOR, enabled=False),
            used=0,
            today=TODAY,
            plan_name="Gratuito",
        )

        assert resultado.allowed is False
        assert "não está incluído" in resultado.reason
        assert "Gratuito" in resultado.reason

    def test_recurso_ilimitado_nao_tem_teto_nem_contador(self):
        resultado = check(Entitlement(FeatureKey.SIMULATIONS), used=9999, today=TODAY)

        assert resultado.allowed is True
        assert resultado.is_unlimited is True
        assert resultado.remaining is None

    def test_dentro_do_limite_informa_o_que_resta(self):
        resultado = check(Entitlement(FeatureKey.AI_TUTOR, limit=10), used=4, today=TODAY)

        assert resultado.allowed is True
        assert resultado.remaining == 6

    def test_limite_atingido_diz_quanto_foi_usado_e_quando_zera(self):
        resultado = check(
            Entitlement(FeatureKey.AI_TUTOR, limit=10),
            used=10,
            today=date(2026, 3, 25),
            anchor=date(2026, 1, 20),
        )

        assert resultado.allowed is False
        assert "10 de 10" in resultado.reason
        assert "20/04/2026" in resultado.reason
        assert "Mudar de plano" in resultado.reason

    def test_limite_total_avisa_que_nao_renova(self):
        resultado = check(
            Entitlement(FeatureKey.SHARE_CARDS, limit=3, period=Period.TOTAL),
            used=3,
            today=TODAY,
        )

        assert resultado.allowed is False
        assert "não se renova" in resultado.reason


class TestCoupons:
    def _coupon(self, **kwargs) -> Coupon:
        base = {"code": "BEMVINDO", "kind": DiscountKind.PERCENT, "value": 30}
        return Coupon(**{**base, **kwargs})

    def test_desconto_percentual(self):
        resultado = apply(self._coupon(), amount_cents=4990, today=TODAY, plan_slug="mestre")

        assert resultado.valid is True
        assert resultado.discount_cents == 1497
        assert resultado.final_cents == 3493

    def test_o_desconto_nunca_passa_do_valor_cobrado(self):
        resultado = apply(
            self._coupon(kind=DiscountKind.FIXED, value=99900),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
        )

        assert resultado.discount_cents == 4990
        assert resultado.final_cents == 0, "cupom não vira crédito"

    def test_cupom_expirado_diz_quando_expirou(self):
        resultado = apply(
            self._coupon(ends_on=date(2026, 1, 31)),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
        )

        assert resultado.valid is False
        assert "31/01/2026" in resultado.reason

    def test_cupom_esgotado_e_recusado(self):
        resultado = apply(
            self._coupon(max_redemptions=10, redeemed=10),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
        )

        assert resultado.valid is False
        assert "número máximo de usos" in resultado.reason

    def test_cupom_de_outro_plano_e_recusado(self):
        resultado = apply(
            self._coupon(plan_slugs=("mestre-anual",)),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
        )

        assert resultado.valid is False
        assert "não vale para o plano" in resultado.reason

    def test_uso_repetido_pelo_mesmo_candidato_e_recusado(self):
        resultado = apply(
            self._coupon(),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
            already_used_by_user=True,
        )

        assert resultado.valid is False
        assert "já usou" in resultado.reason

    def test_valor_minimo_e_respeitado(self):
        resultado = apply(
            self._coupon(min_amount_cents=10000),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
        )

        assert resultado.valid is False
        assert "a partir de R$ 100,00".replace(",", ".") in resultado.reason

    def test_toda_recusa_devolve_o_valor_original_intacto(self):
        resultado = apply(
            self._coupon(is_active=False),
            amount_cents=4990,
            today=TODAY,
            plan_slug="mestre",
        )

        assert resultado.discount_cents == 0
        assert resultado.final_cents == 4990


class TestMetrics:
    def test_plano_anual_entra_pelo_duodecimo(self):
        resultado = mrr([SubscriptionSnapshot("anual", 47900, months=12)])

        # 47900/12 = 3991,67 centavos. A conta trunca: nunca superestima receita.
        assert resultado.value == pytest.approx(39.91, abs=0.01)
        assert "divididos por 12" in resultado.basis

    def test_sem_assinatura_paga_nao_ha_mrr(self):
        resultado = mrr([SubscriptionSnapshot("gratuito", 0)])

        assert resultado.value is None
        assert resultado.empty_reason is not None

    def test_arpu_precisa_de_pagante(self):
        assert arpu([]).value is None
        assert arpu([SubscriptionSnapshot("mestre", 4990)]).value == pytest.approx(49.9)

    def test_churn_exige_periodo_fechado(self):
        aberto = churn(active_at_start=100, canceled_in_period=3, period_closed=False)

        assert aberto.value is None
        assert "período encerrado" in (aberto.empty_reason or "")

    def test_churn_exige_base_no_inicio_do_periodo(self):
        vazio = churn(active_at_start=0, canceled_in_period=0, period_closed=True)
        assert vazio.value is None

    def test_churn_calculado_mostra_o_denominador(self):
        resultado = churn(active_at_start=200, canceled_in_period=6, period_closed=True)

        assert resultado.value == 3.0
        assert "sobre 200" in resultado.basis

    def test_margem_depende_de_receita(self):
        sem_receita = gross_margin(mrr([]), mrr([]))
        assert sem_receita.value is None

    def test_o_painel_traz_todos_os_indicadores_com_base(self):
        painel = build(
            subscriptions=[SubscriptionSnapshot("mestre", 4990)],
            active_at_start=10,
            canceled_in_period=1,
            period_closed=True,
            cost_cents=1200.0,
            ai_calls=340,
        )

        assert {item.key for item in painel.metrics} == {
            "mrr",
            "arpu",
            "churn",
            "ai_cost",
            "margin",
        }
        for item in painel.metrics:
            assert item.basis, f"{item.key} não declara a base"
            if item.value is None:
                assert item.empty_reason
