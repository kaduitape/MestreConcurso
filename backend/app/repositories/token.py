"""Consultas de tokens de uso único."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.token import AuthToken
from app.repositories.base import BaseRepository, rowcount


class AuthTokenRepository(BaseRepository[AuthToken]):
    model = AuthToken

    async def get_valid(self, token_hash: str, token_type: str) -> AuthToken | None:
        stmt = select(AuthToken).where(
            AuthToken.token_hash == token_hash,
            AuthToken.type == token_type,
            AuthToken.used_at.is_(None),
            AuthToken.expires_at > datetime.now(UTC),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def invalidate_pending(self, user_id: int, token_type: str) -> int:
        """Invalida tokens anteriores do mesmo tipo — só o último vale."""
        stmt = (
            update(AuthToken)
            .where(
                AuthToken.user_id == user_id,
                AuthToken.type == token_type,
                AuthToken.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        return rowcount(await self.session.execute(stmt))
