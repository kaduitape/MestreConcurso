"""Analista de melhorias — o que cada detector pode afirmar.

Três testes pesam mais que os outros: o que cobra que **sem amostra não há
achado** (e que o motivo diz o que falta), o que cobra que o gabarito suspeito é
medido **contra o acaso** e não contra um número absoluto, e o que cobra que
**economia só aparece com custo medido**.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.improvements import (
    DETECTORS,
    CompetitionGaps,
    Destination,
    DetectorKey,
    DetectorStatus,
    FeatureErrors,
    QuestionStats,
    RouteActivity,
    Severity,
    TopicGap,
    inert_routes,
    model_error_rates,
    suspect_answer_keys,
    topics_without_material,
)


def _question(**overrides: object) -> QuestionStats:
    base: dict[str, object] = {
        "public_id": "Q1",
        "statement": "Segundo o Código Penal, o homicídio qualificado",
        "attempts": 100,
        "correct": 8,
        "alternatives": 4,
        "answer_letter": "A",
        "most_chosen_letter": "C",
        "most_chosen_count": 70,
        "subject_name": "Direito Penal",
    }
    base.update(overrides)
    return QuestionStats(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
def test_every_detector_declares_its_scope_and_its_thresholds() -> None:
    """Detector sem alcance declarado deixa "nada encontrado" virar garantia."""
    assert len(DETECTORS) == 4
    for spec in DETECTORS:
        assert spec.scope, f"{spec.key} precisa dizer o que olha e o que não olha"
        assert spec.defaults, f"{spec.key} precisa ter limiares editáveis"
        assert "mute_days" in spec.defaults


def test_no_detector_proposes_a_patch() -> None:
    """Decisão D1, opção A: o analista descreve a mudança, não a escreve."""
    for spec in DETECTORS:
        assert spec.destination in {Destination.ADMIN, Destination.DEVELOPMENT}


# --------------------------------------------------------------------------- #
# 1. Gabarito suspeito
# --------------------------------------------------------------------------- #
def test_without_the_minimum_sample_there_is_no_finding_only_what_is_missing() -> None:
    """O teste que pesa mais: amostra pequena não produz acusação."""
    resultado = suspect_answer_keys(
        [_question(attempts=5, correct=0)],
        min_attempts=30,
        chance_divisor=2,
        considered=12,
    )

    assert resultado.status is DetectorStatus.NOT_ENOUGH_DATA
    assert resultado.findings == ()
    assert "30 respostas" in resultado.detail
    assert "12 questão(ões)" in resultado.detail


def test_the_threshold_is_relative_to_chance_not_an_absolute_number() -> None:
    """20% é desastre em 4 alternativas e esperado em 5 com gabarito difícil."""
    quatro = suspect_answer_keys(
        [_question(attempts=100, correct=12, alternatives=4)],
        min_attempts=30,
        chance_divisor=2,
        considered=1,
    )
    assert quatro.status is DetectorStatus.FOUND  # acaso 25%, limite 12,5%

    cinco = suspect_answer_keys(
        [_question(attempts=100, correct=12, alternatives=5)],
        min_attempts=30,
        chance_divisor=2,
        considered=1,
    )
    assert cinco.status is DetectorStatus.CLEAN  # acaso 20%, limite 10%


def test_the_finding_carries_the_evidence_that_produced_it() -> None:
    resultado = suspect_answer_keys([_question()], min_attempts=30, chance_divisor=2, considered=1)

    achado = resultado.findings[0]
    assert achado.severity is Severity.HIGH
    assert achado.destination is Destination.ADMIN
    assert achado.target_public_id == "Q1"
    assert achado.evidence["attempts"] == 100
    assert achado.evidence["chance"] == 0.25
    # A alternativa mais marcada é a evidência mais forte do detector.
    assert "alternativa mais marcada foi a C" in achado.detail
    assert "gabarito aponta a A" in achado.detail


def test_a_question_without_alternatives_has_no_chance_to_compare_against() -> None:
    resultado = suspect_answer_keys(
        [_question(alternatives=0)], min_attempts=30, chance_divisor=2, considered=1
    )

    assert resultado.status is DetectorStatus.CLEAN


def test_the_fingerprint_is_stable_across_runs() -> None:
    """A segunda passada atualiza o achado; não cria o segundo igual."""
    primeiro = suspect_answer_keys(
        [_question()], min_attempts=30, chance_divisor=2, considered=1
    ).findings[0]
    segundo = suspect_answer_keys(
        [_question(attempts=200, correct=16)], min_attempts=30, chance_divisor=2, considered=1
    ).findings[0]

    assert primeiro.fingerprint == segundo.fingerprint
    assert primeiro.fingerprint == f"{DetectorKey.SUSPECT_ANSWER_KEY}:Q1"


# --------------------------------------------------------------------------- #
# 2. Tópico do edital sem material
# --------------------------------------------------------------------------- #
def _gaps(**overrides: object) -> CompetitionGaps:
    base: dict[str, object] = {
        "competition_public_id": "C1",
        "competition_name": "Concurso de Teste",
        "notice_title": "Edital nº 1/2026",
        "gaps": (
            TopicGap("Crase", "Português", Decimal("1.00"), 10),
            TopicGap("Regência", "Português", Decimal("3.00"), 20),
        ),
        "linked_topics": 10,
    }
    base.update(overrides)
    return CompetitionGaps(**base)  # type: ignore[arg-type]


def test_the_gap_list_is_ordered_by_what_the_notice_says_it_costs() -> None:
    resultado = topics_without_material([_gaps()], min_topics=1, top_topics=10)

    achado = resultado.findings[0]
    # Regência (peso 3 × 20 questões) vem antes de Crase (peso 1 × 10).
    assert achado.detail.index("Regência") < achado.detail.index("Crase")
    assert achado.evidence["top"][0]["topic"] == "Regência"  # type: ignore[index]


def test_a_topic_without_weight_goes_last_and_the_text_says_why() -> None:
    """Sem peso não há com o que comparar — e isso não é o mesmo que valer pouco."""
    resultado = topics_without_material(
        [
            _gaps(
                gaps=(
                    TopicGap("Sem peso", "Português", None, None),
                    TopicGap("Com peso", "Português", Decimal("2.00"), 10),
                )
            )
        ],
        min_topics=1,
        top_topics=10,
    )

    achado = resultado.findings[0]
    assert achado.detail.index("Com peso") < achado.detail.index("Sem peso")
    assert "não por serem menos importantes" in achado.detail


def test_without_any_analysed_competition_the_detector_says_so() -> None:
    resultado = topics_without_material([], min_topics=1, top_topics=10)

    assert resultado.status is DetectorStatus.NOT_ENOUGH_DATA
    assert "edital analisado" in resultado.detail


def test_a_competition_with_material_everywhere_is_clean() -> None:
    resultado = topics_without_material([_gaps(gaps=())], min_topics=1, top_topics=10)

    assert resultado.status is DetectorStatus.CLEAN


def test_the_severity_rises_when_the_gap_covers_half_the_notice() -> None:
    poucos = topics_without_material([_gaps(linked_topics=20)], min_topics=1, top_topics=10)
    muitos = topics_without_material([_gaps(linked_topics=3)], min_topics=1, top_topics=10)

    assert poucos.findings[0].severity is Severity.MEDIUM
    assert muitos.findings[0].severity is Severity.HIGH


# --------------------------------------------------------------------------- #
# 3. Modelo errando acima do limiar
# --------------------------------------------------------------------------- #
def _errors(**overrides: object) -> FeatureErrors:
    base: dict[str, object] = {
        "feature": "question.classify",
        "feature_label": "Classificação de questões",
        "model_slug": "gpt-4o-mini",
        "provider_slug": "openai",
        "calls": 100,
        "errors": 30,
        "error_cost_cents": Decimal("250"),
        "top_error_code": "ProviderRateLimitedError",
    }
    base.update(overrides)
    return FeatureErrors(**base)  # type: ignore[arg-type]


def test_a_feature_erroring_above_the_threshold_is_found_with_the_measured_waste() -> None:
    resultado = model_error_rates([_errors()], window_days=7, min_calls=20, error_rate_percent=10)

    achado = resultado.findings[0]
    assert achado.severity is Severity.HIGH  # 30% >= 25%
    assert achado.measured_waste_cents == Decimal("250")
    assert "R$ 2,50" in achado.detail
    assert "ProviderRateLimitedError" in achado.detail


def test_without_a_registered_price_no_saving_is_claimed() -> None:
    """O terceiro teste que pesa: economia só com número medido."""
    resultado = model_error_rates(
        [_errors(error_cost_cents=Decimal("0"))],
        window_days=7,
        min_calls=20,
        error_rate_percent=10,
    )

    achado = resultado.findings[0]
    assert achado.measured_waste_cents is None
    assert "não pode ser estimado em dinheiro" in achado.detail
    assert "R$" not in achado.detail


def test_below_the_minimum_calls_the_detector_declines_and_says_the_volume() -> None:
    resultado = model_error_rates(
        [_errors(calls=5, errors=5)], window_days=7, min_calls=20, error_rate_percent=10
    )

    assert resultado.status is DetectorStatus.NOT_ENOUGH_DATA
    assert "5 chamada(s)" in resultado.detail


def test_a_feature_within_the_threshold_is_clean() -> None:
    resultado = model_error_rates(
        [_errors(errors=2)], window_days=7, min_calls=20, error_rate_percent=10
    )

    assert resultado.status is DetectorStatus.CLEAN


# --------------------------------------------------------------------------- #
# 4. Regra de roteamento inerte
# --------------------------------------------------------------------------- #
def _route(**overrides: object) -> RouteActivity:
    base: dict[str, object] = {
        "route_id": 7,
        "label": "Edital grande",
        "feature": "notice.extraction",
        "feature_label": "Análise de edital",
        "model_slug": "gpt-4o",
        "evaluated": 120,
        "matched": 0,
        "not_evaluated": 0,
        "missing_signals": (),
    }
    base.update(overrides)
    return RouteActivity(**base)  # type: ignore[arg-type]


def test_a_rule_whose_condition_never_held_points_at_the_threshold() -> None:
    resultado = inert_routes(
        [_route()], window_days=30, min_decisions=50, rows_read=500, max_rows=2000
    )

    achado = resultado.findings[0]
    assert "a condição nunca valeu" in achado.detail
    assert "limiar" in achado.proposal


def test_a_rule_starved_of_its_signal_says_no_threshold_will_fix_it() -> None:
    """Os dois motivos levam a providências diferentes, e o texto os separa."""
    resultado = inert_routes(
        [_route(not_evaluated=120, missing_signals=("BUDGET_USED_PCT",))],
        window_days=30,
        min_decisions=50,
        rows_read=500,
        max_rows=2000,
    )

    achado = resultado.findings[0]
    assert "Nenhum ajuste de limiar muda isso" in achado.detail
    assert "BUDGET_USED_PCT" in achado.detail


def test_a_rule_that_applied_at_least_once_is_not_inert() -> None:
    resultado = inert_routes(
        [_route(matched=3)], window_days=30, min_decisions=50, rows_read=500, max_rows=2000
    )

    assert resultado.status is DetectorStatus.CLEAN


def test_the_reading_cap_is_declared_in_the_finding() -> None:
    """O alcance da leitura entra na evidência: sem ele, "nunca se aplicou" é
    uma afirmação sobre o histórico inteiro, que o detector não olhou."""
    resultado = inert_routes(
        [_route()], window_days=30, min_decisions=50, rows_read=2000, max_rows=2000
    )

    assert resultado.findings[0].evidence["rows_read"] == 2000
    assert resultado.findings[0].evidence["max_rows"] == 2000


def test_without_enough_decisions_the_detector_declines() -> None:
    resultado = inert_routes(
        [_route(evaluated=3)], window_days=30, min_decisions=50, rows_read=10, max_rows=2000
    )

    assert resultado.status is DetectorStatus.NOT_ENOUGH_DATA
    assert "10 decisão(ões) lidas" in resultado.detail
