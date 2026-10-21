"""Roteador de modelos — a decisão e o rastro dela.

Dois testes pesam mais que os outros: o que cobra que **sinal ausente não vale
como falso** (uma regra sobre o tamanho da entrada, numa chamada que não
informou tamanho, tem de ficar *não avaliada* e dizer qual sinal faltou), e o
que cobra que o rastro traz **todas** as regras, não só a vencedora — um rastro
que para na primeira que atendeu não responde por que as outras não atenderam.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.model_routing import (
    RouteReason,
    Rule,
    RuleOutcome,
    SignalKey,
    Signals,
    after_error,
    budget_used_pct,
    choose,
    evaluate,
)

PADRAO = {
    "default_model_id": 1,
    "default_model_slug": "modelo-padrao",
    "default_provider_slug": "openai",
}


def _rule(**overrides: object) -> Rule:
    base: dict[str, object] = {
        "id": 10,
        "label": "Edital grande",
        "priority": 100,
        "is_enabled": True,
        "model_id": 2,
        "model_slug": "modelo-grande",
        "provider_slug": "openai",
        "model_is_usable": True,
    }
    base.update(overrides)
    return Rule(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Sem regras
# --------------------------------------------------------------------------- #
def test_without_rules_the_binding_decides() -> None:
    decisao = choose([], Signals(), **PADRAO)  # type: ignore[arg-type]

    assert decisao.reason is RouteReason.BINDING_DEFAULT
    assert decisao.model_slug == "modelo-padrao"
    assert decisao.rule_id is None
    assert "nenhuma regra cadastrada" in decisao.explanation


def test_the_explanation_says_whether_rules_existed_and_none_applied() -> None:
    regra = _rule(min_input_chars=100_000)
    decisao = choose([regra], Signals(input_chars=10), **PADRAO)  # type: ignore[arg-type]

    assert decisao.reason is RouteReason.BINDING_DEFAULT
    assert "nenhuma regra se aplicou" in decisao.explanation


# --------------------------------------------------------------------------- #
# A regra que atende
# --------------------------------------------------------------------------- #
def test_a_matching_rule_replaces_the_bound_model() -> None:
    decisao = choose(
        [_rule(min_input_chars=50_000)],
        Signals(input_chars=80_000),
        **PADRAO,  # type: ignore[arg-type]
    )

    assert decisao.reason is RouteReason.RULE_MATCHED
    assert decisao.model_slug == "modelo-grande"
    assert decisao.rule_label == "Edital grande"
    # A explicação carrega o número observado, não só o nome da regra.
    assert "80.000 caracteres" in decisao.explanation


def test_the_first_rule_by_priority_wins() -> None:
    barata = _rule(id=1, priority=10, label="Barata", model_id=3, model_slug="modelo-barato")
    grande = _rule(id=2, priority=20, label="Grande", model_id=4, model_slug="modelo-grande")

    decisao = choose([grande, barata], Signals(input_chars=1), **PADRAO)  # type: ignore[arg-type]

    assert decisao.model_slug == "modelo-barato"
    assert decisao.rule_label == "Barata"


def test_a_rule_without_conditions_applies_to_every_call_and_says_so() -> None:
    rastro = evaluate(_rule(), Signals())

    assert rastro.outcome is RuleOutcome.MATCHED
    assert "sem condição cadastrada" in rastro.detail


def test_all_conditions_of_a_rule_must_hold_together() -> None:
    regra = _rule(min_input_chars=1_000, requires_json=True)

    assert evaluate(regra, Signals(input_chars=2_000, needs_json=True)).outcome is (
        RuleOutcome.MATCHED
    )
    assert evaluate(regra, Signals(input_chars=2_000, needs_json=False)).outcome is (
        RuleOutcome.NOT_MATCHED
    )


def test_min_and_max_input_bound_a_window() -> None:
    regra = _rule(min_input_chars=1_000, max_input_chars=5_000)

    assert evaluate(regra, Signals(input_chars=3_000)).outcome is RuleOutcome.MATCHED
    assert evaluate(regra, Signals(input_chars=9_000)).outcome is RuleOutcome.NOT_MATCHED


# --------------------------------------------------------------------------- #
# Sinal ausente não vale como falso
# --------------------------------------------------------------------------- #
def test_a_rule_that_needs_a_signal_the_call_did_not_declare_is_not_evaluated() -> None:
    """O teste que pesa: ausência não é zero.

    Tratar "não informou o tamanho" como "tamanho zero" faria a condição
    "entrada acima de 50 mil caracteres" parecer respondida — quando ninguém
    mediu nada.
    """
    rastro = evaluate(_rule(min_input_chars=50_000), Signals())

    assert rastro.outcome is RuleOutcome.NOT_EVALUATED
    assert rastro.missing_signals == (SignalKey.INPUT_CHARS,)
    assert "tamanho da entrada" in rastro.detail


def test_a_not_evaluated_rule_never_wins() -> None:
    decisao = choose([_rule(min_input_chars=1)], Signals(), **PADRAO)  # type: ignore[arg-type]

    assert decisao.reason is RouteReason.BINDING_DEFAULT
    assert decisao.model_slug == "modelo-padrao"


def test_without_a_monthly_ceiling_a_budget_rule_cannot_be_evaluated() -> None:
    # Sem teto não existe "percentual do teto": o sinal é ausente, não zero.
    assert budget_used_pct(Decimal("500"), Decimal("0")) is None

    rastro = evaluate(_rule(min_budget_used_pct=Decimal("80")), Signals())
    assert rastro.outcome is RuleOutcome.NOT_EVALUATED
    assert rastro.missing_signals == (SignalKey.BUDGET_USED_PCT,)


def test_with_a_ceiling_the_pressure_signal_is_a_real_percentage() -> None:
    assert budget_used_pct(Decimal("900"), Decimal("1000")) == Decimal("90.00")

    rastro = evaluate(
        _rule(min_budget_used_pct=Decimal("80")), Signals(budget_used_pct=Decimal("90"))
    )
    assert rastro.outcome is RuleOutcome.MATCHED


# --------------------------------------------------------------------------- #
# Regra que não pode valer
# --------------------------------------------------------------------------- #
def test_a_disabled_rule_is_reported_as_disabled_not_as_unmatched() -> None:
    rastro = evaluate(_rule(is_enabled=False, min_input_chars=1), Signals(input_chars=10))

    assert rastro.outcome is RuleOutcome.DISABLED


def test_a_rule_pointing_at_an_unusable_model_cannot_apply_and_says_why() -> None:
    rastro = evaluate(_rule(model_is_usable=False), Signals())

    assert rastro.outcome is RuleOutcome.UNUSABLE
    assert "não está disponível" in rastro.detail


def test_an_unusable_rule_does_not_block_the_next_one() -> None:
    quebrada = _rule(id=1, priority=10, model_is_usable=False)
    boa = _rule(id=2, priority=20, label="Boa", model_id=5, model_slug="modelo-bom")

    decisao = choose([quebrada, boa], Signals(), **PADRAO)  # type: ignore[arg-type]

    assert decisao.model_slug == "modelo-bom"


# --------------------------------------------------------------------------- #
# O rastro
# --------------------------------------------------------------------------- #
def test_the_trace_covers_every_rule_not_only_the_winner() -> None:
    """O outro teste que pesa.

    Um rastro que para na regra vencedora não responde por que as outras não
    venceram — e é essa a pergunta que o histórico existe para responder.
    """
    regras = [
        _rule(id=1, priority=10, label="Primeira", min_input_chars=1),
        _rule(id=2, priority=20, label="Segunda", min_input_chars=100_000),
        _rule(id=3, priority=30, label="Terceira", is_enabled=False),
    ]

    decisao = choose(regras, Signals(input_chars=500), **PADRAO)  # type: ignore[arg-type]

    assert decisao.rule_label == "Primeira"
    assert [item.label for item in decisao.trace] == ["Primeira", "Segunda", "Terceira"]
    assert [item.outcome for item in decisao.trace] == [
        RuleOutcome.MATCHED,
        RuleOutcome.NOT_MATCHED,
        RuleOutcome.DISABLED,
    ]


def test_only_declared_signals_appear_in_the_record() -> None:
    sinais = Signals(input_chars=120, needs_json=True)

    assert sinais.as_dict() == {"input_chars": 120, "needs_json": True}
    assert sinais.known() == (SignalKey.INPUT_CHARS, SignalKey.NEEDS_JSON)


# --------------------------------------------------------------------------- #
# Desvio depois do erro
# --------------------------------------------------------------------------- #
def test_the_fallback_decision_names_the_model_that_failed_and_the_error() -> None:
    decisao = after_error(
        failed_model_slug="modelo-caro",
        error_code="ai_provider_rate_limited",
        model_id=9,
        model_slug="modelo-reserva",
        provider_slug="aisa",
    )

    assert decisao.reason is RouteReason.FALLBACK_AFTER_ERROR
    assert decisao.model_slug == "modelo-reserva"
    assert "modelo-caro" in decisao.explanation
    assert "ai_provider_rate_limited" in decisao.explanation
