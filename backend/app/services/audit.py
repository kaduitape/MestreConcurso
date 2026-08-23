"""Registro da trilha de auditoria."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger, request_id_ctx
from app.models.audit import AuditLog
from app.models.user import User

logger = get_logger(__name__)


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        action: str,
        *,
        actor: User | None = None,
        actor_email: str | None = None,
        actor_ip: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status: str = "SUCCESS",
        meta: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_email=actor_email or (actor.email if actor else None),
            actor_ip=actor_ip,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            meta=meta or {},
            request_id=request_id_ctx.get(),
        )
        self.session.add(entry)
        logger.info(
            "audit",
            action=action,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        return entry
