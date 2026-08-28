"""Consultas do histórico de Mestre Score."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import select

from app.models.analytics import MasterScoreSnapshot
from app.repositories.base import BaseRepository


class MasterScoreRepository(BaseRepository[MasterScoreSnapshot]):
    model = MasterScoreSnapshot

    async def get_day(self, user_id: int, day: date) -> MasterScoreSnapshot | None:
        return await self.get_by(user_id=user_id, day=day)

    async def history(self, user_id: int, *, limit: int = 90) -> Sequence[MasterScoreSnapshot]:
        """Do mais recente para trás — quem chama ordena para exibir."""
        stmt = (
            select(MasterScoreSnapshot)
            .where(MasterScoreSnapshot.user_id == user_id)
            .order_by(MasterScoreSnapshot.day.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()
