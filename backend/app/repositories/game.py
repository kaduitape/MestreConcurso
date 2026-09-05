"""Consultas da gamificação."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.models.game import (
    Achievement,
    BattleLoadout,
    BattlePowerUse,
    BattleRunLoadout,
    BattleSetting,
    Duel,
    EventParticipation,
    GameRule,
    GameRun,
    GamificationProfile,
    Mission,
    MissionStatus,
    RankSnapshot,
    Season,
    SeasonParticipation,
    ShareCardRecord,
    SpecialEvent,
    StreakDay,
    UserAchievement,
    WarCampaign,
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


class RankSnapshotRepository(BaseRepository[RankSnapshot]):
    model = RankSnapshot

    async def get_day(self, user_id: int, day: date) -> RankSnapshot | None:
        return await self.get_by(user_id=user_id, day=day)

    async def history(self, user_id: int, *, limit: int = 90) -> Sequence[RankSnapshot]:
        """Do mais recente para trás — quem chama ordena para exibir."""
        stmt = (
            select(RankSnapshot)
            .where(RankSnapshot.user_id == user_id)
            .order_by(RankSnapshot.day.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class SeasonRepository(BaseRepository[Season]):
    model = Season

    async def get_by_slug(self, slug: str) -> Season | None:
        return await self.get_by(slug=slug)

    async def active_on(self, day: date) -> Season | None:
        """A temporada vigente naquele dia. Janelas não se sobrepõem por convenção."""
        stmt = (
            select(Season)
            .where(
                Season.is_active.is_(True),
                Season.starts_on <= day,
                Season.ends_on >= day,
            )
            .order_by(Season.starts_on.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def recent(self, *, limit: int = 12) -> Sequence[Season]:
        stmt = select(Season).order_by(Season.starts_on.desc()).limit(limit)
        return (await self.session.execute(stmt)).scalars().all()


class SeasonParticipationRepository(BaseRepository[SeasonParticipation]):
    model = SeasonParticipation

    async def get_for(self, season_id: int, user_id: int) -> SeasonParticipation | None:
        return await self.get_by(season_id=season_id, user_id=user_id)

    async def history_for(self, user_id: int, *, limit: int = 12) -> Sequence[SeasonParticipation]:
        stmt = (
            select(SeasonParticipation)
            .where(SeasonParticipation.user_id == user_id)
            .order_by(SeasonParticipation.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class GameRunRepository(BaseRepository[GameRun]):
    model = GameRun

    async def get_by_public_id(self, public_id: str, user_id: int) -> GameRun | None:
        return await self.get_by(public_id=public_id, user_id=user_id)

    async def running_for(self, user_id: int) -> GameRun | None:
        """No máximo uma rodada aberta por vez: duas seriam dois placares."""
        stmt = (
            select(GameRun)
            .where(GameRun.user_id == user_id, GameRun.status == "RUNNING")
            .order_by(GameRun.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def history(self, user_id: int, *, limit: int = 20) -> Sequence[GameRun]:
        stmt = (
            select(GameRun)
            .where(GameRun.user_id == user_id, GameRun.status != "RUNNING")
            .order_by(GameRun.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def finished_today(self, user_id: int, day: date) -> int:
        stmt = select(func.count()).where(
            GameRun.user_id == user_id,
            GameRun.status == "FINISHED",
            func.date(GameRun.ended_at) == day,
        )
        return int((await self.session.execute(stmt)).scalar_one())


class DuelRepository(BaseRepository[Duel]):
    model = Duel

    async def get_by_code(self, code: str) -> Duel | None:
        return await self.get_by(code=code)

    async def get_by_public_id(self, public_id: str) -> Duel | None:
        return await self.get_by(public_id=public_id)

    async def for_user(self, user_id: int, *, limit: int = 20) -> Sequence[Duel]:
        stmt = (
            select(Duel)
            .where(or_(Duel.challenger_id == user_id, Duel.opponent_id == user_id))
            .order_by(Duel.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class SpecialEventRepository(BaseRepository[SpecialEvent]):
    model = SpecialEvent

    async def get_by_slug(self, slug: str) -> SpecialEvent | None:
        return await self.get_by(slug=slug)

    async def open_on(self, day: date) -> Sequence[SpecialEvent]:
        """Eventos podem coexistir — ao contrário das temporadas."""
        stmt = (
            select(SpecialEvent)
            .where(
                SpecialEvent.is_active.is_(True),
                SpecialEvent.starts_on <= day,
                SpecialEvent.ends_on >= day,
            )
            .order_by(SpecialEvent.ends_on)
        )
        return (await self.session.execute(stmt)).scalars().all()


class EventParticipationRepository(BaseRepository[EventParticipation]):
    model = EventParticipation

    async def get_for(self, event_id: int, user_id: int) -> EventParticipation | None:
        return await self.get_by(event_id=event_id, user_id=user_id)


class WarCampaignRepository(BaseRepository[WarCampaign]):
    model = WarCampaign

    async def running_for(self, user_id: int) -> WarCampaign | None:
        stmt = (
            select(WarCampaign)
            .where(WarCampaign.user_id == user_id, WarCampaign.status == "RUNNING")
            .order_by(WarCampaign.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def history_for(self, user_id: int, *, limit: int = 10) -> Sequence[WarCampaign]:
        stmt = (
            select(WarCampaign)
            .where(WarCampaign.user_id == user_id)
            .order_by(WarCampaign.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class ShareCardRepository(BaseRepository[ShareCardRecord]):
    model = ShareCardRecord

    async def get_by_token(self, token: str) -> ShareCardRecord | None:
        return await self.get_by(token=token)

    async def for_user(self, user_id: int, *, limit: int = 20) -> Sequence[ShareCardRecord]:
        stmt = (
            select(ShareCardRecord)
            .where(ShareCardRecord.user_id == user_id)
            .order_by(ShareCardRecord.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class BattleSettingRepository(BaseRepository[BattleSetting]):
    model = BattleSetting

    async def all_settings(self) -> Sequence[BattleSetting]:
        stmt = select(BattleSetting).order_by(BattleSetting.key)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_key(self, key: str) -> BattleSetting | None:
        return await self.get_by(key=key)

    async def get_fresh(self, key: str) -> BattleSetting | None:
        """Releitura após gravar — evita ``MissingGreenlet`` em ``updated_at``."""
        stmt = (
            select(BattleSetting)
            .where(BattleSetting.key == key)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalars().first()


class BattlePowerUseRepository(BaseRepository[BattlePowerUse]):
    model = BattlePowerUse

    async def for_run(self, run_id: int) -> Sequence[BattlePowerUse]:
        stmt = (
            select(BattlePowerUse)
            .where(BattlePowerUse.game_run_id == run_id)
            .order_by(BattlePowerUse.id)
        )
        return (await self.session.execute(stmt)).scalars().all()


class BattleLoadoutRepository(BaseRepository[BattleLoadout]):
    model = BattleLoadout

    async def for_user(self, user_id: int) -> BattleLoadout | None:
        return await self.get_by(user_id=user_id)


class BattleRunLoadoutRepository(BaseRepository[BattleRunLoadout]):
    model = BattleRunLoadout

    async def for_run(self, run_id: int) -> BattleRunLoadout | None:
        return await self.get_by(game_run_id=run_id)
