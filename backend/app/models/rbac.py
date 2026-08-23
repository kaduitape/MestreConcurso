"""Papéis e permissões (RBAC por permissão, não por nome de papel)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        BigInteger,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", BigInteger, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("granted_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("granted_by_user_id", BigInteger, ForeignKey("users.id", ondelete="SET NULL")),
)


class Permission(IdMixin, TimestampMixin, Base):
    """Permissão atômica no formato ``recurso:acao`` (ex.: ``users:read``)."""

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("slug", name="uq_permissions_slug"),)

    slug: Mapped[str] = mapped_column(String(80), index=True)
    resource: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(255), default="")

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions, back_populates="permissions", lazy="selectin"
    )


class Role(IdMixin, TimestampMixin, Base):
    """Agrupamento nomeado de permissões."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("slug", name="uq_roles_slug"),)

    slug: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(255), default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )
    users: Mapped[list[User]] = relationship(
        secondary=user_roles,
        back_populates="roles",
        lazy="noload",
        # user_roles tem duas FKs para users (user_id e granted_by_user_id):
        # o par de joins precisa ser explícito.
        primaryjoin=lambda: Role.id == user_roles.c.role_id,
        secondaryjoin="User.id == user_roles.c.user_id",
    )

    @property
    def permission_slugs(self) -> set[str]:
        return {permission.slug for permission in self.permissions}
