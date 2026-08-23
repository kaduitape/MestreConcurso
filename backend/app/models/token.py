"""Tokens de uso único: verificação de e-mail e recuperação de senha."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import Sha256Hex


class AuthTokenType(StrEnum):
    EMAIL_VERIFY = "EMAIL_VERIFY"
    PASSWORD_RESET = "PASSWORD_RESET"


class AuthToken(IdMixin, TimestampMixin, Base):
    __tablename__ = "auth_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
        Index("ix_auth_tokens_user_id_type", "user_id", "type"),
        Index("ix_auth_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[str] = mapped_column(Sha256Hex)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_ip: Mapped[str | None] = mapped_column(String(45))
