"""Plano de geração em massa: o que gerar, o que reaproveitar e quanto custa.

O teste que sustenta a fase é o da estimativa sem histórico. Devolver um número
ali seria chute vestido de previsão — e um chute sobre 300 tópicos vira uma
fatura que ninguém autorizou.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.generation import (
    CostSample,
    Decision,
    ExistingContent,
    GenerationKind,
    ItemStatus,
    PlanStatus,
    TopicRef,
    estimate_plan,
    median,
    plan_items,
    plan_status,
    summarize,
)

AULA = GenerationKind.TRAINING_LESSON
MAPA = GenerationKind.MIND_MAP
FEATURE_AULA = "training.script"
FEATURE_MAPA = "mindmap.generation"


def _topicos(quantos: int) -> list[TopicRef]:
    return [
        TopicRef(
            topic_id=indice,
            topic_name=f"Tópico {indice}",
            subject_id=1,
            subject_name="Português",
        )
        for indice in range(1, quantos + 1)
    ]


# --------------------------------------------------------------------------- #
# O que gerar
# --------------------------------------------------------------------------- #
def test_a_topic_without_content_is_planned_for_generation() -> None:
    itens = plan_items(_topicos(2), [AULA], [])

    assert [item.decision for item in itens] == [Decision.GENERATE, Decision.GENERATE]
    assert all(item.reason for item in itens), "decisão sem motivo escrito vira mistério"


def test_one_item_per_topic_and_kind() -> None:
    itens = plan_items(_topicos(3), [AULA, MAPA], [])

    assert len(itens) == 6
    assert {item.kind for item in itens} == {AULA, MAPA}


def test_existing_content_is_reused_instead_of_generated_again() -> None:
    """Gerar de novo seria pagar duas vezes pelo mesmo texto."""
    existente = [ExistingContent(topic_id=1, kind=AULA, public_id="aula-antiga")]

    itens = plan_items(_topicos(2), [AULA], existente)

    assert itens[0].decision == Decision.REUSE
    assert itens[0].existing_public_id == "aula-antiga"
    assert itens[1].decision == Decision.GENERATE


def test_content_from_another_competition_counts_as_reuse() -> None:
    """O vínculo é com o tópico canônico, e ele atravessa concursos."""
    existente = [
        ExistingContent(
            topic_id=1, kind=AULA, public_id="aula-de-outro", from_other_competition=True
        )
    ]

    itens = plan_items(_topicos(1), [AULA], existente)

    assert itens[0].decision == Decision.REUSE
    assert "outro concurso" in itens[0].reason


def test_when_the_origin_is_unknown_the_reason_does_not_claim_one() -> None:
    """O mapa mental se liga ao tópico, não ao concurso: não dá para saber de onde veio."""
    existente = [ExistingContent(topic_id=1, kind=MAPA, public_id="mapa-qualquer")]

    itens = plan_items(_topicos(1), [MAPA], existente)

    assert itens[0].decision == Decision.REUSE
    assert itens[0].reason == "Já existe conteúdo para este tópico."


def test_content_from_this_competition_wins_over_content_from_outside() -> None:
    """É o daqui que a pessoa vai encontrar primeiro quando for revisar."""
    existente = [
        ExistingContent(topic_id=1, kind=AULA, public_id="de-fora", from_other_competition=True),
        ExistingContent(topic_id=1, kind=AULA, public_id="daqui", from_other_competition=False),
    ]

    itens = plan_items(_topicos(1), [AULA], existente)

    assert itens[0].existing_public_id == "daqui"


def test_the_plan_respects_the_ceiling() -> None:
    itens = plan_items(_topicos(400), [AULA], [], max_items=10)

    assert len(itens) == 10


# --------------------------------------------------------------------------- #
# Quanto custa
# --------------------------------------------------------------------------- #
def test_the_estimate_comes_from_the_measured_median() -> None:
    itens = plan_items(_topicos(4), [AULA], [])
    amostras = {FEATURE_AULA: CostSample(FEATURE_AULA, count=9, median_cents=Decimal("12.5"))}

    estimativa = estimate_plan(itens, amostras)

    assert estimativa.is_known is True
    assert estimativa.cents == Decimal("50.0")
    assert estimativa.basis[FEATURE_AULA]["items"] == 4
    assert estimativa.basis[FEATURE_AULA]["samples"] == 9


def test_without_enough_history_there_is_no_estimate() -> None:
    """O teste que sustenta a fase: chute sobre centenas de tópicos vira fatura."""
    itens = plan_items(_topicos(300), [AULA], [])
    amostras = {FEATURE_AULA: CostSample(FEATURE_AULA, count=2, median_cents=Decimal("12.5"))}

    estimativa = estimate_plan(itens, amostras)

    assert estimativa.is_known is False
    assert estimativa.cents == Decimal("0")
    assert estimativa.unknown_features == (FEATURE_AULA,)
    assert estimativa.basis[FEATURE_AULA]["median_cents"] is None


def test_a_partial_estimate_is_marked_incomplete() -> None:
    """Somar o desconhecido como zero faria a estimativa parecer completa."""
    itens = plan_items(_topicos(2), [AULA, MAPA], [])
    amostras = {
        FEATURE_AULA: CostSample(FEATURE_AULA, count=10, median_cents=Decimal("10")),
        FEATURE_MAPA: CostSample(FEATURE_MAPA, count=1, median_cents=Decimal("30")),
    }

    estimativa = estimate_plan(itens, amostras)

    assert estimativa.is_known is False
    assert estimativa.cents == Decimal("20"), "só a parte que dava para estimar"
    assert estimativa.unknown_features == (FEATURE_MAPA,)


def test_what_is_reused_does_not_enter_the_estimate() -> None:
    existente = [ExistingContent(topic_id=1, kind=AULA, public_id="x")]
    itens = plan_items(_topicos(2), [AULA], existente)
    amostras = {FEATURE_AULA: CostSample(FEATURE_AULA, count=5, median_cents=Decimal("10"))}

    estimativa = estimate_plan(itens, amostras)

    assert estimativa.cents == Decimal("10"), "um gerado, um reaproveitado"


def test_an_empty_plan_costs_nothing_and_is_known() -> None:
    estimativa = estimate_plan([], {})

    assert estimativa.cents == Decimal("0")
    assert estimativa.is_known is True


def test_the_median_resists_an_isolated_spike() -> None:
    valores = [Decimal("10"), Decimal("11"), Decimal("12"), Decimal("900")]

    assert median(valores) == Decimal("11.5")
    assert median([]) == Decimal("0")


# --------------------------------------------------------------------------- #
# O que aconteceu
# --------------------------------------------------------------------------- #
def test_progress_is_derived_from_the_items() -> None:
    progresso = summarize(
        [
            ItemStatus.DONE,
            ItemStatus.DONE,
            ItemStatus.REUSED,
            ItemStatus.FAILED,
            ItemStatus.BUDGET_BLOCKED,
            ItemStatus.PENDING,
        ]
    )

    assert progresso.total == 6
    assert progresso.done == 2
    assert progresso.reused == 1
    assert progresso.failed == 1
    assert progresso.blocked == 1
    assert progresso.pending == 1


def test_a_plan_with_a_blocked_item_is_not_running_forever() -> None:
    """Barrado pelo teto é desfecho, não espera: o plano termina e diz o que faltou."""
    assert plan_status([ItemStatus.DONE, ItemStatus.BUDGET_BLOCKED]) == PlanStatus.DONE
    assert plan_status([ItemStatus.DONE, ItemStatus.PENDING]) == PlanStatus.RUNNING
