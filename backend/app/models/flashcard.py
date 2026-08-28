"""Flashcards e o estado de memória de cada candidato.

Duas separações importantes:

* **cartão** e **estado de memória** são tabelas distintas. Um cartão global
  (curado pela equipe) é revisado por muita gente, e cada pessoa tem seu próprio
  intervalo — misturar as duas coisas impediria isso.
* **origem** é declarada. Cartão gerado por IA nasce marcado como tal, e quando
  vem de um trecho de edital carrega a citação: a interface nunca apresenta
  redação de modelo como se fosse texto oficial.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText

if TYPE_CHECKING:
    from app.models.catalog import Subject


class CardOrigin(StrEnum):
    """De onde o cartão veio. Governa o selo exibido na interface."""

    USER = "USER"  # escrito pelo candidato
    AI = "AI"  # gerado por modelo
    QUESTION = "QUESTION"  # nasceu de uma questão errada
    ERROR = "ERROR"  # nasceu de um erro do Caderno de Erros
    NOTICE = "NOTICE"  # nasceu de um trecho do edital
    EDITORIAL = "EDITORIAL"  # curadoria da equipe


class Flashcard(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma frente e um verso, com a procedência do conteúdo."""

    __tablename__ = "flashcards"
    __table_args__ = (
        Index("ix_flashcards_user_subject", "user_id", "subject_id"),
        Index("ix_flashcards_origin", "origin", "is_active"),
    )

    # Nulo significa cartão global, disponível para todos.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )

    front: Mapped[str] = mapped_column(MediumText)
    back: Mapped[str] = mapped_column(MediumText)
    hint: Mapped[str | None] = mapped_column(MediumText)
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    extra: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    origin: Mapped[str] = mapped_column(String(20), default=CardOrigin.USER)
    # Referência à origem concreta (questão, erro, edital) quando existir.
    source_ref: Mapped[str | None] = mapped_column(String(60))
    source_quote: Mapped[str | None] = mapped_column(MediumText)
    source_page: Mapped[int | None] = mapped_column(Integer)
    source_document: Mapped[str | None] = mapped_column(String(255))
    model_slug: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(20))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Impressão digital da frente normalizada — barra cartão repetido no mesmo baralho.
    checksum: Mapped[str] = mapped_column(String(64), index=True)

    subject: Mapped[Subject | None] = relationship(lazy="selectin")

    @property
    def is_generated(self) -> bool:
        return self.origin == CardOrigin.AI


class CardMemoryState(IdMixin, TimestampMixin, Base):
    """O estado de memória de um candidato sobre um cartão."""

    __tablename__ = "flashcard_states"
    __table_args__ = (
        UniqueConstraint("user_id", "flashcard_id", name="uq_flashcard_states_user_card"),
        Index("ix_flashcard_states_user_due", "user_id", "due_on"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    flashcard_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("flashcards.id", ondelete="CASCADE"), index=True
    )

    state: Mapped[str] = mapped_column(String(20), default="NEW")
    ease_factor: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("2.500"))
    interval_days: Mapped[int] = mapped_column(Integer, default=0)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    step_index: Mapped[int] = mapped_column(Integer, default=0)

    due_on: Mapped[date] = mapped_column(Date, index=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_rating: Mapped[str | None] = mapped_column(String(10))
    # Como o intervalo atual foi calculado — o "por quê?" da próxima revisão.
    last_breakdown: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # Quantas vezes a fila adiou este cartão por causa do teto diário.
    postponed_count: Mapped[int] = mapped_column(Integer, default=0)

    flashcard: Mapped[Flashcard] = relationship(lazy="selectin")


class FlashcardReview(IdMixin, TimestampMixin, Base):
    """O registro de cada revisão — a base de qualquer estatística de memória."""

    __tablename__ = "flashcard_reviews"
    __table_args__ = (
        Index("ix_flashcard_reviews_user_created", "user_id", "created_at"),
        Index("ix_flashcard_reviews_card", "flashcard_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    flashcard_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("flashcards.id", ondelete="CASCADE")
    )
    rating: Mapped[str] = mapped_column(String(10))
    time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    previous_interval_days: Mapped[int] = mapped_column(Integer, default=0)
    next_interval_days: Mapped[int] = mapped_column(Integer, default=0)
    ease_factor: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("2.500"))
    due_on: Mapped[date] = mapped_column(Date)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
