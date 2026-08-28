"""Recálculo do mapa de incidência e do DNA da banca.

Tudo aqui é contagem sobre o banco de questões, feita em Python. O resultado é
gravado com a amostra e a data do cálculo, para que qualquer tela consiga dizer
"este número vem de N questões entre X e Y" — e para que nenhum número apareça
sem essa origem.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.domain.intelligence import (
    ProfileSample,
    QuestionSample,
    build_board_profile,
    compute_incidence,
)
from app.models.catalog import ExamBoard
from app.models.intelligence import BoardProfileMetric, TopicIncidence
from app.models.question import Question, QuestionStatus
from app.repositories.intelligence import (
    BoardProfileMetricRepository,
    TopicIncidenceRepository,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RecomputeResult:
    board_slug: str
    questions_sampled: int
    incidence_rows: int
    profile_metrics: int
    # Motivo quando nada pôde ser calculado — a interface mostra isso, não um vazio.
    incidence_blocked: str | None = None
    profile_blocked: str | None = None


class IntelligenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.incidence = TopicIncidenceRepository(session)
        self.profile = BoardProfileMetricRepository(session)

    async def _board(self, slug: str) -> ExamBoard:
        board = (
            await self.session.execute(select(ExamBoard).where(ExamBoard.slug == slug))
        ).scalar_one_or_none()
        if board is None:
            raise NotFoundError("Banca não encontrada.")
        return board

    async def _questions(self, exam_board_id: int) -> list[Question]:
        stmt = (
            select(Question)
            .options(selectinload(Question.subject), selectinload(Question.alternatives))
            .where(
                Question.exam_board_id == exam_board_id,
                Question.status == QuestionStatus.PUBLISHED,
                Question.subject_id.is_not(None),
            )
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def recompute_board(self, slug: str) -> RecomputeResult:
        """Refaz incidência e perfil de uma banca a partir das questões publicadas."""
        board = await self._board(slug)
        questions = await self._questions(board.id)
        now = datetime.now(UTC)

        report = compute_incidence(
            [
                QuestionSample(
                    subject_id=int(question.subject_id or 0),
                    subject_name=question.subject.name if question.subject else "Sem disciplina",
                    topic_id=question.topic_id,
                    year=question.year,
                    exam_id=question.exam_id,
                )
                for question in questions
            ]
        )

        await self.session.execute(
            delete(TopicIncidence).where(TopicIncidence.exam_board_id == board.id)
        )
        stored_rows = 0
        for row in report.rows:
            # Recorte sem amostra não é gravado: publicá-lo seria publicar um número frágil.
            if not row.is_sufficient:
                continue
            scope = f"banca:{board.id}|disciplina:{row.subject_id}|assunto:{row.topic_id or 0}"
            period = f"{report.period_start_year or 0}-{report.period_end_year or 0}"
            self.session.add(
                TopicIncidence(
                    scope_key=f"{scope}|{period}",
                    exam_board_id=board.id,
                    subject_id=row.subject_id,
                    topic_id=row.topic_id,
                    subject_name=row.subject_name,
                    topic_name=row.topic_name,
                    period_start_year=report.period_start_year or 0,
                    period_end_year=report.period_end_year or 0,
                    exams_count=row.exams_count,
                    questions_count=row.questions_count,
                    board_questions_count=row.board_questions_count,
                    incidence_pct=Decimal(str(row.incidence_pct)),
                    trend=None if row.trend is None else Decimal(str(row.trend)),
                    confidence=Decimal(str(row.confidence)),
                    computed_at=now,
                )
            )
            stored_rows += 1

        profile = build_board_profile(
            [
                ProfileSample(
                    subject_id=question.subject_id,
                    subject_name=question.subject.name if question.subject else "Sem disciplina",
                    difficulty=question.difficulty,
                    kind=question.kind,
                    alternatives_count=len(question.alternatives),
                    year=question.year,
                    exam_id=question.exam_id,
                )
                for question in questions
            ]
        )

        await self.session.execute(
            delete(BoardProfileMetric).where(BoardProfileMetric.exam_board_id == board.id)
        )
        for metric in profile.metrics:
            self.session.add(
                BoardProfileMetric(
                    scope_key=f"banca:{board.id}|{metric.slug}",
                    exam_board_id=board.id,
                    metric_slug=metric.slug,
                    label=metric.label,
                    value=Decimal(str(metric.value)),
                    unit=metric.unit,
                    detail=metric.detail,
                    sample_exams=metric.sample_exams,
                    sample_questions=metric.sample_questions,
                    period_start_year=profile.period_start_year,
                    period_end_year=profile.period_end_year,
                    confidence=Decimal(str(round(min(1.0, metric.sample_questions / 200), 3))),
                    computed_at=now,
                )
            )

        await self.session.commit()
        logger.info(
            "intelligence.recomputed",
            board=slug,
            questions=len(questions),
            rows=stored_rows,
            metrics=len(profile.metrics),
        )
        return RecomputeResult(
            board_slug=slug,
            questions_sampled=len(questions),
            incidence_rows=stored_rows,
            profile_metrics=len(profile.metrics),
            incidence_blocked=report.blocked_reason,
            profile_blocked=profile.blocked_reason,
        )

    async def recompute_all(self) -> list[RecomputeResult]:
        slugs = list(
            (await self.session.execute(select(ExamBoard.slug).order_by(ExamBoard.slug)))
            .scalars()
            .all()
        )
        return [await self.recompute_board(slug) for slug in slugs]
