"""Usuário e perfil."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType
from app.models.rbac import user_roles

if TYPE_CHECKING:
    from app.models.rbac import Role
    from app.models.user_session import UserSession


class UserStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DELETED = "DELETED"


class User(IdMixin, PublicIdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_status_created_at", "status", "created_at"),
    )

    email: Mapped[str] = mapped_column(String(255), index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.PENDING, index=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    profile: Mapped[Profile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
        primaryjoin=lambda: User.id == user_roles.c.user_id,
        secondaryjoin="Role.id == user_roles.c.role_id",
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def permission_slugs(self) -> set[str]:
        """União das permissões de todos os papéis do usuário."""
        if self.is_superuser:
            return {"*"}
        slugs: set[str] = set()
        for role in self.roles:
            slugs |= role.permission_slugs
        return slugs

    def has_permission(self, permission: str) -> bool:
        slugs = self.permission_slugs
        if "*" in slugs or permission in slugs:
            return True
        resource = permission.split(":", 1)[0]
        return f"{resource}:*" in slugs


class Profile(IdMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(32))
    birth_date: Mapped[date | None] = mapped_column(Date)
    city: Mapped[str | None] = mapped_column(String(120))
    state: Mapped[str | None] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo")
    locale: Mapped[str] = mapped_column(String(10), default="pt-BR")
    theme: Mapped[str] = mapped_column(String(10), default="system")
    study_goal: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(String(500))
    preferences: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="profile")
