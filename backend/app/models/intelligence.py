"""Camada de inteligência: incidência, DNA da banca, prioridade e erros.

Regra que atravessa este módulo: **todo número guardado aqui é calculado em Python
sobre dados reais e carrega o tamanho da amostra que o sustenta**. Sem amostra, a
linha não é gravada — a interface exibe "dados insuficientes" em vez de um
percentual que não se defende. A IA entra apenas para *interpretar* (sugerir a
causa de um erro), e a sugestão só vira registro depois de confirmada por quem
errou.
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
    from app.models.question import QuestionAttempt


# Abaixo destes tamanhos, a estatística não é publicada.
MIN_INCIDENCE_QUESTIONS = 30  # questões da banca no período
MIN_SUBJECT_QUESTIONS = 5  # questões da disciplina dentro da amostra
MIN_ERROR_SAMPLE = 5  # erros classificados para o radar apontar um padrão


class ErrorCause(StrEnum):
    """Por que a questão foi errada. Taxonomia fechada: vira estatística."""

    UNKNOWN_CONTENT = "UNKNOWN_CONTENT"  # não sabia o conteúdo
    INTERPRETATION = "INTERPRETATION"  # entendeu o enunciado errado
    CONFUSION = "CONFUSION"  # confundiu com assunto parecido
    FORGETTING = "FORGETTING"  # sabia e esqueceu
    RUSH = "RUSH"  # pressa / desatenção
    TRAP = "TRAP"  # caiu numa pegadinha da banca
    ALTERNATIVE_DOUBT = "ALTERNATIVE_DOUBT"  # ficou entre duas alternativas


class AnalysisSource(StrEnum):
    USER = "USER"
    AI = "AI"


class TopicIncidence(IdMixin, TimestampMixin, Base):
    """Quanto uma disciplina/assunto aparece nas provas de uma banca.

    O percentual é a fatia das questões da banca no período; ``exams_count`` e
    ``questions_count`` são a amostra que o sustenta, e viajam junto com o número
    em toda tela que o exibe.
    """

    __tablename__ = "topic_incidence"
    __table_args__ = (
        UniqueConstraint("scope_key", name="uq_topic_incidence_scope_key"),
        Index("ix_topic_incidence_board_subject", "exam_board_id", "subject_id"),
    )

    # Identidade estável do recorte: "banca:12|disciplina:3|assunto:9|2019-2024".
    scope_key: Mapped[str] = mapped_column(String(160))
    exam_board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exam_boards.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="CASCADE")
    )
    subject_name: Mapped[str] = mapped_column(String(200))
    topic_name: Mapped[str | None] = mapped_column(String(200))

    period_start_year: Mapped[int] = mapped_column(Integer)
    period_end_year: Mapped[int] = mapped_column(Integer)
    exams_count: Mapped[int] = mapped_column(Integer, default=0)
    questions_count: Mapped[int] = mapped_column(Integer, default=0)
    board_questions_count: Mapped[int] = mapped_column(Integer, default=0)

    incidence_pct: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    # Variação entre a metade recente e a metade antiga do período (pontos percentuais).
    trend: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BoardProfileMetric(IdMixin, TimestampMixin, Base):
    """Uma métrica do "DNA da banca", apurada sobre o banco de questões."""

    __tablename__ = "board_profile_metrics"
    __table_args__ = (
        UniqueConstraint("scope_key", name="uq_board_profile_metrics_scope_key"),
        Index("ix_board_profile_metrics_board", "exam_board_id", "metric_slug"),
    )

    scope_key: Mapped[str] = mapped_column(String(160))
    exam_board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("exam_boards.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    metric_slug: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(20), default="PERCENT")
    detail: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    sample_exams: Mapped[int] = mapped_column(Integer, default=0)
    sample_questions: Mapped[int] = mapped_column(Integer, default=0)
    period_start_year: Mapped[int | None] = mapped_column(Integer)
    period_end_year: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0"))
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrapPattern(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Padrão de pegadinha — categoria de técnica de prova, curada por pessoas.

    Não é afirmação sobre uma banca específica: é o nome do erro em que o
    candidato caiu. Quantas vezes ele caiu ali é conta feita sobre os erros dele.
    """

    __tablename__ = "trap_patterns"
    __table_args__ = (UniqueConstraint("slug", name="uq_trap_patterns_slug"),)

    slug: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(60), default="GERAL")
    description: Mapped[str | None] = mapped_column(MediumText)
    detection_hint: Mapped[str | None] = mapped_column(MediumText)
    example: Mapped[str | None] = mapped_column(MediumText)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ErrorAnalysis(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """A causa de um erro específico, no Caderno de Erros do candidato.

    Sugestão de IA entra com ``source=AI`` e ``confirmed_at`` nulo: ela aparece
    como sugestão e **não** entra em nenhuma estatística até que o candidato
    confirme ou corrija a causa.
    """

    __tablename__ = "error_analyses"
    __table_args__ = (
        UniqueConstraint("question_attempt_id", name="uq_error_analyses_attempt"),
        Index("ix_error_analyses_user_cause", "user_id", "cause"),
        Index("ix_error_analyses_user_created", "user_id", "created_at"),
    )

    question_attempt_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("question_attempts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE")
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    cause: Mapped[str] = mapped_column(String(30))
    trap_pattern_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("trap_patterns.id", ondelete="SET NULL")
    )
    note: Mapped[str | None] = mapped_column(MediumText)

    source: Mapped[str] = mapped_column(String(10), default=AnalysisSource.USER)
    model_slug: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    rationale: Mapped[str | None] = mapped_column(MediumText)
    # Só entra em estatística depois de confirmada por quem errou.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    attempt: Mapped[QuestionAttempt] = relationship(lazy="selectin")
    trap_pattern: Mapped[TrapPattern | None] = relationship(lazy="selectin")

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None


class UserPriority(IdMixin, TimestampMixin, Base):
    """Priority Score de uma disciplina (ou assunto) para um candidato.

    ``contributions`` guarda as parcelas que **somam exatamente** ``score``: é o
    "POR QUÊ?" da interface, não um texto gerado depois do número.
    """

    __tablename__ = "user_priorities"
    __table_args__ = (
        UniqueConstraint("user_id", "scope_key", name="uq_user_priorities_user_scope"),
        Index("ix_user_priorities_user_score", "user_id", "score"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    study_plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("study_plans.id", ondelete="CASCADE")
    )
    scope_key: Mapped[str] = mapped_column(String(120))
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(String(200))
    color_token: Mapped[str] = mapped_column(String(40), default="subject-especifica")

    score: Mapped[int] = mapped_column(Integer, default=0)
    contributions: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    # Sinais que existiam quando o score foi calculado (0..1).
    coverage: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0"))
    missing_signals: Mapped[list[str]] = mapped_column(JsonType, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
