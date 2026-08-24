"""Mestre IA: conversas, mensagens com citação, vocabulário e vídeos verificados.

O que sustenta este módulo: **uma mensagem do Mestre guarda as afirmações e as
citações que as sustentam**, não apenas o texto. Assim qualquer resposta pode ser
auditada depois — e a interface consegue mostrar de onde cada frase veio, ou
dizer que uma frase ficou sem origem.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText

if TYPE_CHECKING:
    from app.models.catalog import Subject


class ChatMode(StrEnum):
    """Como o Mestre responde."""

    TUTOR = "TUTOR"  # objetivo, direto ao ponto
    TEACHER = "TEACHER"  # Modo Professor: conceito, exemplo, pegadinha, resumo


class MessageRole(StrEnum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"


class Conversation(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma conversa com o Mestre, ancorada no contexto do candidato."""

    __tablename__ = "chat_conversations"
    __table_args__ = (Index("ix_chat_conversations_user_activity", "user_id", "last_message_at"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    mode: Mapped[str] = mapped_column(String(20), default=ChatMode.TUTOR)
    notice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="SET NULL")
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.id",
    )


class Message(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma mensagem. Se veio do Mestre, carrega as afirmações e suas origens."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_conversation", "conversation_id", "id"),)

    conversation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("chat_conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(MediumText)

    # Cada item: texto, tipo, situação da origem, citação, trecho e página.
    claims: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    # Trechos que entraram no contexto — permite reabrir a origem depois.
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    # Dados que o Python calculou e injetou; o modelo não recalcula nada.
    computed_context: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    # Quando o Mestre se recusa a responder, o motivo fica registrado.
    is_refusal: Mapped[bool] = mapped_column(Boolean, default=False)
    refusal_reason: Mapped[str | None] = mapped_column(MediumText)
    # Fração das afirmações factuais com origem conferida (0..1).
    grounding_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    model_slug: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class VocabularyTerm(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Vocabulário inteligente: termos que o candidato guardou da conversa.

    A definição carrega a mesma marca de origem das respostas: veio de um trecho
    citado ou foi redigida pelo modelo. As duas coisas não se confundem na tela.
    """

    __tablename__ = "vocabulary_terms"
    __table_args__ = (
        UniqueConstraint("user_id", "term_key", name="uq_vocabulary_terms_user_term"),
        Index("ix_vocabulary_terms_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(160))
    # Forma normalizada, usada para não duplicar o mesmo termo.
    term_key: Mapped[str] = mapped_column(String(160))
    definition: Mapped[str] = mapped_column(MediumText)
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    message_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    source_quote: Mapped[str | None] = mapped_column(MediumText)
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_document: Mapped[str | None] = mapped_column(String(255))
    # CITED quando há trecho conferido; GENERATED quando é redação do modelo.
    origin: Mapped[str] = mapped_column(String(20), default="GENERATED")
    times_reviewed: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subject: Mapped[Subject | None] = relationship(lazy="selectin")


class VideoResource(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Vídeo de apoio, **conferido por uma pessoa** antes de ser recomendado.

    A plataforma não descobre vídeos sozinha nem inventa links: o Mestre só
    sugere o que está aqui, e cada item registra quem conferiu e quando.
    """

    __tablename__ = "video_resources"
    __table_args__ = (
        UniqueConstraint("url", name="uq_video_resources_url"),
        Index("ix_video_resources_subject", "subject_id", "is_active"),
    )

    title: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    provider: Mapped[str] = mapped_column(String(40), default="YOUTUBE")
    channel: Mapped[str | None] = mapped_column(String(160))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )
    summary: Mapped[str | None] = mapped_column(MediumText)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    verified_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subject: Mapped[Subject | None] = relationship(lazy="selectin")

    @property
    def is_verified(self) -> bool:
        return self.verified_at is not None
