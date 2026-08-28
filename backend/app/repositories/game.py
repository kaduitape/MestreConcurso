"""Consultas da gamificação."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.game import (
    Achievement,
    GameRule,
    GamificationProfile,
    Mission,
    MissionStatus,
    StreakDay,
    UserAchievement,
    XPTransaction,
)
from app.repositories.base import BaseRepository


class GameRuleRepository(BaseRepository[GameRule]):
    model = GameRule

    async def get_by_key(self, key: str) -> GameRule | None:
        return await self.get_by(key=key)

    async def all_rules(self) -> Sequence[GameRule]:
        stmt = select(GameRule).order_by(GameRule.key).execution_options(populate_existing=True)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_fresh(self, key: str) -> GameRule | None:
        """Releitura explícita: a linha recém-semeada ainda não tem os timestamps."""
        stmt = select(GameRule).where(GameRule.key == key).execution_options(populate_existing=True)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class ProfileRepository(BaseRepository[GamificationProfile]):
    model = GamificationProfile

    async def for_user(self, user_id: int) -> GamificationProfile | None:
        return await self.get_by(user_id=user_id)


class XPTransactionRepository(BaseRepository[XPTransaction]):
    model = XPTransaction

    async def earned_today(self, user_id: int, event_kind: str, day: date) -> int:
        stmt = select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
            XPTransaction.user_id == user_id,
            XPTransaction.event_kind == event_kind,
            XPTransaction.day == day,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def total_for(self, user_id: int) -> int:
        """O saldo verdadeiro: a soma do razão."""
        stmt = select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
            XPTransaction.user_id == user_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def day_total(self, user_id: int, day: date) -> int:
        stmt = select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
            XPTransaction.user_id == user_id, XPTransaction.day == day
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def exists_for(self, user_id: int, event_kind: str, reference: str) -> bool:
        stmt = select(XPTransaction.id).where(
            XPTransaction.user_id == user_id,
            XPTransaction.event_kind == event_kind,
            XPTransaction.reference == reference,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def history(
        self, user_id: int, *, limit: int, offset: int
    ) -> tuple[Sequence[XPTransaction], int]:
        stmt = (
            select(XPTransaction)
            .where(XPTransaction.user_id == user_id)
            .order_by(XPTransaction.created_at.desc(), XPTransaction.id.desc())
        )
        return await self.paginate(stmt, limit=limit, offset=offset)


class MissionRepository(BaseRepository[Mission]):
    model = Mission

    async def get_by_public_id(self, public_id: str, user_id: int) -> Mission | None:
        stmt = (
            select(Mission)
            .where(Mission.public_id == public_id, Mission.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def for_day(self, user_id: int, day: date) -> Sequence[Mission]:
        stmt = (
            select(Mission)
            .where(Mission.user_id == user_id, Mission.valid_from == day)
            .order_by(Mission.priority, Mission.id)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def completed_count(self, user_id: int) -> int:
        stmt = select(func.count()).where(
            Mission.user_id == user_id,
            Mission.status.in_([MissionStatus.DONE, MissionStatus.CLAIMED]),
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def expire_old(self, user_id: int, day: date) -> int:
        """Missão vencida não acumula: expira em vez de virar fila de dívida."""
        stmt = select(Mission).where(
            Mission.user_id == user_id,
            Mission.valid_until < day,
            Mission.status == MissionStatus.PENDING,
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        for row in rows:
            row.status = MissionStatus.EXPIRED
        return len(rows)


class AchievementRepository(BaseRepository[Achievement]):
    model = Achievement

    async def all_active(self) -> Sequence[Achievement]:
        stmt = (
            select(Achievement)
            .where(Achievement.is_active.is_(True))
            .order_by(Achievement.category, Achievement.slug)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_slug(self, slug: str) -> Achievement | None:
        return await self.get_by(slug=slug)

    async def unlocked_for(self, user_id: int) -> Sequence[UserAchievement]:
        stmt = (
            select(UserAchievement)
            .options(selectinload(UserAchievement.achievement))
            .where(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.unlocked_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()


class StreakRepository(BaseRepository[StreakDay]):
    model = StreakDay

    async def get_day(self, user_id: int, day: date) -> StreakDay | None:
        return await self.get_by(user_id=user_id, day=day)

    async def recent(self, user_id: int, *, limit: int = 120) -> Sequence[StreakDay]:
        stmt = (
            select(StreakDay)
            .where(StreakDay.user_id == user_id)
            .order_by(StreakDay.day.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()
