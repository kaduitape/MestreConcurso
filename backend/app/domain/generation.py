"""Geração em massa por tópico do edital: o que gerar, o que já existe, e quanto custa.

Três decisões moram aqui, todas puras:

**O que gerar.** Para cada tópico do edital e cada tipo de conteúdo, o plano diz
*gerar* ou *reaproveitar*. Reaproveitar não é preguiça: o vínculo com o tópico
canônico atravessa concursos, então uma aula de "Crase" feita para um concurso
já serve a qualquer outro que cobre o mesmo tópico. Gerar de novo seria pagar
duas vezes pelo mesmo texto.

**Quanto custa.** A estimativa sai do **custo medido** das execuções anteriores
da mesma funcionalidade — a mediana, que não se deixa levar por um estouro
isolado. Sem amostra suficiente, a resposta é *não dá para estimar*, nunca um
número inventado. É o motivo pelo qual a medição (Fase 2) veio antes desta fase.

**O que aconteceu.** O resumo é derivado dos itens, nunca acumulado num contador.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class GenerationKind(StrEnum):
    TRAINING_LESSON = "TRAINING_LESSON"
    MIND_MAP = "MIND_MAP"
    #: Baralho oficial do tópico. Depende de material já conferido por uma
    #: pessoa: cartão não nasce de rascunho de IA.
    FLASHCARD_DECK = "FLASHCARD_DECK"
    #: Questões inéditas do tópico, em rascunho, com o gabarito conferido na
    #: origem. Mesma dependência de material conferido.
    QUESTION_SET = "QUESTION_SET"


#: Qual funcionalidade de IA cada tipo consome. É por ela que o custo medido é
#: procurado, e é ela que o teto de gasto conhece.
FEATURE_OF: Mapping[str, str] = {
    GenerationKind.TRAINING_LESSON: "training.script",
    GenerationKind.MIND_MAP: "mindmap.generation",
    GenerationKind.FLASHCARD_DECK: "flashcard.generation",
    GenerationKind.QUESTION_SET: "question.generation",
}


class Decision(StrEnum):
    GENERATE = "GENERATE"
    #: Já existe conteúdo publicado para este tópico — inclusive de outro
    #: concurso da mesma banca.
    REUSE = "REUSE"


class ItemStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"
    REUSED = "REUSED"
    FAILED = "FAILED"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    CANCELED = "CANCELED"
    #: Não rodou, ou rodou e não sobrou nada, por **falta de material
    #: conferível** — e isso não é falha do item. Cobre os dois casos de
    #: ausência de insumo: não havia aula publicada para o tópico, ou havia e
    #: nada que a IA escreveu a partir dela passou pela conferência. Chamar
    #: qualquer um dos dois de ``FAILED`` mandaria alguém procurar um defeito
    #: onde não há.
    NO_SOURCE = "NO_SOURCE"


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    #: Uma pessoa viu a estimativa e mandou rodar.
    CONFIRMED = "CONFIRMED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    CANCELED = "CANCELED"


#: Abaixo deste número de execuções medidas, não há estimativa — há chute.
MIN_SAMPLES = 3

#: Teto de itens por plano. Vive aqui como padrão; o painel manda.
MAX_ITEMS = 500


@dataclass(frozen=True, slots=True)
class TopicRef:
    """Um tópico do conteúdo programático, já ligado ao catálogo."""

    topic_id: int
    topic_name: str
    subject_id: int | None
    subject_name: str


@dataclass(frozen=True, slots=True)
class ExistingContent:
    """Conteúdo que já cobre um tópico."""

    topic_id: int
    kind: str
    public_id: str
    #: Complemento do motivo, quando "já existe conteúdo" conta pouco. Para
    #: questão, por exemplo, o que importa é **quantas** já existem.
    detail: str | None = None
    #: Verdadeiro quando veio de outro concurso — o reaproveitamento de fato.
    #: ``None`` quer dizer que não dá para saber: o mapa mental, por exemplo,
    #: se liga ao tópico e não ao concurso. Inventar a origem no texto do
    #: motivo seria mentir num lugar barato de acertar.
    from_other_competition: bool | None = None


@dataclass(frozen=True, slots=True)
class PlannedItem:
    topic_id: int
    topic_name: str
    subject_id: int | None
    subject_name: str
    kind: str
    decision: str
    #: Por que esta decisão, em português.
    reason: str
    existing_public_id: str | None = None


def plan_items(
    topics: Sequence[TopicRef],
    kinds: Sequence[str],
    existing: Iterable[ExistingContent],
    *,
    max_items: int = MAX_ITEMS,
) -> list[PlannedItem]:
    """Monta o plano: um item por tópico e tipo, com a decisão escrita.

    A ordem é a do edital, e o corte pelo teto acontece no fim: cortar no meio
    de uma disciplina deixaria o plano com metade de um assunto.
    """
    por_tipo: dict[tuple[int, str], ExistingContent] = {}
    for item in existing:
        chave = (item.topic_id, item.kind)
        # O conteúdo do próprio concurso tem precedência sobre o de fora: é ele
        # que a pessoa vai encontrar primeiro quando for revisar.
        if chave not in por_tipo or (
            por_tipo[chave].from_other_competition is True and item.from_other_competition is False
        ):
            por_tipo[chave] = item

    planejados: list[PlannedItem] = []
    for topic in topics:
        for kind in kinds:
            achado = por_tipo.get((topic.topic_id, kind))
            if achado is None:
                planejados.append(
                    PlannedItem(
                        topic_id=topic.topic_id,
                        topic_name=topic.topic_name,
                        subject_id=topic.subject_id,
                        subject_name=topic.subject_name,
                        kind=kind,
                        decision=Decision.GENERATE,
                        reason="Não há conteúdo deste tipo para o tópico.",
                    )
                )
                continue
            if achado.from_other_competition is None:
                motivo = "Já existe conteúdo para este tópico."
            elif achado.from_other_competition:
                motivo = "Já existe conteúdo de outro concurso para este tópico."
            else:
                motivo = "Já existe conteúdo deste concurso para o tópico."
            if achado.detail:
                motivo = f"{motivo.rstrip('.')}: {achado.detail}."
            planejados.append(
                PlannedItem(
                    topic_id=topic.topic_id,
                    topic_name=topic.topic_name,
                    subject_id=topic.subject_id,
                    subject_name=topic.subject_name,
                    kind=kind,
                    decision=Decision.REUSE,
                    reason=motivo,
                    existing_public_id=achado.public_id,
                )
            )
    return planejados[:max_items]


@dataclass(frozen=True, slots=True)
class CostSample:
    """O custo medido de uma funcionalidade: mediana e tamanho da amostra."""

    feature: str
    count: int
    median_cents: Decimal


def median(values: Sequence[Decimal]) -> Decimal:
    """Mediana. Um estouro isolado não move o número como moveria a média."""
    if not values:
        return Decimal("0")
    ordenados = sorted(values)
    meio = len(ordenados) // 2
    if len(ordenados) % 2 == 1:
        return ordenados[meio]
    return (ordenados[meio - 1] + ordenados[meio]) / 2


@dataclass(frozen=True, slots=True)
class PlanEstimate:
    """A estimativa, com a conta à mostra.

    ``is_known`` falso quer dizer que **falta histórico** para alguma parte —
    o que está em ``cents`` é só o pedaço que dava para estimar, e a tela
    precisa dizer isso. Somar o desconhecido como zero faria a estimativa
    parecer completa, que é a forma mais silenciosa de errar o orçamento.
    """

    cents: Decimal
    is_known: bool
    #: Por funcionalidade: quantos itens, quantas execuções medidas, a mediana.
    basis: dict[str, dict[str, object]] = field(default_factory=dict)
    #: Funcionalidades sem amostra suficiente.
    unknown_features: tuple[str, ...] = ()


def estimate_plan(
    items: Sequence[PlannedItem],
    samples: Mapping[str, CostSample],
    *,
    min_samples: int = MIN_SAMPLES,
) -> PlanEstimate:
    """Estima o custo do que será **gerado**. Reaproveitado não custa nada."""
    contagem: dict[str, int] = {}
    for item in items:
        if item.decision != Decision.GENERATE:
            continue
        feature = FEATURE_OF[item.kind]
        contagem[feature] = contagem.get(feature, 0) + 1

    total = Decimal("0")
    conhecido = True
    base: dict[str, dict[str, object]] = {}
    desconhecidas: list[str] = []

    for feature, quantos in sorted(contagem.items()):
        amostra = samples.get(feature)
        if amostra is None or amostra.count < min_samples:
            conhecido = False
            desconhecidas.append(feature)
            base[feature] = {
                "items": quantos,
                "samples": amostra.count if amostra else 0,
                "median_cents": None,
            }
            continue
        parcial = amostra.median_cents * quantos
        total += parcial
        base[feature] = {
            "items": quantos,
            "samples": amostra.count,
            "median_cents": str(amostra.median_cents),
        }

    return PlanEstimate(
        cents=total,
        is_known=conhecido,
        basis=base,
        unknown_features=tuple(desconhecidas),
    )


@dataclass(frozen=True, slots=True)
class PlanProgress:
    total: int
    pending: int
    done: int
    reused: int
    failed: int
    blocked: int
    no_source: int = 0


def summarize(statuses: Sequence[str]) -> PlanProgress:
    """O progresso é derivado dos itens, nunca acumulado num contador."""
    return PlanProgress(
        total=len(statuses),
        pending=sum(1 for item in statuses if item == ItemStatus.PENDING),
        done=sum(1 for item in statuses if item == ItemStatus.DONE),
        reused=sum(1 for item in statuses if item == ItemStatus.REUSED),
        failed=sum(1 for item in statuses if item == ItemStatus.FAILED),
        blocked=sum(1 for item in statuses if item == ItemStatus.BUDGET_BLOCKED),
        no_source=sum(1 for item in statuses if item == ItemStatus.NO_SOURCE),
    )


def plan_status(statuses: Sequence[str]) -> str:
    """Terminou quando não sobrou item pendente."""
    if not statuses:
        return PlanStatus.DONE
    if any(item == ItemStatus.PENDING for item in statuses):
        return PlanStatus.RUNNING
    return PlanStatus.DONE
