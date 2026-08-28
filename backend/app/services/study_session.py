"""Cronômetro de estudo: tempo real, com pausa, separado do tempo planejado."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.game import GameEvent, GameEventKind
from app.models.study import (
    StudySession,
    StudySessionStatus,
    StudyTask,
    StudyTaskKind,
    StudyTaskStatus,
    UserSubjectProgress,
)
from app.models.user import User
from app.repositories.study import (
    StudySessionRepository,
    StudyTaskRepository,
    UserSubjectProgressRepository,
)
from app.services.game_engine import GameEngine

logger = get_logger(__name__)

# Sessão sem interação por muito tempo não vira "8 horas de estudo".
MAX_SESSION_HOURS = 6


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class StudySessionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sessions = StudySessionRepository(session)
        self.tasks = StudyTaskRepository(session)
        self.progress = UserSubjectProgressRepository(session)

    async def current(self, user: User) -> StudySession | None:
        return await self.sessions.get_running(user.id)

    async def _reload(self, session_id: int) -> StudySession:
        """Releitura com a tarefa carregada: evita lazy load fora do contexto async."""
        stmt = (
            select(StudySession)
            .where(StudySession.id == session_id)
            .options(selectinload(StudySession.task))
            .execution_options(populate_existing=True)
        )
        record = (await self.session.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise NotFoundError("Sessão não encontrada.")
        return record

    async def start(self, user: User, *, task_public_id: str | None = None) -> StudySession:
        running = await self.sessions.get_running(user.id)
        if running is not None:
            raise ConflictError(
                "Já existe uma sessão em andamento. Finalize-a antes de começar outra.",
                code="session_already_running",
                details={"session_public_id": running.public_id},
            )

        task: StudyTask | None = None
        if task_public_id:
            task = await self.tasks.get_by_public_id(task_public_id, user.id)
            if task is None:
                raise NotFoundError("Tarefa não encontrada.")

        record = StudySession(
            user_id=user.id,
            study_task_id=task.id if task else None,
            subject_key=task.subject_key if task else None,
            subject_label=task.subject_label if task else None,
            kind=task.kind if task else StudyTaskKind.THEORY,
            status=StudySessionStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.session.add(record)
        await self.session.commit()
        logger.info("study_session.started", user=user.public_id, task=task_public_id)
        return await self._reload(record.id)

    async def pause(self, user: User, public_id: str) -> StudySession:
        record = await self._get(user, public_id)
        if record.status != StudySessionStatus.RUNNING:
            raise ConflictError("A sessão não está em andamento.", code="session_not_running")

        now = datetime.now(UTC)
        record.focus_seconds += self._elapsed_since(record, now)
        record.paused_at = now
        record.status = StudySessionStatus.PAUSED
        await self.session.commit()
        return await self._reload(record.id)

    async def resume(self, user: User, public_id: str) -> StudySession:
        record = await self._get(user, public_id)
        if record.status != StudySessionStatus.PAUSED:
            raise ConflictError("A sessão não está pausada.", code="session_not_paused")

        now = datetime.now(UTC)
        if record.paused_at:
            record.pause_seconds += int((now - _aware(record.paused_at)).total_seconds())
        record.paused_at = None
        record.status = StudySessionStatus.RUNNING
        # A retomada reinicia a contagem do trecho corrente.
        record.started_at = now
        await self.session.commit()
        return await self._reload(record.id)

    async def finish(self, user: User, public_id: str, *, notes: str | None = None) -> StudySession:
        record = await self._get(user, public_id)
        if record.status == StudySessionStatus.FINISHED:
            return record

        now = datetime.now(UTC)
        if record.status == StudySessionStatus.RUNNING:
            record.focus_seconds += self._elapsed_since(record, now)
        record.status = StudySessionStatus.FINISHED
        record.ended_at = now
        record.notes = notes
        record.focus_seconds = min(record.focus_seconds, MAX_SESSION_HOURS * 3600)

        minutes = record.focus_seconds // 60
        if record.study_task_id:
            task = await self.session.get(StudyTask, record.study_task_id)
            if task is not None:
                task.actual_minutes += minutes
                # Cumprido o tempo planejado, a tarefa é dada como concluída.
                if task.status == StudyTaskStatus.PENDING and (
                    task.actual_minutes >= task.planned_minutes
                ):
                    task.status = StudyTaskStatus.DONE
                    task.completed_at = now
                await self._add_progress(task, minutes)

        await self.session.commit()

        # A gamificação é notificada do fato consumado; a regra de pontuação
        # vive no motor, não aqui.
        await GameEngine(self.session).award(
            user,
            GameEvent(
                GameEventKind.STUDY_SESSION,
                {"focus_minutes": float(minutes)},
                reference=record.public_id,
            ),
        )
        await GameEngine(self.session).touch_day(user, minutes=minutes)

        logger.info(
            "study_session.finished",
            user=user.public_id,
            minutes=minutes,
            task=record.study_task_id,
        )
        return await self._reload(record.id)

    async def abandon(self, user: User, public_id: str) -> StudySession:
        record = await self._get(user, public_id)
        record.status = StudySessionStatus.ABANDONED
        record.ended_at = datetime.now(UTC)
        await self.session.commit()
        return record

    def _elapsed_since(self, record: StudySession, now: datetime) -> int:
        elapsed = int((now - _aware(record.started_at)).total_seconds())
        return max(0, min(elapsed, MAX_SESSION_HOURS * 3600))

    async def _get(self, user: User, public_id: str) -> StudySession:
        record = await self.sessions.get_by_public_id(public_id, user.id)
        if record is None:
            raise NotFoundError("Sessão não encontrada.")
        return record

    async def _add_progress(self, task: StudyTask, minutes: int) -> None:
        if not task.subject_key or minutes <= 0:
            return
        row = await self.progress.get_for_subject(task.user_id, task.subject_key)
        if row is None:
            row = UserSubjectProgress(
                user_id=task.user_id,
                subject_key=task.subject_key,
                subject_label=task.subject_label or task.subject_key,
                color_token=task.color_token,
                planned_minutes=0,
                studied_minutes=0,
                tasks_done=0,
                tasks_skipped=0,
                completion=Decimal("0"),
            )
            self.session.add(row)
            await self.session.flush()

        row.studied_minutes += minutes
        row.last_studied_at = datetime.now(UTC)
        row.completion = (
            Decimal(str(round(min(1.0, row.studied_minutes / row.planned_minutes), 4)))
            if row.planned_minutes
            else Decimal("0")
        )
