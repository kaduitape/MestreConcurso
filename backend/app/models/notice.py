"""Editais e seus arquivos.

Na Fase 2 o edital é cadastrado e o PDF é armazenado com validação de conteúdo.
A extração com IA (Fase 3) consome estes registros — por isso o arquivo já nasce
com checksum, para nunca reprocessar (e repagar) o mesmo documento.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText, Sha256Hex

if TYPE_CHECKING:
    from app.models.catalog import Competition


class NoticeKind(StrEnum):
    MAIN = "MAIN"
    RECTIFICATION = "RECTIFICATION"
    ADDENDUM = "ADDENDUM"
    RESULT = "RESULT"


class NoticeStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class NoticeFileStatus(StrEnum):
    STORED = "STORED"
    QUEUED = "QUEUED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class Notice(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Documento oficial de um concurso."""

    __tablename__ = "notices"
    __table_args__ = (
        Index("ix_notices_competition_id_kind", "competition_id", "kind"),
        Index("ix_notices_status", "status"),
    )

    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20), default=NoticeKind.MAIN)
    number: Mapped[str | None] = mapped_column(String(60))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default=NoticeStatus.DRAFT)
    summary: Mapped[str | None] = mapped_column(MediumText)
    extra: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    competition: Mapped[Competition | None] = relationship(
        back_populates="notices", lazy="selectin"
    )
    files: Mapped[list[NoticeFile]] = relationship(
        back_populates="notice", cascade="all, delete-orphan", lazy="selectin"
    )


class NoticeFile(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Arquivo PDF de um edital, guardado fora da árvore pública."""

    __tablename__ = "notice_files"
    __table_args__ = (
        UniqueConstraint("notice_id", "checksum_sha256", name="uq_notice_files_notice_checksum"),
        Index("ix_notice_files_status", "status"),
    )

    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    uploaded_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(String(255))
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(Sha256Hex, index=True)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=NoticeFileStatus.STORED)
    error_message: Mapped[str | None] = mapped_column(String(500))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notice: Mapped[Notice] = relationship(back_populates="files")
