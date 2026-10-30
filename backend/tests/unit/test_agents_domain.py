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
    blocking_reason,
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
    """E o motivo diz o que falta, não só que falta.

    O exemplo deste teste mudou três vezes conforme os agentes foram sendo
    construídos — e hoje os oito do pedido têm implementação, então não há
    agente real para usar de exemplo. A regra continua valendo para o próximo
    agente que for declarado antes de existir, e é ela que está sob teste: o
    passo nasce com ``is_implemented`` falso e **com o motivo escrito**, nunca
    com um rótulo genérico de "não implementado".
    """
    futuro = AgentSpec(
        key="agente_futuro",
        label="Agente futuro",
        description="Declarado antes de existir.",
        is_implemented=False,
        pending_reason="Falta a funcionalidade X, e é ela que precisa vir antes.",
    )

    passos = {step.key: step for step in initial_steps((futuro,))}

    assert passos["agente_futuro"].is_implemented is False
    assert passos["agente_futuro"].detail == futuro.pending_reason


def test_every_declared_agent_either_is_built_or_says_what_is_missing() -> None:
    """Nenhum agente pode ficar declarado sem motivo escrito.

    Hoje os oito estão construídos; este teste é o que impede que amanhã alguém
    acrescente um nono com ``is_implemented=False`` e sem explicação, deixando a
    tela dizer apenas "ainda não foi implementado".
    """
    sem_motivo = [
        spec.key for spec in AGENTS if not spec.is_implemented and not spec.pending_reason
    ]

    assert sem_motivo == []


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


def test_being_cut_by_the_budget_is_a_caveat_not_a_failure() -> None:
    """Teto de gasto é a regra funcionando, não defeito.

    Antes a execução virava ``FAILED``, o que mandava alguém procurar um erro
    de código onde havia um limite de orçamento sendo respeitado. Também não
    pode ser ``DONE``: alguma coisa deixou de rodar e isso precisa estar dito.
    """
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE),
        _step(AgentKey.STATISTICS, StepStatus.BUDGET_BLOCKED),
    ]
    assert summarize(passos) == RunStatus.DONE_WITH_NOTES


def test_only_something_broken_fails_the_run() -> None:
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE),
        _step(AgentKey.STATISTICS, StepStatus.FAILED),
    ]
    assert summarize(passos) == RunStatus.FAILED


def test_waiting_for_input_is_a_caveat_too() -> None:
    """ "Falta o PDF" não é conclusão limpa nem falha."""
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.AWAITING_INPUT),
        _step(AgentKey.AUDITOR, StepStatus.DONE),
    ]
    assert summarize(passos) == RunStatus.DONE_WITH_NOTES


def test_a_step_blocked_by_a_dependency_is_a_caveat() -> None:
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.AWAITING_INPUT),
        _step(AgentKey.TEACHER, StepStatus.BLOCKED),
    ]
    assert summarize(passos) == RunStatus.DONE_WITH_NOTES


def test_a_declared_agent_without_implementation_is_a_caveat() -> None:
    passos = [
        _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE),
        _step(AgentKey.MEMORY, StepStatus.NOT_IMPLEMENTED),
    ]
    assert summarize(passos) == RunStatus.DONE_WITH_NOTES


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


# --------------------------------------------------------------------------- #
# O que satisfaz dependência, e o que não
# --------------------------------------------------------------------------- #
def test_only_a_fulfilled_step_satisfies_a_dependency() -> None:
    """Pulado é resultado honesto do passo, mas não entrega insumo nenhum."""
    assert _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE).fulfilled is True
    assert _step(AgentKey.NOTICE_ANALYST, StepStatus.DONE_WITH_NOTES).fulfilled is True
    assert _step(AgentKey.NOTICE_ANALYST, StepStatus.SKIPPED).fulfilled is False
    assert _step(AgentKey.NOTICE_ANALYST, StepStatus.AWAITING_INPUT).fulfilled is False


def test_the_blocking_reason_carries_what_happened_to_the_dependency() -> None:
    """Sem isto, quem lê a tela tem de caçar o passo anterior."""
    por_chave = {
        AgentKey.NOTICE_ANALYST: StepView(
            key=AgentKey.NOTICE_ANALYST,
            label="Analista de editais",
            description="",
            status=StepStatus.AWAITING_INPUT,
            detail="O edital está cadastrado, mas sem arquivo PDF enviado.",
        )
    }
    motivo = blocking_reason(AGENT_BY_KEY[AgentKey.TEACHER], por_chave)
    assert motivo is not None
    assert "Analista de editais" in motivo
    assert "aguardando insumo" in motivo
    assert "sem arquivo PDF" in motivo


def test_a_fulfilled_dependency_does_not_block() -> None:
    por_chave = {
        AgentKey.NOTICE_ANALYST: StepView(
            key=AgentKey.NOTICE_ANALYST,
            label="Analista de editais",
            description="",
            status=StepStatus.DONE,
        )
    }
    assert blocking_reason(AGENT_BY_KEY[AgentKey.TEACHER], por_chave) is None


def test_lessons_do_not_depend_on_having_a_past_exam_sample() -> None:
    """A incidência ordena o que vem primeiro; não autoriza o tópico a existir."""
    professor = AGENT_BY_KEY[AgentKey.TEACHER]
    tutor = AGENT_BY_KEY[AgentKey.TUTOR]
    assert AgentKey.STATISTICS not in professor.depends_on
    assert AgentKey.STATISTICS not in tutor.depends_on
    assert professor.depends_on == (AgentKey.NOTICE_ANALYST,)
    assert tutor.depends_on == (AgentKey.NOTICE_ANALYST,)


def test_statistics_teacher_and_tutor_can_run_together() -> None:
    camadas = execution_order()
    segunda = set(camadas[1])
    assert {AgentKey.STATISTICS, AgentKey.TEACHER, AgentKey.TUTOR} <= segunda


def test_attempts_exhausted_is_derived_and_does_not_replace_the_cause() -> None:
    passo = StepView(
        key=AgentKey.AUDITOR,
        label="Auditor",
        description="",
        status=StepStatus.FAILED,
        attempts=2,
        max_attempts=2,
        detail='relation "content_audits" does not exist',
    )
    assert passo.attempts_exhausted is True
    # A causa continua lá: é ela que serve para diagnosticar.
    assert passo.detail is not None and "content_audits" in passo.detail
    assert passo.action == "RETRY_STEP"


def test_each_blocking_state_offers_an_action() -> None:
    for estado in (
        StepStatus.AWAITING_INPUT,
        StepStatus.BUDGET_BLOCKED,
        StepStatus.FAILED,
        StepStatus.BLOCKED,
    ):
        passo = StepView(key="x", label="X", description="", status=estado)
        assert passo.action is not None, estado
