"""Consultas de sessões (dispositivos conectados)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.user_session import UserSession
from app.repositories.base import BaseRepository, rowcount


class UserSessionRepository(BaseRepository[UserSession]):
    model = UserSession

    async def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        stmt = select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_public_id(self, public_id: str, user_id: int) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.public_id == public_id, UserSession.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active(self, user_id: int) -> Sequence[UserSession]:
        stmt = (
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > datetime.now(UTC),
            )
            .order_by(UserSession.last_used_at.desc().nullslast(), UserSession.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def revoke_family(self, family_id: str, reason: str) -> int:
        """Revoga toda a cadeia de refresh tokens (detecção de reuso)."""
        stmt = (
            update(UserSession)
            .where(UserSession.family_id == family_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
        )
        return rowcount(await self.session.execute(stmt))

    async def revoke_all_for_user(
        self, user_id: int, reason: str, *, except_session_id: int | None = None
    ) -> int:
        stmt = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC), revoked_reason=reason)
        )
        if except_session_id is not None:
            stmt = stmt.where(UserSession.id != except_session_id)
        return rowcount(await self.session.execute(stmt))
