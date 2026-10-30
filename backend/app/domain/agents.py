"""Catálogo de agentes e o grafo que decide a ordem de execução.

O pedido descreve oito agentes, e os oito **já rodam** na plataforma, a maioria
com outro nome — análise de edital, inteligência estatística, estúdio de aulas,
baralho oficial de flashcards, geração de questões, tutor, auditoria de conteúdo
e o analista de melhorias. O orquestrador não os reimplementa: ele os nomeia, declara o que cada
um depende e os executa na ordem certa.

Três regras governam o que está aqui:

*Agente que não existe não finge que rodou.* Hoje os oito têm implementação, mas
a regra continua escrita aqui porque ela é a que sustenta o orquestrador: um
agente sem implementação registrada é marcado como **pulado com motivo escrito**
— nunca como concluído. Um passo verde que não fez nada é pior que um passo
vermelho. A mesma regra vale para o agente que roda e não encontra o que fazer:
ele diz o que faltava, em português.

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
    """Onde um passo está. Cada estado responde uma pergunta diferente.

    A distinção que mais importa é entre **falta de insumo** e **falha**:
    "o edital não tem PDF" e "o código quebrou" exigem ações opostas de quem
    lê a tela, e tratá-los como a mesma coisa (como era) gastava tentativas
    num problema que nenhuma tentativa resolve.
    """

    #: Aguardando execução.
    PENDING = "PENDING"
    #: Executando agora.
    RUNNING = "RUNNING"
    #: Cumpriu o contrato e persistiu o resultado.
    DONE = "DONE"
    #: Cumpriu o contrato, com ressalvas declaradas. Verde, mas com o que
    #: ficou de fora dito — não é o mesmo que concluído sem observação.
    DONE_WITH_NOTES = "DONE_WITH_NOTES"
    #: Rodou e não havia o que fazer. É resultado legítimo, com motivo escrito.
    SKIPPED = "SKIPPED"
    #: Falta insumo ou configuração: PDF, provedor de IA, amostra, candidato.
    #: **Não consome tentativa** — nenhuma repetição resolve, e queimar as
    #: tentativas aqui foi o que escondia a causa real atrás de "esgotou".
    AWAITING_INPUT = "AWAITING_INPUT"
    #: Uma dependência não cumpriu o contrato dela. O motivo vem com o nome
    #: do passo que faltou **e o que aconteceu com ele**.
    BLOCKED = "BLOCKED"
    #: Declarado no catálogo e sem implementação registrada, ou não aplicável.
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    #: Quebrou. A causa fica no detalhe e no histórico de tentativas.
    FAILED = "FAILED"
    #: Barrado pelo teto de gasto antes de chamar qualquer coisa.
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    #: Interrompido por decisão de alguém.
    CANCELED = "CANCELED"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    #: Tudo que podia rodar rodou, e sobrou coisa esperando alguém. Não é
    #: "concluída" (mentiria sobre o que falta) nem "falhou" (nada quebrou).
    DONE_WITH_NOTES = "DONE_WITH_NOTES"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


#: Estados em que o passo **cumpriu o contrato**. É o que satisfaz dependência.
#: ``SKIPPED`` fica de fora de propósito: "não havia o que fazer" é resultado
#: honesto do passo, mas não entrega o insumo que o próximo esperava.
FULFILLED: frozenset[str] = frozenset({StepStatus.DONE, StepStatus.DONE_WITH_NOTES})

#: Estados em que um passo não roda de novo numa retomada. ``AWAITING_INPUT`` e
#: ``BLOCKED`` ficam fora: é justamente para eles que retomar serve — o PDF foi
#: anexado, a dependência terminou, e agora o passo tem o que precisava.
TERMINAL: frozenset[str] = frozenset(
    {
        StepStatus.DONE,
        StepStatus.DONE_WITH_NOTES,
        StepStatus.SKIPPED,
        StepStatus.NOT_IMPLEMENTED,
        StepStatus.CANCELED,
    }
)

#: Estados que **não** consomem tentativa: nenhum deles chegou a executar o
#: agente, ou executou e descobriu que faltava insumo.
NO_ATTEMPT_CONSUMED: frozenset[str] = frozenset(
    {
        StepStatus.AWAITING_INPUT,
        StepStatus.BLOCKED,
        StepStatus.BUDGET_BLOCKED,
        StepStatus.NOT_IMPLEMENTED,
        StepStatus.CANCELED,
    }
)

#: Estados que pedem uma ação de alguém para destravar.
NEEDS_ACTION: frozenset[str] = frozenset(
    {StepStatus.AWAITING_INPUT, StepStatus.BUDGET_BLOCKED, StepStatus.FAILED}
)

#: Estados que são ressalva na execução inteira: alguém pode agir sobre eles.
RUN_NOTES: frozenset[str] = frozenset(
    {
        StepStatus.AWAITING_INPUT,
        StepStatus.BLOCKED,
        StepStatus.BUDGET_BLOCKED,
        StepStatus.NOT_IMPLEMENTED,
        StepStatus.DONE_WITH_NOTES,
    }
)

#: O que cada estado que trava pede como próxima ação, para a tela oferecer o
#: botão certo em vez de só mostrar o problema.
ACTION_HINT: dict[str, str] = {
    StepStatus.AWAITING_INPUT: "RESOLVE_INPUT",
    StepStatus.BUDGET_BLOCKED: "RAISE_BUDGET",
    StepStatus.FAILED: "RETRY_STEP",
    StepStatus.BLOCKED: "RESOLVE_DEPENDENCY",
}


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
        # Depende do **edital**, não da estatística. Era o contrário, e isso
        # travava a criação de aula sobre tópico já confirmado só porque não
        # havia prova anterior da banca para medir incidência. A incidência
        # ordena o que vem primeiro; ela não autoriza o tópico a existir.
        depends_on=(AgentKey.NOTICE_ANALYST,),
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
        description=(
            "Escreve questões inéditas por tópico do edital, em rascunho, com o "
            "gabarito conferido na origem e sem procedência de banca."
        ),
        # Depende do Professor pelo mesmo motivo da memorização: o insumo é a
        # aula publicada, não qualquer texto.
        depends_on=(AgentKey.TEACHER,),
        max_attempts=2,
    ),
    AgentSpec(
        key=AgentKey.TUTOR,
        label="Tutor adaptativo",
        description=(
            "Recalcula prioridades de estudo a partir do desempenho real dos "
            "candidatos neste concurso. Sem histórico, ordena pelo edital e diz "
            "que a ordem é inicial."
        ),
        # Também solto da estatística: candidato sem histórico e banca sem
        # prova anterior são duas ausências diferentes, e nenhuma das duas
        # impede ordenar o estudo pelo que o edital cobra.
        depends_on=(AgentKey.NOTICE_ANALYST,),
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

    @property
    def fulfilled(self) -> bool:
        """Cumpriu o contrato. É isto que satisfaz dependência."""
        return self.status in FULFILLED

    @property
    def attempts_exhausted(self) -> bool:
        """Não cabe mais tentativa automática.

        É propriedade derivada, e não um estado: o estado continua sendo
        ``FAILED`` com a **causa** da última falha no detalhe. Sobrescrever o
        detalhe com "esgotou as tentativas" apagava o diagnóstico, que era
        justamente o que alguém precisava ler.
        """
        return self.status == StepStatus.FAILED and self.attempts >= max(1, self.max_attempts)

    @property
    def action(self) -> str | None:
        """O que a tela deve oferecer para destravar este passo."""
        return ACTION_HINT.get(self.status)


def blocked_by(step: StepView, done: set[str]) -> list[str]:
    """Quais dependências ainda faltam para este passo poder rodar."""
    return sorted(key for key in step.depends_on if key not in done)


def blocking_reason(spec: AgentSpec, by_key: dict[str, StepView]) -> str | None:
    """Por que este passo não pode rodar, com o que houve na dependência.

    "Depende do Analista de editais" obriga quem lê a tela a caçar o outro
    passo para descobrir o que aconteceu. A frase inteira — *"depende do
    Analista de editais, que está aguardando insumo: o edital está cadastrado
    sem PDF"* — resolve o problema na primeira leitura, que é onde o diagnóstico
    tem valor.
    """
    partes: list[str] = []
    for key in spec.depends_on:
        dep = by_key.get(key)
        if dep is not None and dep.fulfilled:
            continue
        rotulo = AGENT_BY_KEY[key].label if key in AGENT_BY_KEY else key
        if dep is None:
            partes.append(f"{rotulo} (ainda não executado)")
            continue
        estado = STATUS_LABEL.get(dep.status, dep.status)
        motivo = f": {dep.detail}" if dep.detail else ""
        partes.append(f"{rotulo} ({estado}{motivo})")
    if not partes:
        return None
    return "Depende de " + "; ".join(partes)


#: Como cada estado é dito em português. Usado no motivo do bloqueio e na tela.
STATUS_LABEL: dict[str, str] = {
    StepStatus.PENDING: "aguardando execução",
    StepStatus.RUNNING: "executando",
    StepStatus.DONE: "concluído",
    StepStatus.DONE_WITH_NOTES: "concluído com ressalvas",
    StepStatus.SKIPPED: "sem o que fazer",
    StepStatus.AWAITING_INPUT: "aguardando insumo",
    StepStatus.BLOCKED: "bloqueado por dependência",
    StepStatus.NOT_IMPLEMENTED: "não implementado",
    StepStatus.FAILED: "falhou",
    StepStatus.BUDGET_BLOCKED: "barrado pelo teto de gasto",
    StepStatus.CANCELED: "cancelado",
}


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

    Só ``FAILED`` quando algo **quebrou**. O teto de gasto saiu daqui: barrar
    por orçamento é a regra funcionando, e chamar isso de falha da execução
    mandava alguém procurar um defeito que não existe.

    ``DONE_WITH_NOTES`` é o estado que faltava: tudo que podia rodar rodou, e
    sobrou coisa esperando uma pessoa. Dizer "concluída" ali mentiria sobre o
    que falta; dizer "falhou" mentiria sobre o que quebrou.
    """
    estados = {step.status for step in steps}
    if StepStatus.FAILED in estados:
        return RunStatus.FAILED
    if StepStatus.RUNNING in estados:
        return RunStatus.RUNNING
    if StepStatus.PENDING in estados:
        return RunStatus.PENDING if not (estados & TERMINAL) else RunStatus.RUNNING
    if estados & RUN_NOTES:
        return RunStatus.DONE_WITH_NOTES
    return RunStatus.DONE
