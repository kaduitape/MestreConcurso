"""Consultas do plano de estudo."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.study import (
    StudyPlan,
    StudyPlanStatus,
    StudySession,
    StudySessionStatus,
    StudyTask,
    StudyTaskStatus,
    UserSubjectProgress,
)
from app.repositories.base import BaseRepository


class StudyPlanRepository(BaseRepository[StudyPlan]):
    model = StudyPlan

    async def get_active(self, user_id: int) -> StudyPlan | None:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.user_id == user_id, StudyPlan.status == StudyPlanStatus.ACTIVE)
            .options(selectinload(StudyPlan.availability))
            .order_by(StudyPlan.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_public_id(self, public_id: str, user_id: int) -> StudyPlan | None:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.public_id == public_id, StudyPlan.user_id == user_id)
            .options(selectinload(StudyPlan.availability))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class StudyTaskRepository(BaseRepository[StudyTask]):
    model = StudyTask

    async def for_day(self, user_id: int, day: date) -> Sequence[StudyTask]:
        stmt = (
            select(StudyTask)
            .where(StudyTask.user_id == user_id, StudyTask.scheduled_for == day)
            .order_by(StudyTask.order_index, StudyTask.id)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def for_range(self, user_id: int, start: date, end: date) -> Sequence[StudyTask]:
        stmt = (
            select(StudyTask)
            .where(
                StudyTask.user_id == user_id,
                StudyTask.scheduled_for >= start,
                StudyTask.scheduled_for <= end,
            )
            .order_by(StudyTask.scheduled_for, StudyTask.order_index)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def overdue(self, user_id: int, today: date) -> Sequence[StudyTask]:
        """Tarefas de dias passados que continuam pendentes."""
        stmt = (
            select(StudyTask)
            .where(
                StudyTask.user_id == user_id,
                StudyTask.scheduled_for < today,
                StudyTask.status == StudyTaskStatus.PENDING,
            )
            .order_by(StudyTask.scheduled_for, StudyTask.order_index)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_public_id(self, public_id: str, user_id: int) -> StudyTask | None:
        stmt = select(StudyTask).where(
            StudyTask.public_id == public_id, StudyTask.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def committed_minutes(self, plan_id: int, start: date, end: date) -> dict[date, int]:
        """Minutos já agendados por dia — base para não estourar a capacidade."""
        stmt = (
            select(StudyTask.scheduled_for, func.sum(StudyTask.planned_minutes))
            .where(
                StudyTask.study_plan_id == plan_id,
                StudyTask.scheduled_for >= start,
                StudyTask.scheduled_for <= end,
                StudyTask.status.in_([StudyTaskStatus.PENDING, StudyTaskStatus.DONE]),
            )
            .group_by(StudyTask.scheduled_for)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: int(row[1] or 0) for row in rows}

    async def count_by_status(self, plan_id: int) -> dict[str, int]:
        stmt = (
            select(StudyTask.status, func.count())
            .where(StudyTask.study_plan_id == plan_id)
            .group_by(StudyTask.status)
        )
        rows = (await self.session.execute(stmt)).all()
        return {str(row[0]): int(row[1]) for row in rows}


class StudySessionRepository(BaseRepository[StudySession]):
    model = StudySession

    async def get_running(self, user_id: int) -> StudySession | None:
        stmt = (
            select(StudySession)
            .where(
                StudySession.user_id == user_id,
                StudySession.status.in_([StudySessionStatus.RUNNING, StudySessionStatus.PAUSED]),
            )
            .order_by(StudySession.started_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_public_id(self, public_id: str, user_id: int) -> StudySession | None:
        stmt = select(StudySession).where(
            StudySession.public_id == public_id, StudySession.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def minutes_between(self, user_id: int, start: date, end: date) -> int:
        stmt = select(func.coalesce(func.sum(StudySession.focus_seconds), 0)).where(
            StudySession.user_id == user_id,
            StudySession.started_at >= start,
            StudySession.started_at <= end,
        )
        seconds = int((await self.session.execute(stmt)).scalar_one())
        return seconds // 60


class UserSubjectProgressRepository(BaseRepository[UserSubjectProgress]):
    model = UserSubjectProgress

    async def get_for_subject(self, user_id: int, subject_key: str) -> UserSubjectProgress | None:
        return await self.get_by(user_id=user_id, subject_key=subject_key)

    async def list_for_user(self, user_id: int) -> Sequence[UserSubjectProgress]:
        stmt = (
            select(UserSubjectProgress)
            .where(UserSubjectProgress.user_id == user_id)
            .order_by(UserSubjectProgress.completion, UserSubjectProgress.subject_label)
        )
        return (await self.session.execute(stmt)).scalars().all()
