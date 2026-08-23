"""Sessões de usuário — um refresh token rotativo por sessão/dispositivo."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import Sha256Hex

if TYPE_CHECKING:
    from app.models.user import User


class UserSession(IdMixin, PublicIdMixin, TimestampMixin, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="uq_user_sessions_refresh_token_hash"),
        Index("ix_user_sessions_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_user_sessions_family_id", "family_id"),
        Index("ix_user_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(Sha256Hex)
    family_id: Mapped[str] = mapped_column(String(26))
    device_label: Mapped[str | None] = mapped_column(String(120))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(60))

    user: Mapped[User] = relationship(back_populates="sessions")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None
