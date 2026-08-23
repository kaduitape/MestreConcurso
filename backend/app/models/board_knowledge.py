"""Conhecimento acumulado sobre cada banca.

Regra de custo: tudo o que for apurado sobre uma banca — por cálculo estatístico
ou por interpretação de IA — é gravado aqui com origem, amostra e validade. As
telas leem desta tabela; a IA só é acionada quando não existe registro válido.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class KnowledgeSource(StrEnum):
    """De onde veio o dado — nunca misturamos cálculo com interpretação."""

    COMPUTED = "COMPUTED"  # estatística calculada em Python sobre dados reais
    AI = "AI"  # interpretação gerada por LLM
    EDITORIAL = "EDITORIAL"  # curadoria humana
    OFFICIAL = "OFFICIAL"  # extraído de documento oficial


class BoardKnowledgeKind(StrEnum):
    PROFILE_SUMMARY = "PROFILE_SUMMARY"
    STYLE_TRAIT = "STYLE_TRAIT"
    TRAP_PATTERN = "TRAP_PATTERN"
    SUBJECT_FOCUS = "SUBJECT_FOCUS"
    QUESTION_FORMAT = "QUESTION_FORMAT"
    STUDY_TIP = "STUDY_TIP"


class BoardKnowledgeEntry(IdMixin, TimestampMixin, Base):
    """Um fato apurado sobre a banca, reaproveitável indefinidamente."""

    __tablename__ = "board_knowledge_entries"
    __table_args__ = (
        UniqueConstraint(
            "exam_board_id", "kind", "entry_key", name="uq_board_knowledge_entries_board_kind_key"
        ),
        Index("ix_board_knowledge_entries_board_kind", "exam_board_id", "kind"),
        Index("ix_board_knowledge_entries_expires_at", "expires_at"),
    )

    exam_board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exam_boards.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(40))
    entry_key: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(MediumText)
    data: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    source: Mapped[str] = mapped_column(String(20), default=KnowledgeSource.COMPUTED)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    sample_exams: Mapped[int | None] = mapped_column(Integer)
    sample_questions: Mapped[int | None] = mapped_column(Integer)
    period_start_year: Mapped[int | None] = mapped_column(Integer)
    period_end_year: Mapped[int | None] = mapped_column(Integer)

    provider_slug: Mapped[str | None] = mapped_column(String(40))
    model_slug: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_expired(self) -> bool:
        from datetime import UTC

        if self.expires_at is None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires <= datetime.now(UTC)
