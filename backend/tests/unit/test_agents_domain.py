"""O catálogo de agentes e o grafo que decide a ordem.

O teste que mais importa aqui é o que separa **pulado** de **concluído**. Um
agente que ainda não existe não pode aparecer verde: um passo verde que não fez
nada é pior que um passo vermelho, porque ninguém vai investigar.
"""

from __future__ import annotations

import pytest

from app.domain.agents import (
    AGENT_BY_KEY,
    AGENTS,
    AgentKey,
    AgentSpec,
    CycleError,
    RunStatus,
    StepStatus,
    StepView,
    blocked_by,
    can_retry,
    execution_order,
    flat_order,
    initial_steps,
    summarize,
)


def _step(key: str, status: str, **kwargs: object) -> StepView:
    spec = AGENT_BY_KEY[key]
    return StepView(
        key=key,
        label=spec.label,
        description=spec.description,
        status=status,
        depends_on=spec.depends_on,
        **kwargs,  # type: ignore[arg-type]
    )


def test_the_eight_agents_of_the_request_are_declared() -> None:
    assert len(AGENTS) == 8
    assert {item.key for item in AGENTS} == set(AgentKey)


def test_every_agent_explains_itself_in_portuguese() -> None:
    for spec in AGENTS:
        assert spec.label and spec.description


def test_an_agent_that_does_not_exist_says_why() -> None:
    """Sem motivo escrito, "pulado" vira mistério."""
    for spec in AGENTS:
        if not spec.is_implemented:
            assert spec.pending_reason, f"{spec.key} precisa dizer por que não roda"


def test_the_order_respects_the_dependencies() -> None:
    ordem = flat_order()
    posicao = {key: index for index, key in enumerate(ordem)}
    for spec in AGENTS:
        for dependencia in spec.depends_on:
            assert posicao[dependencia] < posicao[spec.key], (
                f"{spec.key} roda antes de {dependencia}"
            )


def test_layers_group_what_can_run_together() -> None:
    """O pedido pede paralelismo só onde não há dependência."""
    camadas = execution_order()
    # Memória e mestre de batalhas dependem do professor e de mais ninguém:
    # podem correr juntos.
    juntos = next(
        (camada for camada in camadas if AgentKey.MEMORY in camada),
        [],
    )
    assert AgentKey.BATTLE_MASTER in juntos


def test_the_first_layer_needs_nobody() -> None:
    primeira = execution_order()[0]
    for key in primeira:
        assert AGENT_BY_KEY[key].depends_on == ()


def test_a_cycle_is_refused_instead_of_looping_forever() -> None:
    ciclo = (
        AgentSpec(key="a", label="A", description="x", depends_on=("b",)),
        AgentSpec(key="b", label="B", description="y", depends_on=("a",)),
    )
    with pytest.raises(CycleError):
        execution_order(ciclo)


def test_running_a_subset_still_works() -> None:
    """Dependência para fora do conjunto não pode travar o cálculo."""
    subconjunto = (AGENT_BY_KEY[AgentKey.STATISTICS],)
    assert execution_order(subconjunto) == [[AgentKey.STATISTICS]]


# --------------------------------------------------------------------------- #
# Estado
# --------------------------------------------------------------------------- #
def test_a_new_run_starts_with_everything_pending() -> None:
    passos = initial_steps()
    assert len(passos) == 8
    assert all(step.status == StepStatus.PENDING for step in passos)


def test_an_unimplemented_agent_already_carries_its_reason() -> None:
    passos = {step.key: step for step in initial_steps()}
    professor = passos[AgentKey.TEACHER]
    assert professor.is_implemented is False
    assert professor.detail and "Fase 4" in professor.detail


def test_the_auditor_does_not_wait_for_agents_that_do_not_exist() -> None:
    """O portão de qualidade confere o que **já está publicado**.

    Ele nasceu declarado como dependente da geração em massa; amarrá-lo a
    agentes que ainda não existem deixaria o portão parado esperando a Fase 4.
    """
    auditor = AGENT_BY_KEY[AgentKey.AUDITOR]

    assert auditor.is_implemented is True
    assert auditor.depends_on == ()


def test_blocked_by_lists_what_is_missing() -> None:
    passo = _step(AgentKey.STATISTICS, StepStatus.PENDING)
    assert blocked_by(passo, done=set()) == [AgentKey.NOTICE_ANALYST]
    assert blocked_by(passo, done={AgentKey.NOTICE_ANALYST}) == []


def test_retry_respects_the_agent_ceiling() -> None:
    spec = AGENT_BY_KEY[AgentKey.NOTICE_ANALYST]
    assert spec.max_attempts == 2
    assert can_retry(spec, attempts=1) is True
    assert can_retry(spec, attempts=2) is False


# --------------------------------------------------------------------------- #
# O resumo da execução
# --------------------------------------------------------------------------- #
def test_a_failed_step_fails_the_run() -> None:
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE),
        _step(AgentKey.STATISTICS, StepStatus.FAILED),
    ]
    assert summarize(passos) == RunStatus.FAILED


def test_being_cut_by_the_budget_fails_the_run_too() -> None:
    """Parar por falta de orçamento não é conclusão."""
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE),
        _step(AgentKey.STATISTICS, StepStatus.BUDGET_BLOCKED),
    ]
    assert summarize(passos) == RunStatus.FAILED


def test_skipped_does_not_prevent_completion() -> None:
    """Pulado com motivo é resultado legítimo; quebrado não é."""
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE),
        _step(AgentKey.AUDITOR, StepStatus.SKIPPED),
    ]
    assert summarize(passos) == RunStatus.DONE


def test_a_run_in_progress_says_so() -> None:
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.RUNNING),
        _step(AgentKey.STATISTICS, StepStatus.PENDING),
    ]
    assert summarize(passos) == RunStatus.RUNNING


def test_an_untouched_run_is_pending() -> None:
    assert summarize(initial_steps()) == RunStatus.PENDING
