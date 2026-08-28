"""Documentos processados e seus trechos (chunks) com proveniência.

Todo chunk guarda página e deslocamento de caracteres: sem isso não é possível
provar de onde veio uma informação, e a plataforma não exibe fato sem prova.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

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


class DocumentKind(StrEnum):
    NOTICE = "NOTICE"
    LEGISLATION = "LEGISLATION"
    USER_MATERIAL = "USER_MATERIAL"


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    CHUNKED = "CHUNKED"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class ExtractionMethod(StrEnum):
    TEXT_LAYER = "TEXT_LAYER"
    OCR = "OCR"
    MIXED = "MIXED"


class Document(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Texto extraído de um arquivo, pronto para busca e análise."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("checksum_sha256", "kind", name="uq_documents_checksum_kind"),
        Index("ix_documents_owner", "owner_type", "owner_id"),
        Index("ix_documents_status", "status"),
    )

    kind: Mapped[str] = mapped_column(String(30), default=DocumentKind.NOTICE)
    owner_type: Mapped[str] = mapped_column(String(30))
    owner_id: Mapped[int] = mapped_column(BigInteger)
    # tenant "global" para conteúdo público; "user:<id>" isola material do aluno.
    tenant: Mapped[str] = mapped_column(String(40), default="global", index=True)

    checksum_sha256: Mapped[str] = mapped_column(Sha256Hex, index=True)
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING)
    extraction_method: Mapped[str | None] = mapped_column(String(20))
    page_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int | None] = mapped_column(Integer)
    text_coverage: Mapped[float | None] = mapped_column()
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(String(500))
    meta: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", lazy="noload"
    )


class DocumentChunk(IdMixin, TimestampMixin, Base):
    """Trecho indexável. A fonte de verdade do texto é o MySQL; o Qdrant guarda vetores."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
        Index("ix_document_chunks_document_page", "document_id", "page_number"),
        Index("ix_document_chunks_vector_id", "vector_id"),
    )

    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(MediumText)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    heading_path: Mapped[str | None] = mapped_column(String(500))
    section_kind: Mapped[str | None] = mapped_column(String(40))
    vector_id: Mapped[str | None] = mapped_column(String(36))
    embedding_model: Mapped[str | None] = mapped_column(String(120))

    document: Mapped[Document] = relationship(back_populates="chunks")
