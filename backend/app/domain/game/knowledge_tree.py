"""Árvore de conhecimento — o edital inteiro, com o estado real de cada ramo.

O Mapa do Edital (``territory.py``) já mostra **uma disciplina por território**.
Esta árvore desce um nível: dentro da disciplina, qual tópico do conteúdo
programático está medido, qual está só começado e qual a plataforma nem tem
material para ensinar. É a diferença entre saber que Português vai mal e saber
que o problema é Crase.

Quatro decisões governam este módulo, e todas as quatro são sobre não afirmar
mais do que se sabe:

*A árvore é a hierarquia do edital, não uma ordem de pré-requisitos.* Um
desenho de árvore sugere "só depois de passar por aqui". O edital **não declara
pré-requisito nenhum**, e inventar uma ordem pedagógica seria fabricar
conteúdo normativo. Os galhos são disciplina → tópico, na ordem em que o edital
escreveu, e a tela diz isso em voz alta.

*Nenhum nó tranca conteúdo.* Não existe estado ``LOCKED`` aqui — nem poderia:
travar matéria atrás de nível, liga ou pagamento é proibido no projeto. Todo
estado desta árvore é **descritivo**. Um tópico "não iniciado" está tão
disponível quanto um dominado.

*Sem amostra não há porcentagem.* Um tópico com três respostas não recebe taxa
de acerto; recebe o número de respostas que ainda faltam para a taxa começar a
significar algo. Taxa de acerto sobre três questões oscila 33 pontos com uma
resposta.

*Tópico sem vínculo com o catálogo é declarado, não escondido.* O tópico está
no edital, mas ninguém ligou aquele texto a um tópico do catálogo — então não há
como contar questões nem material dele. O nó aparece com o estado
``NOT_LINKED``, que é o equivalente, aqui, do ``NOT_CHECKED`` do auditor:
ausência de medição, não medição ruim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

#: Respostas mínimas para exibir taxa de acerto de um tópico. Abaixo disso a
#: taxa oscila mais do que o aprendizado que ela deveria descrever.
MIN_ANSWERS = 12

#: Acerto a partir do qual o tópico conta como dominado.
MASTERY_THRESHOLD = 0.75

#: Dias sem nenhuma atividade num tópico já dominado antes de ele pedir revisão.
STALE_DAYS = 21


class NodeKind(StrEnum):
    SUBJECT = "SUBJECT"
    TOPIC = "TOPIC"


class NodeState(StrEnum):
    """Estado de um ramo. Nenhum deles impede o acesso ao conteúdo.

    A ordem aqui é a de severidade crescente para quem está estudando, e é a
    que a tela usa para ordenar o que merece atenção.
    """

    #: Dominado e medido com amostra.
    MASTERED = "MASTERED"
    #: Dominado antes, sem atividade há tempo demais.
    NEEDS_REVIEW = "NEEDS_REVIEW"
    #: Amostra suficiente, acerto abaixo do domínio.
    MEASURED = "MEASURED"
    #: Começou, mas ainda não dá para medir.
    IN_PROGRESS = "IN_PROGRESS"
    #: Há material e questões; o candidato ainda não tocou.
    NOT_STARTED = "NOT_STARTED"
    #: O tópico do edital não foi vinculado ao catálogo: não há o que contar.
    NOT_LINKED = "NOT_LINKED"
    #: Vinculado, mas a plataforma não tem questão nem material deste tópico.
    NO_MATERIAL = "NO_MATERIAL"


#: Estados em que a plataforma **não mediu nada** — nem por falta de esforço do
#: candidato, mas por falta de vínculo ou de material. Somá-los ao que foi
#: medido transformaria uma lacuna da plataforma em desempenho do candidato.
UNMEASURED_STATES = frozenset({NodeState.NOT_LINKED, NodeState.NO_MATERIAL})


@dataclass(frozen=True, slots=True)
class Evidence:
    """O que foi contado para um ramo. Tudo derivado, nada acumulado.

    ``answers``/``correct`` vêm das respostas; ``cards``/``reviews`` das
    revisões; ``lessons_done`` do progresso real por aula. Nenhum destes
    números é um contador que a aplicação incrementa à parte — se fosse, ele
    poderia divergir do que a pessoa de fato respondeu.
    """

    answers: int = 0
    correct: int = 0
    questions_available: int = 0
    lessons_available: int = 0
    lessons_done: int = 0
    mind_maps_available: int = 0
    cards: int = 0
    reviews: int = 0
    recalled: int = 0
    #: Dias desde a última atividade do candidato neste ramo. ``None`` = nunca.
    days_since_activity: int | None = None

    def __add__(self, other: Evidence) -> Evidence:
        dias = [
            valor
            for valor in (self.days_since_activity, other.days_since_activity)
            if valor is not None
        ]
        return Evidence(
            answers=self.answers + other.answers,
            correct=self.correct + other.correct,
            questions_available=self.questions_available + other.questions_available,
            lessons_available=self.lessons_available + other.lessons_available,
            lessons_done=self.lessons_done + other.lessons_done,
            mind_maps_available=self.mind_maps_available + other.mind_maps_available,
            cards=self.cards + other.cards,
            reviews=self.reviews + other.reviews,
            recalled=self.recalled + other.recalled,
            # A atividade mais recente entre os filhos: é ela que diz se o ramo
            # esfriou, e o mínimo é o mais recente.
            days_since_activity=min(dias) if dias else None,
        )

    @property
    def has_material(self) -> bool:
        return bool(
            self.questions_available
            or self.lessons_available
            or self.mind_maps_available
            or self.cards
        )

    @property
    def touched(self) -> bool:
        return bool(self.answers or self.reviews or self.lessons_done)

    @property
    def accuracy(self) -> float | None:
        """Taxa de acerto, ou ``None`` quando a amostra não chega ao mínimo."""
        if self.answers < MIN_ANSWERS:
            return None
        return round(self.correct / self.answers, 4)

    @property
    def answers_missing(self) -> int:
        """Quantas respostas ainda faltam para a taxa de acerto aparecer."""
        return max(0, MIN_ANSWERS - self.answers)


@dataclass(frozen=True, slots=True)
class TopicInput:
    """Um tópico do conteúdo programático, com o que foi medido nele."""

    label: str
    order: int = 0
    #: Tópico do catálogo ao qual o texto do edital foi vinculado. ``None`` é o
    #: que produz ``NOT_LINKED``.
    topic_id: int | None = None
    #: Quantos subtópicos do catálogo entraram na conta deste nó.
    descendants: int = 0
    page_number: int | None = None
    evidence: Evidence = field(default_factory=Evidence)


@dataclass(frozen=True, slots=True)
class SubjectInput:
    """Uma disciplina do edital, com os tópicos dela."""

    label: str
    order: int = 0
    subject_id: int | None = None
    color_token: str = "subject-especifica"
    weight: str | None = None
    questions_count: int | None = None
    #: Procedência do que o edital disse sobre esta disciplina.
    evidence_level: str = "INFERRED"
    topics: tuple[TopicInput, ...] = ()


@dataclass(frozen=True, slots=True)
class TopicNode:
    kind: str
    label: str
    state: str
    reason: str
    order: int
    topic_id: int | None
    descendants: int
    page_number: int | None
    evidence: Evidence
    accuracy: float | None


@dataclass(frozen=True, slots=True)
class SubjectNode:
    kind: str
    label: str
    state: str
    reason: str
    order: int
    subject_id: int | None
    color_token: str
    weight: str | None
    questions_count: int | None
    evidence_level: str
    evidence: Evidence
    accuracy: float | None
    topics: tuple[TopicNode, ...]


@dataclass(frozen=True, slots=True)
class TreeSummary:
    """O retrato do edital inteiro, com as lacunas separadas do desempenho."""

    subjects: int = 0
    topics: int = 0
    #: Tópicos com amostra suficiente para ter taxa de acerto.
    measured: int = 0
    mastered: int = 0
    needs_review: int = 0
    in_progress: int = 0
    not_started: int = 0
    #: Lacunas da plataforma, nunca somadas ao desempenho do candidato.
    not_linked: int = 0
    no_material: int = 0

    @property
    def measurable(self) -> int:
        """Tópicos que a plataforma consegue medir, vinculados e com material."""
        return self.topics - self.not_linked - self.no_material


# --------------------------------------------------------------------------- #
# Estado de um ramo
# --------------------------------------------------------------------------- #
def _topic_state(topic: TopicInput) -> tuple[str, str]:
    if topic.topic_id is None:
        return (
            NodeState.NOT_LINKED,
            "este tópico do edital ainda não foi vinculado ao catálogo; sem vínculo "
            "não há como contar questões nem material dele",
        )
    return _state_from(topic.evidence)


def _state_from(evidencia: Evidence) -> tuple[str, str]:
    """Estado derivado só do que foi contado."""
    if not evidencia.has_material:
        return (
            NodeState.NO_MATERIAL,
            "a plataforma ainda não tem questão nem material cadastrado aqui",
        )
    if not evidencia.touched:
        return NodeState.NOT_STARTED, "há material disponível e nenhuma atividade sua ainda"

    acerto = evidencia.accuracy
    if acerto is None:
        faltam = evidencia.answers_missing
        return (
            NodeState.IN_PROGRESS,
            f"{evidencia.answers} resposta(s) registrada(s); faltam {faltam} para a "
            "taxa de acerto deixar de oscilar a cada questão",
        )

    porcentagem = round(acerto * 100)
    if acerto >= MASTERY_THRESHOLD:
        esfriou = (
            evidencia.days_since_activity is not None
            and evidencia.days_since_activity >= STALE_DAYS
        )
        if esfriou:
            return (
                NodeState.NEEDS_REVIEW,
                f"{porcentagem}% de acerto em {evidencia.answers} respostas, e "
                f"{evidencia.days_since_activity} dias sem nenhuma atividade aqui",
            )
        return (
            NodeState.MASTERED,
            f"{porcentagem}% de acerto em {evidencia.answers} respostas",
        )
    return (
        NodeState.MEASURED,
        f"{porcentagem}% de acerto em {evidencia.answers} respostas",
    )


# --------------------------------------------------------------------------- #
# Construção
# --------------------------------------------------------------------------- #
def build(subjects: list[SubjectInput] | tuple[SubjectInput, ...]) -> list[SubjectNode]:
    """Monta a árvore na ordem do edital.

    A disciplina **não** tem medição própria: a dela é a soma dos tópicos. Uma
    disciplina com número próprio ao lado da soma dos filhos daria dois valores
    para a mesma coisa, e eles divergiriam no primeiro tópico que faltasse.
    """
    arvore: list[SubjectNode] = []
    for materia in sorted(subjects, key=lambda item: (item.order, item.label)):
        topicos: list[TopicNode] = []
        soma = Evidence()
        for topico in sorted(materia.topics, key=lambda item: (item.order, item.label)):
            estado, motivo = _topic_state(topico)
            topicos.append(
                TopicNode(
                    kind=NodeKind.TOPIC,
                    label=topico.label,
                    state=estado,
                    reason=motivo,
                    order=topico.order,
                    topic_id=topico.topic_id,
                    descendants=topico.descendants,
                    page_number=topico.page_number,
                    evidence=topico.evidence,
                    accuracy=topico.evidence.accuracy,
                )
            )
            # Tópico sem vínculo não entra na soma: a medição dele não existe,
            # e somar zero puxaria a disciplina para baixo como se o candidato
            # tivesse errado algo que ninguém mediu.
            if topico.topic_id is not None:
                soma = soma + topico.evidence

        estado, motivo = _state_from(soma)
        arvore.append(
            SubjectNode(
                kind=NodeKind.SUBJECT,
                label=materia.label,
                state=estado,
                reason=motivo,
                order=materia.order,
                subject_id=materia.subject_id,
                color_token=materia.color_token,
                weight=materia.weight,
                questions_count=materia.questions_count,
                evidence_level=materia.evidence_level,
                evidence=soma,
                accuracy=soma.accuracy,
                topics=tuple(topicos),
            )
        )
    return arvore


def summarize(tree: list[SubjectNode] | tuple[SubjectNode, ...]) -> TreeSummary:
    contagem: dict[str, int] = {}
    total = 0
    for materia in tree:
        for topico in materia.topics:
            total += 1
            contagem[topico.state] = contagem.get(topico.state, 0) + 1
    return TreeSummary(
        subjects=len(tree),
        topics=total,
        measured=(
            contagem.get(NodeState.MEASURED, 0)
            + contagem.get(NodeState.MASTERED, 0)
            + contagem.get(NodeState.NEEDS_REVIEW, 0)
        ),
        mastered=contagem.get(NodeState.MASTERED, 0),
        needs_review=contagem.get(NodeState.NEEDS_REVIEW, 0),
        in_progress=contagem.get(NodeState.IN_PROGRESS, 0),
        not_started=contagem.get(NodeState.NOT_STARTED, 0),
        not_linked=contagem.get(NodeState.NOT_LINKED, 0),
        no_material=contagem.get(NodeState.NO_MATERIAL, 0),
    )


def attention_order(tree: list[SubjectNode] | tuple[SubjectNode, ...]) -> list[TopicNode]:
    """Tópicos que pedem atenção primeiro, e só os que a plataforma mediu.

    A ordem é: pede revisão, depois medido abaixo do domínio (pior acerto
    primeiro), depois em andamento. Tópico sem vínculo e sem material **não
    entra** — a providência deles é de quem cadastra conteúdo, não de quem
    estuda, e misturar as duas coisas transformaria lacuna da plataforma em
    tarefa do candidato.
    """
    prioridade = {
        NodeState.NEEDS_REVIEW: 0,
        NodeState.MEASURED: 1,
        NodeState.IN_PROGRESS: 2,
    }
    candidatos = [
        topico for materia in tree for topico in materia.topics if topico.state in prioridade
    ]
    return sorted(
        candidatos,
        key=lambda item: (
            prioridade[item.state],
            item.accuracy if item.accuracy is not None else 1.0,
            item.label,
        ),
    )
