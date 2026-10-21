"""Diferença entre duas versões de edital, e o que ela atinge.

Retificação é rotina em concurso: muda data, muda peso, entra disciplina, sai
tópico. O problema não é a mudança — é ninguém saber que ela aconteceu, e o
conteúdo continuar apontando para um programa que não existe mais.

Três regras governam este módulo:

**Nenhuma IA.** A comparação é entre duas análises que já existem. Comparar
rótulo com rótulo é trabalho determinístico; pedir a um modelo que "resuma o
que mudou" trocaria um fato por uma opinião que não se repete.

**Nada é apagado.** Tópico que saiu do edital deixa o conteúdo **órfão**, com o
motivo escrito — nunca removido. Quem decide o destino de uma aula é uma
pessoa, e um edital retificado pode ser retificado de novo.

**A procedência viaja junto.** Cada mudança carrega o nível de evidência do
dado novo: data conferida no PDF não é a mesma coisa que data deduzida. A tela
mostra as duas de forma diferente porque elas **não** são a mesma coisa.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.domain.catalog_match import normalize


class ChangeKind(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    CHANGED = "CHANGED"


class ChangeScope(StrEnum):
    SUBJECT = "SUBJECT"
    TOPIC = "TOPIC"
    EVENT = "EVENT"
    FACT = "FACT"


class ImpactAction(StrEnum):
    #: O tópico saiu do edital e o conteúdo ficou sem programa que o cobre.
    ORPHANED = "ORPHANED"
    #: Tópico novo, sem conteúdo nenhum.
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class SubjectEntry:
    raw_label: str
    subject_id: int | None = None
    weight: str | None = None
    questions_count: int | None = None


@dataclass(frozen=True, slots=True)
class TopicEntry:
    raw_label: str
    subject_label: str
    topic_id: int | None = None


@dataclass(frozen=True, slots=True)
class EventEntry:
    kind: str
    title: str
    date_start: date | None = None
    date_end: date | None = None
    evidence_level: str | None = None


@dataclass(frozen=True, slots=True)
class FactEntry:
    field_path: str
    label: str
    value: str
    evidence_level: str | None = None


@dataclass(frozen=True, slots=True)
class ProgrammeSnapshot:
    """O que uma análise de edital produziu, no formato que a comparação usa."""

    subjects: tuple[SubjectEntry, ...] = ()
    topics: tuple[TopicEntry, ...] = ()
    events: tuple[EventEntry, ...] = ()
    facts: tuple[FactEntry, ...] = ()


@dataclass(frozen=True, slots=True)
class Change:
    scope: str
    kind: str
    label: str
    #: O que havia e o que passou a haver. ``None`` de um lado é entrada ou saída.
    before: str | None = None
    after: str | None = None
    detail: str = ""
    topic_id: int | None = None
    subject_id: int | None = None
    #: Procedência do dado novo: OFFICIAL, CONFIRMED, INFERRED ou NOT_FOUND.
    evidence_level: str | None = None


@dataclass(frozen=True, slots=True)
class ContentRef:
    kind: str
    public_id: str
    title: str
    topic_id: int | None


@dataclass(frozen=True, slots=True)
class Impact:
    action: str
    topic_label: str
    topic_id: int | None
    reason: str
    content: ContentRef | None = None


@dataclass(frozen=True, slots=True)
class DiffSummary:
    added: int
    removed: int
    changed: int
    orphaned: int
    missing: int
    #: Quantas mudanças vieram de dado deduzido, e não conferido no documento.
    inferred: int


def _key(entry: SubjectEntry | TopicEntry) -> str:
    """Casa pelo vínculo com o catálogo; sem ele, pelo rótulo normalizado.

    O identificador canônico é mais confiável que o texto: o edital pode
    reescrever "Língua Portuguesa" como "Português" sem que nada tenha mudado
    de verdade.
    """
    if isinstance(entry, TopicEntry):
        if entry.topic_id is not None:
            return f"id:{entry.topic_id}"
        return f"txt:{normalize(entry.subject_label)}|{normalize(entry.raw_label)}"
    if entry.subject_id is not None:
        return f"id:{entry.subject_id}"
    return f"txt:{normalize(entry.raw_label)}"


def _peso(entry: SubjectEntry) -> str:
    partes = []
    if entry.weight is not None:
        partes.append(f"peso {entry.weight}")
    if entry.questions_count is not None:
        partes.append(f"{entry.questions_count} questões")
    return ", ".join(partes) or "sem peso declarado"


def _periodo(entry: EventEntry) -> str:
    if entry.date_start and entry.date_end and entry.date_end != entry.date_start:
        return f"{entry.date_start:%d/%m/%Y} a {entry.date_end:%d/%m/%Y}"
    if entry.date_start:
        return f"{entry.date_start:%d/%m/%Y}"
    return "sem data"


def diff_subjects(before: Sequence[SubjectEntry], after: Sequence[SubjectEntry]) -> list[Change]:
    antes = {_key(item): item for item in before}
    depois = {_key(item): item for item in after}
    mudancas: list[Change] = []

    for chave, item in depois.items():
        if chave not in antes:
            mudancas.append(
                Change(
                    scope=ChangeScope.SUBJECT,
                    kind=ChangeKind.ADDED,
                    label=item.raw_label,
                    after=_peso(item),
                    detail="Disciplina que o edital anterior não cobrava.",
                    subject_id=item.subject_id,
                )
            )
            continue
        anterior = antes[chave]
        if (anterior.weight, anterior.questions_count) != (item.weight, item.questions_count):
            mudancas.append(
                Change(
                    scope=ChangeScope.SUBJECT,
                    kind=ChangeKind.CHANGED,
                    label=item.raw_label,
                    before=_peso(anterior),
                    after=_peso(item),
                    detail="O peso da disciplina mudou — a distribuição do plano muda com ele.",
                    subject_id=item.subject_id,
                )
            )

    for chave, item in antes.items():
        if chave not in depois:
            mudancas.append(
                Change(
                    scope=ChangeScope.SUBJECT,
                    kind=ChangeKind.REMOVED,
                    label=item.raw_label,
                    before=_peso(item),
                    detail="Disciplina que saiu do edital.",
                    subject_id=item.subject_id,
                )
            )
    return mudancas


def diff_topics(before: Sequence[TopicEntry], after: Sequence[TopicEntry]) -> list[Change]:
    antes = {_key(item): item for item in before}
    depois = {_key(item): item for item in after}
    mudancas: list[Change] = []

    for chave, item in depois.items():
        if chave not in antes:
            mudancas.append(
                Change(
                    scope=ChangeScope.TOPIC,
                    kind=ChangeKind.ADDED,
                    label=item.raw_label,
                    after=item.subject_label,
                    detail="Tópico novo no conteúdo programático.",
                    topic_id=item.topic_id,
                )
            )

    for chave, item in antes.items():
        if chave not in depois:
            mudancas.append(
                Change(
                    scope=ChangeScope.TOPIC,
                    kind=ChangeKind.REMOVED,
                    label=item.raw_label,
                    before=item.subject_label,
                    detail="Tópico que saiu do conteúdo programático.",
                    topic_id=item.topic_id,
                )
            )
    return mudancas


def diff_events(before: Sequence[EventEntry], after: Sequence[EventEntry]) -> list[Change]:
    """Datas. É aqui que a retificação costuma doer mais no candidato."""
    antes = {(item.kind, normalize(item.title)): item for item in before}
    depois = {(item.kind, normalize(item.title)): item for item in after}
    mudancas: list[Change] = []

    for chave, item in depois.items():
        anterior = antes.get(chave)
        if anterior is None:
            mudancas.append(
                Change(
                    scope=ChangeScope.EVENT,
                    kind=ChangeKind.ADDED,
                    label=item.title,
                    after=_periodo(item),
                    detail="Data que o cronograma anterior não trazia.",
                    evidence_level=item.evidence_level,
                )
            )
            continue
        if (anterior.date_start, anterior.date_end) != (item.date_start, item.date_end):
            mudancas.append(
                Change(
                    scope=ChangeScope.EVENT,
                    kind=ChangeKind.CHANGED,
                    label=item.title,
                    before=_periodo(anterior),
                    after=_periodo(item),
                    detail="A data mudou.",
                    evidence_level=item.evidence_level,
                )
            )

    for chave, item in antes.items():
        if chave not in depois:
            mudancas.append(
                Change(
                    scope=ChangeScope.EVENT,
                    kind=ChangeKind.REMOVED,
                    label=item.title,
                    before=_periodo(item),
                    detail="Data que saiu do cronograma.",
                    evidence_level=item.evidence_level,
                )
            )
    return mudancas


def diff_facts(before: Sequence[FactEntry], after: Sequence[FactEntry]) -> list[Change]:
    antes = {item.field_path: item for item in before}
    depois = {item.field_path: item for item in after}
    mudancas: list[Change] = []

    for chave, item in depois.items():
        anterior = antes.get(chave)
        if anterior is None:
            mudancas.append(
                Change(
                    scope=ChangeScope.FACT,
                    kind=ChangeKind.ADDED,
                    label=item.label,
                    after=item.value,
                    detail="Dado que o edital anterior não trazia.",
                    evidence_level=item.evidence_level,
                )
            )
        elif anterior.value != item.value:
            mudancas.append(
                Change(
                    scope=ChangeScope.FACT,
                    kind=ChangeKind.CHANGED,
                    label=item.label,
                    before=anterior.value,
                    after=item.value,
                    detail="O valor mudou entre as duas versões.",
                    evidence_level=item.evidence_level,
                )
            )

    for chave, item in antes.items():
        if chave not in depois:
            mudancas.append(
                Change(
                    scope=ChangeScope.FACT,
                    kind=ChangeKind.REMOVED,
                    label=item.label,
                    before=item.value,
                    detail="Dado que saiu do edital.",
                    evidence_level=item.evidence_level,
                )
            )
    return mudancas


def diff(before: ProgrammeSnapshot, after: ProgrammeSnapshot) -> list[Change]:
    """A comparação inteira, na ordem em que uma pessoa lê o edital."""
    return [
        *diff_subjects(before.subjects, after.subjects),
        *diff_topics(before.topics, after.topics),
        *diff_events(before.events, after.events),
        *diff_facts(before.facts, after.facts),
    ]


def impacts(
    changes: Sequence[Change], content_by_topic: Mapping[int, Sequence[ContentRef]]
) -> list[Impact]:
    """O que as mudanças atingem no conteúdo que já existe.

    **Nada é apagado aqui, nem proposto para apagar.** Conteúdo de tópico que
    saiu do edital fica órfão, com o motivo escrito: um edital retificado pode
    ser retificado de novo, e quem decide o destino de uma aula é uma pessoa.
    """
    achados: list[Impact] = []
    for mudanca in changes:
        if mudanca.scope != ChangeScope.TOPIC:
            continue

        if mudanca.kind == ChangeKind.REMOVED:
            existentes = (
                content_by_topic.get(mudanca.topic_id, ()) if mudanca.topic_id is not None else ()
            )
            for item in existentes:
                achados.append(
                    Impact(
                        action=ImpactAction.ORPHANED,
                        topic_label=mudanca.label,
                        topic_id=mudanca.topic_id,
                        reason=(
                            "O edital não cobra mais este tópico. O conteúdo continua "
                            "no ar — quem decide o destino dele é uma pessoa."
                        ),
                        content=item,
                    )
                )
        elif mudanca.kind == ChangeKind.ADDED:
            existentes = (
                content_by_topic.get(mudanca.topic_id, ()) if mudanca.topic_id is not None else ()
            )
            if not existentes:
                achados.append(
                    Impact(
                        action=ImpactAction.MISSING,
                        topic_label=mudanca.label,
                        topic_id=mudanca.topic_id,
                        reason="Tópico novo sem conteúdo. Entra no próximo plano de geração.",
                    )
                )
    return achados


#: Níveis que querem dizer "conferido no documento".
_CONFERIDOS = frozenset({"OFFICIAL", "CONFIRMED"})


def summarize(changes: Sequence[Change], found: Sequence[Impact]) -> DiffSummary:
    """O resumo é derivado das mudanças, nunca acumulado."""
    return DiffSummary(
        added=sum(1 for item in changes if item.kind == ChangeKind.ADDED),
        removed=sum(1 for item in changes if item.kind == ChangeKind.REMOVED),
        changed=sum(1 for item in changes if item.kind == ChangeKind.CHANGED),
        orphaned=sum(1 for item in found if item.action == ImpactAction.ORPHANED),
        missing=sum(1 for item in found if item.action == ImpactAction.MISSING),
        inferred=sum(
            1
            for item in changes
            if item.evidence_level is not None and item.evidence_level not in _CONFERIDOS
        ),
    )
