"""Base declarativa, mixins e convenções de nomes de constraints."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.ids import new_ulid
from app.db.types import BigIntPk, PublicId

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:  # pragma: no cover - conveniência de debug
        pk = getattr(self, "id", None)
        return f"<{type(self).__name__} id={pk}>"


def utcnow() -> datetime:
    return datetime.now(UTC)


class IdMixin:
    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True, autoincrement=True)


class PublicIdMixin:
    """Identificador exposto na API — nunca vazamos o id sequencial."""

    public_id: Mapped[str] = mapped_column(PublicId, unique=True, index=True, default=new_ulid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
