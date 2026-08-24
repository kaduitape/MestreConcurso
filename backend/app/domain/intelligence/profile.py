"""DNA da Banca: o retrato da banca que sai da contagem, não da opinião.

São métricas calculadas sobre as questões cadastradas daquela banca. Cada uma
carrega a amostra que a sustenta; abaixo do mínimo, a métrica não é produzida.
A leitura qualitativa da banca (estilo, dicas) vive em ``board_knowledge`` e é
marcada como interpretação de IA — as duas coisas nunca se misturam na tela.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MIN_PROFILE_QUESTIONS = 30

DIFFICULTY_LABELS: dict[str, str] = {
    "EASY": "fáceis",
    "MEDIUM": "médias",
    "HARD": "difíceis",
}

KIND_LABELS: dict[str, str] = {
    "MULTIPLE_CHOICE": "múltipla escolha",
    "TRUE_FALSE": "certo/errado",
    "DISCURSIVE": "discursivas",
}


@dataclass(frozen=True, slots=True)
class ProfileSample:
    subject_id: int | None
    subject_name: str
    difficulty: str
    kind: str
    alternatives_count: int
    year: int | None = None
    exam_id: int | None = None


@dataclass(frozen=True, slots=True)
class BoardMetric:
    slug: str
    label: str
    value: float
    unit: str
    detail: dict[str, float] = field(default_factory=dict)
    sample_questions: int = 0
    sample_exams: int = 0


@dataclass(frozen=True, slots=True)
class BoardProfile:
    period_start_year: int | None
    period_end_year: int | None
    sample_questions: int
    sample_exams: int
    metrics: list[BoardMetric] = field(default_factory=list)
    blocked_reason: str | None = None


def _distribution(values: list[str]) -> dict[str, float]:
    total = len(values)
    if total == 0:
        return {}
    return {value: round(values.count(value) / total, 4) for value in sorted(set(values))}


def build_board_profile(questions: list[ProfileSample]) -> BoardProfile:
    """Produz as métricas do DNA da banca a partir das questões cadastradas."""
    years = [item.year for item in questions if item.year is not None]
    exams = {item.exam_id for item in questions if item.exam_id is not None}
    total = len(questions)
    period = (min(years) if years else None, max(years) if years else None)

    if total < MIN_PROFILE_QUESTIONS:
        return BoardProfile(
            period_start_year=period[0],
            period_end_year=period[1],
            sample_questions=total,
            sample_exams=len(exams),
            blocked_reason=(
                f"Amostra insuficiente: {total} questão(ões) desta banca no banco, "
                f"mínimo de {MIN_PROFILE_QUESTIONS} para traçar o perfil."
            ),
        )

    difficulty = _distribution([item.difficulty for item in questions])
    kinds = _distribution([item.kind for item in questions])
    with_alternatives = [item.alternatives_count for item in questions if item.alternatives_count]
    subjects = _distribution([item.subject_name for item in questions])

    metrics = [
        BoardMetric(
            slug="difficulty_mix",
            label="Distribuição por dificuldade",
            value=difficulty.get("HARD", 0.0),
            unit="PERCENT",
            detail=difficulty,
            sample_questions=total,
            sample_exams=len(exams),
        ),
        BoardMetric(
            slug="question_kind_mix",
            label="Formato das questões",
            value=max(kinds.values()) if kinds else 0.0,
            unit="PERCENT",
            detail=kinds,
            sample_questions=total,
            sample_exams=len(exams),
        ),
        BoardMetric(
            slug="subject_focus",
            label="Disciplinas mais cobradas",
            value=max(subjects.values()) if subjects else 0.0,
            unit="PERCENT",
            detail=dict(sorted(subjects.items(), key=lambda item: -item[1])[:8]),
            sample_questions=total,
            sample_exams=len(exams),
        ),
    ]

    if with_alternatives:
        metrics.append(
            BoardMetric(
                slug="average_alternatives",
                label="Alternativas por questão",
                value=round(sum(with_alternatives) / len(with_alternatives), 3),
                unit="COUNT",
                detail={},
                sample_questions=len(with_alternatives),
                sample_exams=len(exams),
            )
        )

    return BoardProfile(
        period_start_year=period[0],
        period_end_year=period[1],
        sample_questions=total,
        sample_exams=len(exams),
        metrics=metrics,
    )
