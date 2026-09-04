"""Fase 4 da gamificação: duelos, eventos, Modo Guerra e card compartilhável.

O card é o ponto mais delicado do produto inteiro: ele sai da plataforma e vai
para um lugar onde ninguém pode conferir o contexto. Metade destes testes existe
por causa dele.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.game.duels import (
    DuelOutcome,
    DuelSide,
    resolve,
)
from app.domain.game.events import (
    EVENT_METRICS,
    EventGoal,
    evaluate,
    validate_goals,
)
from app.domain.game.share_card import (
    FORBIDDEN_FRAGMENTS,
    MIN_ATTEMPTS,
    MIN_REVIEWS,
    ApprovalClaimError,
    CardInput,
    assert_no_approval_claim,
    build_card,
)
from app.domain.game.war_mode import (
    MAX_DAYS,
    MIN_DAILY_MINUTES,
    MIN_DAYS,
    DayActivity,
    WarPlan,
    WarStatus,
    build_progress,
    review_plan,
    validate_plan,
)


class TestDuels:
    def test_sem_adversario_nao_ha_placar(self):
        result = resolve(DuelSide("a", "Ana", 10, 8, 300, True), None)

        assert result.outcome == DuelOutcome.UNDECIDED
        assert result.winner_key is None
        assert "Aguardando" in result.headline

    def test_convite_sem_resposta_expira(self):
        result = resolve(DuelSide("a", "Ana", 10, 8, 300, True), None, expired=True)

        assert result.outcome == DuelOutcome.EXPIRED
        assert result.winner_key is None

    def test_o_resultado_so_sai_com_os_dois_lados_prontos(self):
        result = resolve(
            DuelSide("a", "Ana", 10, 9, 300, True),
            DuelSide("b", "Bruno", 4, 4, 120, False),
        )

        assert result.outcome == DuelOutcome.UNDECIDED
        assert result.winner_key is None
        assert any("só é declarado" in line for line in result.lines)

    def test_vitoria_por_ausencia_e_dita_com_esse_nome(self):
        """Vencer porque o outro não jogou não é vencer no desempenho."""
        result = resolve(
            DuelSide("a", "Ana", 10, 6, 300, True),
            DuelSide("b", "Bruno", 2, 2, 60, False),
            expired=True,
        )

        assert result.outcome == DuelOutcome.WALKOVER
        assert result.winner_key == "a"
        assert "por ausência" in result.headline
        assert any("não mede desempenho comparado" in line for line in result.lines)

    def test_vence_quem_acerta_mais(self):
        result = resolve(
            DuelSide("a", "Ana", 10, 6, 400, True),
            DuelSide("b", "Bruno", 10, 8, 200, True),
        )

        assert result.outcome == DuelOutcome.WIN
        assert result.winner_key == "b"
        assert result.margin == 2

    def test_empate_em_acertos_desempata_pelo_tempo_e_diz_isso(self):
        result = resolve(
            DuelSide("a", "Ana", 10, 7, 280, True),
            DuelSide("b", "Bruno", 10, 7, 340, True),
        )

        assert result.winner_key == "a"
        assert any("desempate foi pelo tempo" in line for line in result.lines)

    def test_empate_completo_e_empate(self):
        result = resolve(
            DuelSide("a", "Ana", 10, 7, 300, True),
            DuelSide("b", "Bruno", 10, 7, 300, True),
        )

        assert result.outcome == DuelOutcome.TIE
        assert result.winner_key is None

    def test_prazo_esgotado_sem_ninguem_terminar_nao_produz_vencedor(self):
        result = resolve(
            DuelSide("a", "Ana", 3, 2, 90, False),
            DuelSide("b", "Bruno", 1, 1, 30, False),
            expired=True,
        )

        assert result.winner_key is None
        assert "não há resultado" in result.lines[0]


class TestEvents:
    def test_so_metricas_conhecidas_entram_num_evento(self):
        erros = validate_goals([EventGoal("horas_de_sorte", 10)])

        assert erros
        assert "Métrica desconhecida" in erros[0]

    def test_evento_sem_meta_e_recusado(self):
        assert validate_goals([]) == ["Um evento precisa de pelo menos uma meta."]

    def test_meta_zerada_e_recusada(self):
        erros = validate_goals([EventGoal("questions", 0)])
        assert any("maior que zero" in item for item in erros)

    def test_o_progresso_sai_dos_numeros_reais(self):
        progress = evaluate(
            [EventGoal("questions", 100), EventGoal("focus_minutes", 300)],
            {"questions": 60, "focus_minutes": 300},
        )

        questoes = progress.goals[0]
        assert questoes.current == 60
        assert questoes.ratio == 0.6
        assert questoes.completed is False
        assert progress.goals[1].completed is True
        assert progress.completed_goals == 1

    def test_evento_so_e_cumprido_com_todas_as_metas(self):
        parcial = evaluate(
            [EventGoal("questions", 10), EventGoal("reviews", 10)],
            {"questions": 10, "reviews": 3},
        )
        completo = evaluate(
            [EventGoal("questions", 10), EventGoal("reviews", 10)],
            {"questions": 10, "reviews": 12},
        )

        assert parcial.completed is False
        assert completo.completed is True

    def test_a_razao_nunca_passa_de_um(self):
        progress = evaluate([EventGoal("questions", 10)], {"questions": 900})
        assert progress.goals[0].ratio == 1.0

    def test_a_janela_diz_quantos_dias_faltam(self):
        progress = evaluate(
            [EventGoal("questions", 10)],
            {"questions": 4},
            starts_on=date(2026, 3, 1),
            ends_on=date(2026, 3, 8),
            today=date(2026, 3, 5),
        )

        assert progress.days_left == 3
        assert progress.is_open is True

    def test_o_evento_declara_que_nao_mexe_no_rank(self):
        progress = evaluate([EventGoal("questions", 10)], {})
        assert "não altera o seu rank" in progress.note

    def test_todas_as_metricas_tem_rotulo_legivel(self):
        for metric, label in EVENT_METRICS.items():
            assert label and label != metric


class TestWarMode:
    def test_periodo_fora_do_limite_e_recusado(self):
        curto = validate_plan(WarPlan(MIN_DAYS - 1, 120, 20))
        longo = validate_plan(WarPlan(MAX_DAYS + 1, 120, 20))

        assert curto and longo

    def test_meta_diaria_abaixo_do_minimo_e_recusada(self):
        erros = validate_plan(WarPlan(7, MIN_DAILY_MINUTES - 1, 20))
        assert any("meta diária de estudo" in item for item in erros)

    def test_plano_valido_passa(self):
        assert validate_plan(WarPlan(7, 120, 20)) == []

    def test_meta_muito_acima_do_historico_gera_aviso_sem_bloquear(self):
        avisos = review_plan(WarPlan(7, 240, 20), average_minutes=40)

        assert len(avisos) == 1
        assert "média recente" in avisos[0].message
        assert validate_plan(WarPlan(7, 240, 20)) == [], "avisar não é bloquear"

    def test_sem_historico_nao_ha_aviso_inventado(self):
        assert review_plan(WarPlan(7, 600, 20), average_minutes=None) == []

    def test_o_dia_de_hoje_ainda_nao_conta_como_perdido(self):
        progress = build_progress(
            WarPlan(5, 120, 0),
            [DayActivity(date(2026, 3, 1), 130)],
            starts_on=date(2026, 3, 1),
            today=date(2026, 3, 2),
        )

        assert progress.days_met == 1
        assert progress.days_missed == 0, "o dia corrente ainda pode ser cumprido"

    def test_dia_abaixo_da_meta_conta_como_perdido(self):
        progress = build_progress(
            WarPlan(5, 120, 20),
            [DayActivity(date(2026, 3, 1), 130, 25), DayActivity(date(2026, 3, 2), 130, 5)],
            starts_on=date(2026, 3, 1),
            today=date(2026, 3, 3),
        )

        assert progress.days_met == 1
        assert progress.days_missed == 1, "cumpriu os minutos, não as questões"

    def test_a_mensagem_descreve_sem_acusar(self):
        progress = build_progress(
            WarPlan(5, 120, 0),
            [DayActivity(date(2026, 3, 1), 10)],
            starts_on=date(2026, 3, 1),
            today=date(2026, 3, 4),
        )
        texto = progress.message.lower()

        for proibido in ("falhou", "perdeu tudo", "você não conseguiu", "fracass"):
            assert proibido not in texto

    def test_periodo_concluido_inteiro_e_reconhecido(self):
        dias = [DayActivity(date(2026, 3, day), 130, 25) for day in range(1, 4)]
        progress = build_progress(
            WarPlan(3, 120, 20),
            dias,
            starts_on=date(2026, 3, 1),
            today=date(2026, 3, 5),
            status=WarStatus.FINISHED,
        )

        assert progress.is_over is True
        assert progress.succeeded is True
        assert progress.ratio == 1.0

    def test_periodo_encerrado_com_falhas_ainda_reconhece_o_que_foi_feito(self):
        progress = build_progress(
            WarPlan(3, 120, 0),
            [DayActivity(date(2026, 3, 1), 130)],
            starts_on=date(2026, 3, 1),
            today=date(2026, 3, 9),
        )

        assert progress.succeeded is False
        assert "continua valendo" in progress.message


class TestShareCard:
    def test_o_card_barra_qualquer_promessa_de_aprovacao(self):
        for fragment in FORBIDDEN_FRAGMENTS:
            with pytest.raises(ApprovalClaimError):
                assert_no_approval_claim(f"Texto com {fragment} no meio.")

    def test_texto_comum_passa(self):
        assert_no_approval_claim("Nível 7 · Ouro · 340 questões respondidas.")

    def test_o_rodape_nega_previsao_de_resultado(self):
        card = build_card(CardInput(display_name="Marina"))

        assert "não resultado em prova" in card.footer
        assert "Game of Concursos" in card.footer

    def test_estatistica_sem_amostra_nao_entra_e_o_motivo_aparece(self):
        card = build_card(
            CardInput(
                display_name="Marina",
                questions_answered=MIN_ATTEMPTS - 1,
                accuracy=0.97,
                reviews=MIN_REVIEWS - 1,
                recall_rate=0.99,
            ),
            include={"accuracy", "retention"},
        )

        assert card.stats == []
        assert len(card.omitted) == 2
        assert str(MIN_ATTEMPTS) in card.omitted[0]

    def test_com_amostra_a_estatistica_entra_com_a_base(self):
        card = build_card(
            CardInput(display_name="Marina", questions_answered=340, accuracy=0.72),
            include={"accuracy"},
        )
        acerto = card.stats[0]

        assert acerto.value == "72%"
        assert "340 respostas" in acerto.detail

    def test_cobertura_exige_plano_ativo(self):
        sem_plano = build_card(CardInput(display_name="Marina", coverage=0.6), include={"coverage"})
        com_plano = build_card(
            CardInput(display_name="Marina", coverage=0.6, has_plan=True), include={"coverage"}
        )

        assert sem_plano.stats == []
        assert "não há plano" in sem_plano.omitted[0]
        assert com_plano.stats[0].value == "60%"

    def test_o_candidato_escolhe_o_que_entra(self):
        card = build_card(
            CardInput(display_name="Marina", level=9, current_streak=14),
            include={"streak"},
        )

        assert [item.key for item in card.stats] == ["streak"]
        assert card.stats[0].value == "14 dias"

    def test_o_card_declara_que_xp_nao_entra_no_rank(self):
        card = build_card(CardInput(display_name="Marina", rank_name="Ouro"), include={"rank"})
        assert "XP não entra" in card.stats[0].detail
