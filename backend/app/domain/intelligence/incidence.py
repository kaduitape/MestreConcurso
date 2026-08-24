"""Mapa de incidência: quanto cada disciplina/assunto aparece nas provas da banca.

Conta pura sobre o banco de questões. Se a amostra não chega ao mínimo, a função
devolve o recorte marcado como **insuficiente** em vez de um percentual — e quem
chama é obrigado a lidar com isso.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Amostras mínimas para publicar um percentual.
MIN_BOARD_QUESTIONS = 30
MIN_SCOPE_QUESTIONS = 5


@dataclass(frozen=True, slots=True)
class QuestionSample:
    """Uma questão da amostra, reduzida ao que a incidência precisa."""

    subject_id: int
    subject_name: str
    topic_id: int | None = None
    topic_name: str | None = None
    year: int | None = None
    exam_id: int | None = None


@dataclass(frozen=True, slots=True)
class IncidenceRow:
    subject_id: int
    subject_name: str
    topic_id: int | None
    topic_name: str | None
    questions_count: int
    exams_count: int
    board_questions_count: int
    incidence_pct: float
    trend: float | None
    confidence: float
    is_sufficient: bool
    insufficient_reason: str | None = None


@dataclass(frozen=True, slots=True)
class IncidenceReport:
    period_start_year: int | None
    period_end_year: int | None
    board_questions_count: int
    exams_count: int
    rows: list[IncidenceRow] = field(default_factory=list)
    # Motivo pelo qual o mapa inteiro não pôde ser publicado, quando for o caso.
    blocked_reason: str | None = None


def _confidence(questions: int) -> float:
    """Cresce com a amostra e satura em 1 — nunca afirma certeza que não tem."""
    if questions <= 0:
        return 0.0
    return round(min(1.0, questions / 200), 3)


def _trend(years: list[int], all_years: list[int]) -> float | None:
    """Diferença entre a fatia na metade recente e na metade antiga do período.

    Sem dois anos distintos na amostra, não existe tendência — devolve ``None``
    em vez de zero, que seria lido como "estável".
    """
    distinct = sorted(set(all_years))
    if len(distinct) < 2 or not years:
        return None
    middle = distinct[len(distinct) // 2]
    recent_total = sum(1 for year in all_years if year >= middle)
    older_total = len(all_years) - recent_total
    if recent_total == 0 or older_total == 0:
        return None
    recent = sum(1 for year in years if year >= middle) / recent_total
    older = sum(1 for year in years if year < middle) / older_total
    return round(recent - older, 4)


def compute_incidence(
    questions: list[QuestionSample], *, by_topic: bool = False
) -> IncidenceReport:
    """Monta o mapa de incidência a partir das questões da banca."""
    years = [item.year for item in questions if item.year is not None]
    period_start = min(years) if years else None
    period_end = max(years) if years else None
    exams = {item.exam_id for item in questions if item.exam_id is not None}
    total = len(questions)

    if total < MIN_BOARD_QUESTIONS:
        return IncidenceReport(
            period_start_year=period_start,
            period_end_year=period_end,
            board_questions_count=total,
            exams_count=len(exams),
            rows=[],
            blocked_reason=(
                f"Amostra insuficiente: {total} questão(ões) desta banca no banco, "
                f"mínimo de {MIN_BOARD_QUESTIONS} para calcular incidência."
            ),
        )

    grouped: dict[tuple[int, int | None], list[QuestionSample]] = {}
    for item in questions:
        key = (item.subject_id, item.topic_id if by_topic else None)
        grouped.setdefault(key, []).append(item)

    rows: list[IncidenceRow] = []
    for (subject_id, topic_id), items in grouped.items():
        count = len(items)
        scope_years = [item.year for item in items if item.year is not None]
        sufficient = count >= MIN_SCOPE_QUESTIONS
        rows.append(
            IncidenceRow(
                subject_id=subject_id,
                subject_name=items[0].subject_name,
                topic_id=topic_id,
                topic_name=items[0].topic_name if topic_id is not None else None,
                questions_count=count,
                exams_count=len({item.exam_id for item in items if item.exam_id is not None}),
                board_questions_count=total,
                incidence_pct=round(count / total, 4),
                trend=_trend(scope_years, years) if sufficient else None,
                confidence=_confidence(count),
                is_sufficient=sufficient,
                insufficient_reason=(
                    None
                    if sufficient
                    else (
                        f"{count} questão(ões) na amostra; "
                        f"mínimo de {MIN_SCOPE_QUESTIONS} para publicar o percentual."
                    )
                ),
            )
        )

    rows.sort(key=lambda row: (-row.questions_count, row.subject_name))
    return IncidenceReport(
        period_start_year=period_start,
        period_end_year=period_end,
        board_questions_count=total,
        exams_count=len(exams),
        rows=rows,
    )
