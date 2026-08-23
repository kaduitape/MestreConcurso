"""Consultas da trilha de auditoria."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from app.models.audit import AuditLog, ConsentLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def search(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        actor_user_id: int | None = None,
        since: datetime | None = None,
    ) -> tuple[Sequence[AuditLog], int]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_user_id:
            stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
        if since:
            stmt = stmt.where(AuditLog.created_at >= since)
        return await self.paginate(stmt, limit=limit, offset=offset)


class ConsentLogRepository(BaseRepository[ConsentLog]):
    model = ConsentLog

    async def list_for_user(self, user_id: int) -> Sequence[ConsentLog]:
        stmt = (
            select(ConsentLog)
            .where(ConsentLog.user_id == user_id)
            .order_by(ConsentLog.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()
