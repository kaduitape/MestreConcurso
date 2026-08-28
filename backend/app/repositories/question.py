"""Consultas do banco de questões e dos simulados."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Integer, Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.question import (
    Alternative,
    Exam,
    Question,
    QuestionAttempt,
    QuestionStats,
    QuestionStatus,
    Simulation,
    SimulationAttempt,
    SimulationAttemptStatus,
    SimulationQuestion,
)
from app.repositories.base import BaseRepository


class ExamRepository(BaseRepository[Exam]):
    model = Exam

    async def get_by_public_id(self, public_id: str) -> Exam | None:
        return await self.get_by(public_id=public_id)

    async def search(
        self, *, limit: int, offset: int, board_slug: str | None = None, year: int | None = None
    ) -> tuple[Sequence[Exam], int]:
        stmt = select(Exam).order_by(Exam.year.desc(), Exam.name)
        if year:
            stmt = stmt.where(Exam.year == year)
        if board_slug:
            from app.models.catalog import ExamBoard

            stmt = stmt.join(Exam.exam_board).where(ExamBoard.slug == board_slug)
        return await self.paginate(stmt, limit=limit, offset=offset)


class QuestionRepository(BaseRepository[Question]):
    model = Question

    def _base(self) -> Select[tuple[Question]]:
        return select(Question).options(
            selectinload(Question.alternatives),
            selectinload(Question.subject),
            selectinload(Question.stats),
        )

    async def get_by_public_id(self, public_id: str) -> Question | None:
        # ``populate_existing`` recarrega os relacionamentos após uma alteração
        # na mesma sessão (troca de disciplina, por exemplo).
        stmt = (
            self._base()
            .where(Question.public_id == public_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_checksum(self, checksum: str) -> Question | None:
        return await self.get_by(checksum=checksum)

    async def list_by_ids(self, ids: Sequence[int]) -> Sequence[Question]:
        if not ids:
            return []
        stmt = self._base().where(Question.id.in_(ids))
        return (await self.session.execute(stmt)).scalars().all()

    def filtered(
        self,
        *,
        search: str | None = None,
        subject_id: int | None = None,
        topic_id: int | None = None,
        board_slug: str | None = None,
        year: int | None = None,
        difficulty: str | None = None,
        origin: str | None = None,
        status: str | None = QuestionStatus.PUBLISHED,
    ) -> Select[tuple[Question]]:
        stmt = self._base().order_by(Question.id.desc())
        if search:
            stmt = stmt.where(Question.statement.like(f"%{search.strip()}%"))
        if subject_id:
            stmt = stmt.where(Question.subject_id == subject_id)
        if topic_id:
            stmt = stmt.where(Question.topic_id == topic_id)
        if year:
            stmt = stmt.where(Question.year == year)
        if difficulty:
            stmt = stmt.where(Question.difficulty == difficulty)
        if origin:
            stmt = stmt.where(Question.origin == origin)
        if status:
            stmt = stmt.where(Question.status == status)
        if board_slug:
            from app.models.catalog import ExamBoard

            stmt = stmt.join(ExamBoard, Question.exam_board_id == ExamBoard.id).where(
                ExamBoard.slug == board_slug
            )
        return stmt

    async def search(
        self, *, limit: int, offset: int, **filters: object
    ) -> tuple[Sequence[Question], int]:
        stmt = self.filtered(**filters)  # type: ignore[arg-type]
        return await self.paginate(stmt, limit=limit, offset=offset)

    async def get_full(self, question_id: int) -> Question | None:
        """Questão com alternativas já carregadas — usado pelas rodadas de desafio."""
        stmt = self._base().where(Question.id == question_id)
        return (await self.session.execute(stmt)).scalars().first()

    async def pick_for_simulation(
        self,
        *,
        limit: int,
        subject_id: int | None = None,
        difficulty: str | None = None,
        board_slug: str | None = None,
        exclude_ids: Sequence[int] = (),
        only_ids: Sequence[int] | None = None,
    ) -> Sequence[Question]:
        """Seleciona questões publicadas para compor um simulado."""
        stmt = self.filtered(
            subject_id=subject_id,
            difficulty=difficulty,
            board_slug=board_slug,
            status=QuestionStatus.PUBLISHED,
        )
        if exclude_ids:
            stmt = stmt.where(Question.id.notin_(exclude_ids))
        if only_ids is not None:
            if not only_ids:
                return []
            stmt = stmt.where(Question.id.in_(only_ids))
        # Ordem estável e reproduzível: id decrescente (mais recentes primeiro).
        stmt = stmt.limit(limit)
        return (await self.session.execute(stmt)).scalars().all()


class QuestionStatsRepository(BaseRepository[QuestionStats]):
    model = QuestionStats

    async def get_for_question(self, question_id: int) -> QuestionStats | None:
        return await self.get_by(question_id=question_id)


class QuestionAttemptRepository(BaseRepository[QuestionAttempt]):
    model = QuestionAttempt

    async def list_for_user(
        self, user_id: int, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[QuestionAttempt], int]:
        stmt = (
            select(QuestionAttempt)
            .where(QuestionAttempt.user_id == user_id)
            .options(selectinload(QuestionAttempt.question))
            .order_by(QuestionAttempt.created_at.desc())
        )
        return await self.paginate(stmt, limit=limit, offset=offset)

    async def wrong_question_ids(self, user_id: int, *, limit: int = 200) -> list[int]:
        """Questões que o candidato errou e ainda não acertou depois."""
        latest = (
            select(
                QuestionAttempt.question_id,
                func.max(QuestionAttempt.id).label("last_id"),
            )
            .where(QuestionAttempt.user_id == user_id)
            .group_by(QuestionAttempt.question_id)
            .subquery()
        )
        # Errar e deixar em branco contam igual aqui: as duas deixam a questão pendente.
        stmt = (
            select(QuestionAttempt.question_id)
            .join(latest, QuestionAttempt.id == latest.c.last_id)
            .where(QuestionAttempt.is_correct.is_(False))
            .limit(limit)
        )
        return [int(row[0]) for row in (await self.session.execute(stmt)).all()]

    async def answered_question_ids(self, user_id: int) -> list[int]:
        stmt = select(QuestionAttempt.question_id).where(QuestionAttempt.user_id == user_id)
        return [int(row[0]) for row in (await self.session.execute(stmt)).all()]

    async def accuracy_since(self, user_id: int, since: datetime | None = None) -> float | None:
        correct_sum = func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0)
        stmt = select(func.count(QuestionAttempt.id), correct_sum).where(
            QuestionAttempt.user_id == user_id, QuestionAttempt.is_blank.is_(False)
        )
        if since:
            stmt = stmt.where(QuestionAttempt.created_at >= since)
        total, correct = (await self.session.execute(stmt)).one()
        if not total:
            return None
        return round(int(correct) / int(total), 4)


class SimulationRepository(BaseRepository[Simulation]):
    model = Simulation

    async def get_by_public_id(
        self, public_id: str, user_id: int | None = None
    ) -> Simulation | None:
        stmt = (
            select(Simulation)
            .where(Simulation.public_id == public_id)
            .options(selectinload(Simulation.questions).selectinload(SimulationQuestion.question))
        )
        if user_id is not None:
            stmt = stmt.where(or_(Simulation.user_id == user_id, Simulation.user_id.is_(None)))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[Sequence[Simulation], int]:
        stmt = (
            select(Simulation)
            .where(Simulation.user_id == user_id)
            .order_by(Simulation.created_at.desc())
        )
        return await self.paginate(stmt, limit=limit, offset=offset)


class SimulationAttemptRepository(BaseRepository[SimulationAttempt]):
    model = SimulationAttempt

    async def get_by_public_id(self, public_id: str, user_id: int) -> SimulationAttempt | None:
        stmt = (
            select(SimulationAttempt)
            .where(
                SimulationAttempt.public_id == public_id,
                SimulationAttempt.user_id == user_id,
            )
            .options(
                selectinload(SimulationAttempt.simulation)
                .selectinload(Simulation.questions)
                .selectinload(SimulationQuestion.question)
                .selectinload(Question.alternatives)
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_running(self, user_id: int) -> SimulationAttempt | None:
        stmt = (
            select(SimulationAttempt)
            .where(
                SimulationAttempt.user_id == user_id,
                SimulationAttempt.status.in_(
                    [SimulationAttemptStatus.IN_PROGRESS, SimulationAttemptStatus.PAUSED]
                ),
            )
            .order_by(SimulationAttempt.started_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_finished(self, user_id: int, *, limit: int = 20) -> Sequence[SimulationAttempt]:
        stmt = (
            select(SimulationAttempt)
            .where(
                SimulationAttempt.user_id == user_id,
                SimulationAttempt.status == SimulationAttemptStatus.FINISHED,
            )
            .options(selectinload(SimulationAttempt.simulation))
            .order_by(SimulationAttempt.finished_at.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class AlternativeRepository(BaseRepository[Alternative]):
    model = Alternative
