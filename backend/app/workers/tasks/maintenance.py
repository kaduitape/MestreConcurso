"""Tarefas de manutenção periódica."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import delete, update

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.models.token import AuthToken
from app.models.user_session import UserSession
from app.repositories.base import rowcount

logger = get_logger(__name__)


async def _purge_expired() -> dict[str, int]:
    now = datetime.now(UTC)
    factory = get_session_factory()
    async with factory() as session:
        tokens = await session.execute(delete(AuthToken).where(AuthToken.expires_at < now))
        sessions = await session.execute(
            update(UserSession)
            .where(UserSession.expires_at < now, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoked_reason="EXPIRED")
        )
        await session.commit()
        return {
            "tokens_removed": rowcount(tokens),
            "sessions_expired": rowcount(sessions),
        }


@shared_task(name="maintenance.purge_expired")
def purge_expired() -> dict[str, int]:
    """Remove tokens vencidos e marca sessões expiradas."""
    result = asyncio.run(_purge_expired())
    logger.info("maintenance.purge_expired", **result)
    return result
