"""Consultas da camada de inteligência."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from app.models.intelligence import (
    BoardProfileMetric,
    ErrorAnalysis,
    TopicIncidence,
    TrapPattern,
    UserPriority,
)
from app.models.question import Question, QuestionAttempt
from app.repositories.base import BaseRepository


class TopicIncidenceRepository(BaseRepository[TopicIncidence]):
    model = TopicIncidence

    async def for_board(
        self, exam_board_id: int, *, subject_id: int | None = None
    ) -> Sequence[TopicIncidence]:
        stmt = (
            select(TopicIncidence)
            .where(TopicIncidence.exam_board_id == exam_board_id)
            .order_by(TopicIncidence.incidence_pct.desc(), TopicIncidence.subject_name)
        )
        if subject_id is not None:
            stmt = stmt.where(TopicIncidence.subject_id == subject_id)
        return (await self.session.execute(stmt)).scalars().all()

    async def by_subject(self, exam_board_id: int) -> dict[int, TopicIncidence]:
        """Incidência por disciplina (recorte sem assunto), pronta para o Priority Score."""
        rows = await self.for_board(exam_board_id)
        return {row.subject_id: row for row in rows if row.topic_id is None}


class BoardProfileMetricRepository(BaseRepository[BoardProfileMetric]):
    model = BoardProfileMetric

    async def for_board(self, exam_board_id: int) -> Sequence[BoardProfileMetric]:
        stmt = (
            select(BoardProfileMetric)
            .where(BoardProfileMetric.exam_board_id == exam_board_id)
            .order_by(BoardProfileMetric.metric_slug)
        )
        return (await self.session.execute(stmt)).scalars().all()


class TrapPatternRepository(BaseRepository[TrapPattern]):
    model = TrapPattern

    async def get_by_public_id(self, public_id: str) -> TrapPattern | None:
        return await self.get_by(public_id=public_id)

    async def get_by_slug(self, slug: str) -> TrapPattern | None:
        return await self.get_by(slug=slug)

    async def active(self) -> Sequence[TrapPattern]:
        stmt = (
            select(TrapPattern)
            .where(TrapPattern.is_active.is_(True))
            .order_by(TrapPattern.category, TrapPattern.name)
        )
        return (await self.session.execute(stmt)).scalars().all()


class ErrorAnalysisRepository(BaseRepository[ErrorAnalysis]):
    model = ErrorAnalysis

    def _base(self) -> Select[tuple[ErrorAnalysis]]:
        return select(ErrorAnalysis).options(
            selectinload(ErrorAnalysis.trap_pattern),
            selectinload(ErrorAnalysis.attempt).selectinload(QuestionAttempt.question),
        )

    async def get_by_public_id(self, public_id: str, user_id: int) -> ErrorAnalysis | None:
        stmt = (
            self._base()
            .where(ErrorAnalysis.public_id == public_id, ErrorAnalysis.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_for_attempt(self, attempt_id: int) -> ErrorAnalysis | None:
        stmt = self._base().where(ErrorAnalysis.question_attempt_id == attempt_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int,
        cause: str | None = None,
        subject_id: int | None = None,
        only_confirmed: bool = False,
        only_pending: bool = False,
    ) -> tuple[Sequence[ErrorAnalysis], int]:
        stmt = (
            self._base()
            .where(ErrorAnalysis.user_id == user_id)
            .order_by(ErrorAnalysis.created_at.desc())
        )
        if cause:
            stmt = stmt.where(ErrorAnalysis.cause == cause)
        if subject_id is not None:
            stmt = stmt.where(ErrorAnalysis.subject_id == subject_id)
        if only_confirmed:
            stmt = stmt.where(ErrorAnalysis.confirmed_at.is_not(None))
        if only_pending:
            stmt = stmt.where(ErrorAnalysis.confirmed_at.is_(None))
        return await self.paginate(stmt, limit=limit, offset=offset)

    async def confirmed_for_user(self, user_id: int) -> Sequence[ErrorAnalysis]:
        """Base de toda estatística do caderno: só o que a pessoa confirmou."""
        stmt = (
            self._base()
            .where(ErrorAnalysis.user_id == user_id, ErrorAnalysis.confirmed_at.is_not(None))
            .order_by(ErrorAnalysis.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def unclassified_attempts(
        self, user_id: int, *, limit: int = 50
    ) -> Sequence[QuestionAttempt]:
        """Erros ainda sem causa registrada — a fila do caderno."""
        classified = select(ErrorAnalysis.question_attempt_id).where(
            ErrorAnalysis.user_id == user_id
        )
        stmt = (
            select(QuestionAttempt)
            .options(selectinload(QuestionAttempt.question).selectinload(Question.subject))
            .where(
                QuestionAttempt.user_id == user_id,
                QuestionAttempt.is_correct.is_(False),
                QuestionAttempt.id.notin_(classified),
            )
            .order_by(QuestionAttempt.created_at.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class UserPriorityRepository(BaseRepository[UserPriority]):
    model = UserPriority

    async def for_user(self, user_id: int, *, limit: int = 50) -> Sequence[UserPriority]:
        stmt = (
            select(UserPriority)
            .where(UserPriority.user_id == user_id)
            .order_by(UserPriority.score.desc(), UserPriority.label)
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def scores_by_scope(self, user_id: int) -> dict[str, int]:
        stmt = select(UserPriority.scope_key, UserPriority.score).where(
            UserPriority.user_id == user_id
        )
        return {str(row[0]): int(row[1]) for row in (await self.session.execute(stmt)).all()}
