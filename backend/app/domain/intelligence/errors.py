"""Caderno de Erros e Radar de Pegadinhas: o que os erros do candidato dizem.

Só entram na conta os erros com causa **confirmada** por quem errou. Sugestão de
IA não vira estatística — vira sugestão na tela, esperando confirmação.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Abaixo disso a plataforma não afirma que existe um padrão.
MIN_CAUSE_SAMPLE = 5
MIN_TRAP_SAMPLE = 3
MIN_SUBJECT_SAMPLE = 3

CAUSE_LABELS: dict[str, str] = {
    "UNKNOWN_CONTENT": "Não sabia o conteúdo",
    "INTERPRETATION": "Interpretei o enunciado errado",
    "CONFUSION": "Confundi com assunto parecido",
    "FORGETTING": "Sabia e esqueci",
    "RUSH": "Pressa ou desatenção",
    "TRAP": "Caí numa pegadinha",
    "ALTERNATIVE_DOUBT": "Fiquei entre duas alternativas",
}

# O que fazer diante de cada causa. Texto fixo, ligado à causa — não é geração.
CAUSE_ACTIONS: dict[str, str] = {
    "UNKNOWN_CONTENT": "Volte à teoria do assunto antes de resolver mais questões dele.",
    "INTERPRETATION": (
        "Treine leitura de comando: sublinhe o que é pedido antes de olhar as alternativas."
    ),
    "CONFUSION": "Estude os dois assuntos lado a lado e monte um quadro comparativo.",
    "FORGETTING": "Encurte o intervalo de revisão deste assunto.",
    "RUSH": "Reduza o ritmo nas questões deste tipo e confira o comando antes de marcar.",
    "TRAP": "Revise o padrão de pegadinha que apareceu e procure questões com a mesma armadilha.",
    "ALTERNATIVE_DOUBT": "Treine eliminação de alternativas e revise o detalhe que separa as duas.",
}


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    """Um erro já classificado e confirmado."""

    cause: str
    subject_id: int | None
    subject_name: str
    trap_slug: str | None = None
    trap_name: str | None = None
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class CauseSummary:
    cause: str
    label: str
    count: int
    share: float
    action: str


@dataclass(frozen=True, slots=True)
class TrapSummary:
    slug: str
    name: str
    count: int
    share: float


@dataclass(frozen=True, slots=True)
class SubjectErrorSummary:
    subject_id: int | None
    subject_name: str
    count: int
    dominant_cause: str | None
    dominant_cause_label: str | None


@dataclass(frozen=True, slots=True)
class ErrorNotebook:
    total: int
    resolved: int
    by_cause: list[CauseSummary] = field(default_factory=list)
    by_subject: list[SubjectErrorSummary] = field(default_factory=list)
    traps: list[TrapSummary] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)
    # Por que alguma seção veio vazia, quando for o caso.
    notes: list[str] = field(default_factory=list)


def _dominant(causes: list[str]) -> str | None:
    if not causes:
        return None
    counted = {cause: causes.count(cause) for cause in set(causes)}
    best = max(counted.values())
    winners = sorted(cause for cause, count in counted.items() if count == best)
    # Empate não tem dominante: dizer que tem seria escolher por conta própria.
    return winners[0] if len(winners) == 1 else None


def build_notebook(records: list[ErrorRecord]) -> ErrorNotebook:
    """Resume os erros confirmados em causas, disciplinas e pegadinhas."""
    total = len(records)
    if total == 0:
        return ErrorNotebook(
            total=0,
            resolved=0,
            notes=[
                "Nenhum erro classificado ainda. Classifique a causa dos seus erros "
                "para que o caderno mostre padrões."
            ],
        )

    notes: list[str] = []

    causes = [record.cause for record in records]
    by_cause = [
        CauseSummary(
            cause=cause,
            label=CAUSE_LABELS.get(cause, cause),
            count=causes.count(cause),
            share=round(causes.count(cause) / total, 4),
            action=CAUSE_ACTIONS.get(cause, ""),
        )
        for cause in sorted(set(causes))
    ]
    by_cause.sort(key=lambda item: (-item.count, item.label))

    grouped: dict[tuple[int | None, str], list[ErrorRecord]] = {}
    for record in records:
        grouped.setdefault((record.subject_id, record.subject_name), []).append(record)

    by_subject: list[SubjectErrorSummary] = []
    for (subject_id, subject_name), items in grouped.items():
        dominant = (
            _dominant([item.cause for item in items]) if len(items) >= MIN_SUBJECT_SAMPLE else None
        )
        by_subject.append(
            SubjectErrorSummary(
                subject_id=subject_id,
                subject_name=subject_name,
                count=len(items),
                dominant_cause=dominant,
                dominant_cause_label=CAUSE_LABELS.get(dominant, dominant) if dominant else None,
            )
        )
    by_subject.sort(key=lambda item: (-item.count, item.subject_name))

    trap_records = [record for record in records if record.trap_slug]
    traps: list[TrapSummary] = []
    if trap_records:
        slugs = [str(record.trap_slug) for record in trap_records]
        names = {
            str(record.trap_slug): record.trap_name or str(record.trap_slug)
            for record in trap_records
        }
        for slug in sorted(set(slugs)):
            count = slugs.count(slug)
            if count < MIN_TRAP_SAMPLE:
                continue
            traps.append(
                TrapSummary(
                    slug=slug,
                    name=names[slug],
                    count=count,
                    share=round(count / len(trap_records), 4),
                )
            )
        traps.sort(key=lambda item: (-item.count, item.name))
    if not traps:
        notes.append(
            f"O radar de pegadinhas aponta um padrão a partir de {MIN_TRAP_SAMPLE} "
            "erros marcados com a mesma armadilha."
        )

    insights: list[str] = []
    if total >= MIN_CAUSE_SAMPLE and by_cause:
        top = by_cause[0]
        insights.append(
            f"{top.count} dos seus {total} erros classificados são "
            f"“{top.label.lower()}”. {top.action}"
        )
    else:
        notes.append(
            f"Com {total} erro(s) classificado(s), ainda não há base para apontar uma causa "
            f"predominante — o mínimo é {MIN_CAUSE_SAMPLE}."
        )

    strongest = next(
        (item for item in by_subject if item.dominant_cause is not None),
        None,
    )
    if strongest is not None:
        insights.append(
            f"Em {strongest.subject_name}, {strongest.count} erro(s) e a causa mais frequente "
            f"é “{strongest.dominant_cause_label}”."
        )

    return ErrorNotebook(
        total=total,
        resolved=sum(1 for record in records if record.resolved),
        by_cause=by_cause,
        by_subject=by_subject,
        traps=traps,
        insights=insights,
        notes=notes,
    )
