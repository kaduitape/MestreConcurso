"""Catálogo de agentes e o grafo que decide a ordem de execução.

O pedido descreve oito agentes. Sete deles **já rodam** na plataforma, a maioria
com outro nome — análise de edital, inteligência estatística, estúdio de aulas,
baralho oficial de flashcards, tutor, auditoria de conteúdo e o analista de
melhorias. O orquestrador não os reimplementa: ele os nomeia, declara o que cada
um depende e os executa na ordem certa.

Três regras governam o que está aqui:

*Agente que não existe não finge que rodou.* Um dos oito (mestre de batalhas)
ainda depende de uma funcionalidade que a plataforma não tem: gerar questão com
gabarito validado na origem. Ele está declarado, com ``is_implemented=False``, e
o orquestrador o marca como **pulado com motivo escrito** — nunca como
concluído. Um passo verde que não fez nada é pior que um passo vermelho.

*Dependência é do grafo, não da ordem do arquivo.* Quem depende de quem está
declarado; a ordem de execução é derivada disso. Assim dá para rodar um agente
sozinho e saber exatamente o que precisa estar pronto antes.

*Paralelismo só onde não há dependência.* O pedido pede isso explicitamente, e
o grafo é o que permite responder quais passos podem correr juntos.

O módulo é puro: sem I/O, sem banco, sem IA.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentKey(StrEnum):
    """Os oito agentes do pedido."""

    NOTICE_ANALYST = "notice_analyst"
    STATISTICS = "statistics"
    TEACHER = "teacher"
    MEMORY = "memory"
    BATTLE_MASTER = "battle_master"
    TUTOR = "tutor"
    AUDITOR = "auditor"
    IMPROVEMENTS = "improvements"


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    #: Não rodou, e o motivo está escrito. Nunca se confunde com DONE.
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    #: Barrado pelo teto de gasto antes de chamar qualquer coisa.
    BUDGET_BLOCKED = "BUDGET_BLOCKED"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


#: Estados em que um passo não roda de novo numa retomada.
TERMINAL: frozenset[str] = frozenset({StepStatus.DONE, StepStatus.SKIPPED})


@dataclass(frozen=True, slots=True)
class AgentSpec:
    key: str
    label: str
    #: O que ele faz, em português, para a tela de acompanhamento.
    description: str
    #: Chaves de quem precisa ter terminado antes.
    depends_on: tuple[str, ...] = ()
    #: Falso enquanto o agente não existir de verdade. O orquestrador pula.
    is_implemented: bool = True
    #: Por que não está implementado. Vai para a tela no lugar do resultado.
    pending_reason: str | None = None
    #: Quantas tentativas automáticas antes de desistir.
    max_attempts: int = 1


AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        key=AgentKey.NOTICE_ANALYST,
        label="Analista de editais",
        description=(
            "Lê o PDF, estrutura disciplinas e tópicos, extrai datas e pesos e "
            "confere cada citação no documento."
        ),
        max_attempts=2,
    ),
    AgentSpec(
        key=AgentKey.STATISTICS,
        label="Inteligência estatística",
        description=(
            "Calcula incidência por disciplina e tópico a partir das provas "
            "disponíveis, com o tamanho da amostra à vista."
        ),
        depends_on=(AgentKey.NOTICE_ANALYST,),
        max_attempts=2,
    ),
    AgentSpec(
        key=AgentKey.TEACHER,
        label="Professor",
        description=(
            "Executa os planos de geração já confirmados: aulas e mapas mentais "
            "por tópico do edital, sempre como rascunho."
        ),
        depends_on=(AgentKey.STATISTICS,),
        max_attempts=2,
    ),
    AgentSpec(
        key=AgentKey.MEMORY,
        label="Memorização",
        description=(
            "Monta o baralho oficial de cada tópico do edital, em rascunho, a "
            "partir de aula publicada e com citação conferida."
        ),
        # Depende do Professor porque o insumo é a aula — e não qualquer aula: a
        # publicada, que alguém já conferiu.
        depends_on=(AgentKey.TEACHER,),
        max_attempts=2,
    ),
    AgentSpec(
        key=AgentKey.BATTLE_MASTER,
        label="Mestre de batalhas",
        description="Gera questões e desafios por tópico.",
        depends_on=(AgentKey.TEACHER,),
        is_implemented=False,
        pending_reason=(
            "A plataforma classifica questão por IA, mas não gera: falta a "
            "funcionalidade, com validação de gabarito, antes de produzir em massa."
        ),
    ),
    AgentSpec(
        key=AgentKey.TUTOR,
        label="Tutor adaptativo",
        description=(
            "Recalcula prioridades de estudo a partir do desempenho real dos "
            "candidatos neste concurso."
        ),
        depends_on=(AgentKey.STATISTICS,),
    ),
    AgentSpec(
        key=AgentKey.AUDITOR,
        label="Auditor de qualidade",
        description=(
            "Confere o conteúdo publicado do concurso com regras determinísticas e "
            "diz o que não deu para conferir."
        ),
        # Sem dependência de propósito. O auditor começou declarado como
        # dependente da geração em massa, mas o trabalho dele é outro: conferir
        # o que **já está publicado**. Amarrá-lo a agentes que ainda não
        # existem deixaria o portão de qualidade parado esperando a Fase 4.
        max_attempts=2,
    ),
    AgentSpec(
        key=AgentKey.IMPROVEMENTS,
        label="Analista de melhorias",
        description=(
            "Varre os registros da própria plataforma com detectores determinísticos "
            "e grava achados com evidência para uma pessoa decidir. Não aplica nada, "
            "não usa IA e não lê o repositório."
        ),
        # Sem dependência: ele analisa o que já aconteceu, e amarrá-lo a outro
        # agente deixaria a análise parada esperando uma execução que talvez
        # nem fosse disparada.
    ),
)

AGENT_BY_KEY: dict[str, AgentSpec] = {item.key: item for item in AGENTS}


class CycleError(ValueError):
    """O grafo de dependências se mordeu."""


def execution_order(agents: tuple[AgentSpec, ...] = AGENTS) -> list[list[str]]:
    """Agrupa os agentes em camadas que podem rodar em paralelo.

    Cada lista interna é um conjunto sem dependência entre si: o pedido pede
    paralelismo **apenas** onde não existe dependência, e é isto que responde
    onde ele existe.
    """
    pendentes = {item.key: set(item.depends_on) for item in agents}
    conhecidos = set(pendentes)
    # Dependência para fora do conjunto não trava o cálculo: rodar um
    # subconjunto de agentes precisa continuar possível.
    for key in pendentes:
        pendentes[key] &= conhecidos

    camadas: list[list[str]] = []
    resolvidos: set[str] = set()
    while pendentes:
        pronta = sorted(key for key, deps in pendentes.items() if deps <= resolvidos)
        if not pronta:
            raise CycleError("Dependência circular entre agentes: " + ", ".join(sorted(pendentes)))
        camadas.append(pronta)
        resolvidos |= set(pronta)
        for key in pronta:
            del pendentes[key]
    return camadas


def flat_order(agents: tuple[AgentSpec, ...] = AGENTS) -> list[str]:
    """A ordem linear, para quem executa um passo de cada vez."""
    return [key for camada in execution_order(agents) for key in camada]


@dataclass(frozen=True, slots=True)
class StepView:
    """O estado de um passo, do jeito que a tela precisa."""

    key: str
    label: str
    description: str
    status: str
    depends_on: tuple[str, ...] = ()
    attempts: int = 0
    max_attempts: int = 1
    detail: str | None = None
    is_implemented: bool = True

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL


def blocked_by(step: StepView, done: set[str]) -> list[str]:
    """Quais dependências ainda faltam para este passo poder rodar."""
    return sorted(key for key in step.depends_on if key not in done)


def can_retry(spec: AgentSpec, attempts: int) -> bool:
    """Se ainda cabe uma tentativa automática.

    Tentar de novo um agente que falhou por configuração (sem provedor, sem
    crédito) só queima tempo; por isso o teto de tentativas é por agente e
    pequeno, e a decisão de insistir manualmente continua sendo de uma pessoa.
    """
    return attempts < max(1, spec.max_attempts)


def initial_steps(agents: tuple[AgentSpec, ...] = AGENTS) -> list[StepView]:
    """Os passos de uma execução nova, na ordem de dependência."""
    ordem = flat_order(agents)
    por_chave = {item.key: item for item in agents}
    return [
        StepView(
            key=spec.key,
            label=spec.label,
            description=spec.description,
            status=StepStatus.PENDING,
            depends_on=spec.depends_on,
            max_attempts=spec.max_attempts,
            is_implemented=spec.is_implemented,
            detail=spec.pending_reason if not spec.is_implemented else None,
        )
        for spec in (por_chave[key] for key in ordem)
    ]


def summarize(steps: list[StepView]) -> str:
    """O estado da execução inteira, derivado dos passos.

    Execução só é ``DONE`` quando nenhum passo falhou nem foi barrado. Pulado
    não impede a conclusão: o agente declarou por que não rodou, e isso é um
    resultado legítimo — diferente de ter quebrado.
    """
    estados = {step.status for step in steps}
    if StepStatus.FAILED in estados or StepStatus.BUDGET_BLOCKED in estados:
        return RunStatus.FAILED
    if StepStatus.RUNNING in estados:
        return RunStatus.RUNNING
    if StepStatus.PENDING in estados:
        return RunStatus.PENDING if not (estados & TERMINAL) else RunStatus.RUNNING
    return RunStatus.DONE
