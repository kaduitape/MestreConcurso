"""Banco de provas: provas, questões, alternativas e estatísticas de uso.

Estatística aqui é sempre contagem sobre tentativas reais. Enquanto a amostra for
pequena, a plataforma diz "dados insuficientes" em vez de exibir um percentual que
não se sustenta.
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
from app.db.types import JsonType, MediumText, Sha256Hex

if TYPE_CHECKING:
    from app.models.catalog import ExamBoard, Subject


class QuestionKind(StrEnum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    DISCURSIVE = "DISCURSIVE"


class QuestionDifficulty(StrEnum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class QuestionOrigin(StrEnum):
    OFFICIAL = "OFFICIAL"  # questão de prova aplicada
    AI_GENERATED = "AI_GENERATED"
    EDITORIAL = "EDITORIAL"


class QuestionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class Exam(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma prova aplicada, agrupando as questões pelo contexto real."""

    __tablename__ = "exams"
    __table_args__ = (
        Index("ix_exams_board_year", "exam_board_id", "year"),
        Index("ix_exams_competition", "competition_id"),
    )

    name: Mapped[str] = mapped_column(String(255))
    exam_board_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("exam_boards.id", ondelete="SET NULL"), index=True
    )
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )
    position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("positions.id", ondelete="SET NULL")
    )
    year: Mapped[int] = mapped_column(Integer, index=True)
    phase: Mapped[str | None] = mapped_column(String(60))
    applied_on: Mapped[date | None] = mapped_column(Date)
    questions_count: Mapped[int | None] = mapped_column(Integer)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(String(500))
    is_official: Mapped[bool] = mapped_column(Boolean, default=True)

    exam_board: Mapped[ExamBoard | None] = relationship(lazy="selectin")
    questions: Mapped[list[Question]] = relationship(back_populates="exam", lazy="noload")


class Question(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma questão do banco, com sua procedência."""

    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("checksum", name="uq_questions_checksum"),
        Index("ix_questions_subject_topic", "subject_id", "topic_id"),
        Index("ix_questions_board_year", "exam_board_id", "year"),
        Index("ix_questions_status_origin", "status", "origin"),
    )

    exam_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("exams.id", ondelete="SET NULL"), index=True
    )
    exam_board_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("exam_boards.id", ondelete="SET NULL")
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )
    year: Mapped[int | None] = mapped_column(Integer)

    statement: Mapped[str] = mapped_column(MediumText)
    kind: Mapped[str] = mapped_column(String(20), default=QuestionKind.MULTIPLE_CHOICE)
    difficulty: Mapped[str] = mapped_column(String(10), default=QuestionDifficulty.MEDIUM)
    origin: Mapped[str] = mapped_column(String(20), default=QuestionOrigin.OFFICIAL)
    status: Mapped[str] = mapped_column(String(20), default=QuestionStatus.PUBLISHED)
    explanation: Mapped[str | None] = mapped_column(MediumText)
    source_note: Mapped[str | None] = mapped_column(String(255))
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    # Impressão digital do enunciado normalizado: barra duplicata na importação.
    checksum: Mapped[str] = mapped_column(Sha256Hex, index=True)

    # Classificação sugerida por IA aguardando revisão humana.
    ai_suggestion: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    exam: Mapped[Exam | None] = relationship(back_populates="questions")
    subject: Mapped[Subject | None] = relationship(lazy="selectin")
    alternatives: Mapped[list[Alternative]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Alternative.letter",
    )
    stats: Mapped[QuestionStats | None] = relationship(
        back_populates="question", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def correct_alternative(self) -> Alternative | None:
        return next((item for item in self.alternatives if item.is_correct), None)


class Alternative(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Alternativa de uma questão. O comentário explica por que ela erra ou acerta."""

    __tablename__ = "alternatives"
    __table_args__ = (
        UniqueConstraint("question_id", "letter", name="uq_alternatives_question_letter"),
    )

    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    letter: Mapped[str] = mapped_column(String(2))
    content: Mapped[str] = mapped_column(MediumText)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str | None] = mapped_column(MediumText)

    question: Mapped[Question] = relationship(back_populates="alternatives")


class QuestionStats(IdMixin, TimestampMixin, Base):
    """Contadores agregados de uso — a fonte de qualquer percentual exibido."""

    __tablename__ = "question_stats"
    __table_args__ = (UniqueConstraint("question_id", name="uq_question_stats_question"),)

    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0)
    total_time_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    question: Mapped[Question] = relationship(back_populates="stats")

    @property
    def accuracy(self) -> Decimal | None:
        """Taxa de acerto. Sem amostra mínima, devolve ``None`` em vez de um número frágil."""
        if self.attempts < MIN_STATS_SAMPLE:
            return None
        return Decimal(self.correct_attempts) / Decimal(self.attempts)

    @property
    def average_time_seconds(self) -> int | None:
        if self.attempts <= 0:
            return None
        return self.total_time_seconds // self.attempts


# Abaixo desta amostra a taxa de acerto não é exibida como estatística.
MIN_STATS_SAMPLE = 20


class QuestionAttempt(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Resposta de um candidato a uma questão."""

    __tablename__ = "question_attempts"
    __table_args__ = (
        Index("ix_question_attempts_user_created", "user_id", "created_at"),
        Index("ix_question_attempts_user_question", "user_id", "question_id"),
        Index("ix_question_attempts_attempt", "simulation_attempt_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), index=True
    )
    simulation_attempt_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("simulation_attempts.id", ondelete="CASCADE")
    )
    study_task_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("study_tasks.id", ondelete="SET NULL")
    )

    selected_alternative_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("alternatives.id", ondelete="SET NULL")
    )
    selected_letter: Mapped[str | None] = mapped_column(String(2))
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blank: Mapped[bool] = mapped_column(Boolean, default=False)
    time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    # Quanta certeza o candidato tinha — entra na análise de erro da Fase 6.
    confidence: Mapped[str | None] = mapped_column(String(10))
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )

    question: Mapped[Question] = relationship(lazy="selectin")


class SimulationKind(StrEnum):
    OFFICIAL = "OFFICIAL"  # distribuição igual à da prova
    BOARD = "BOARD"  # só questões da banca
    ERRORS = "ERRORS"  # questões que o candidato errou
    FINAL_STRETCH = "FINAL_STRETCH"  # alto retorno na reta final
    FLASH = "FLASH"  # relâmpago, poucas questões
    CUSTOM = "CUSTOM"
    ADAPTIVE = "ADAPTIVE"  # dificuldade ajustada pelo desempenho


class SimulationAttemptStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ABANDONED = "ABANDONED"


class Simulation(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um simulado montado para um candidato (ou modelo reaproveitável)."""

    __tablename__ = "simulations"
    __table_args__ = (Index("ix_simulations_user_kind", "user_id", "kind"),)

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(20), default=SimulationKind.CUSTOM)
    name: Mapped[str] = mapped_column(String(200))
    questions_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)

    questions: Mapped[list[SimulationQuestion]] = relationship(
        back_populates="simulation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SimulationQuestion.order_index",
    )


class SimulationQuestion(IdMixin, Base):
    __tablename__ = "simulation_questions"
    __table_args__ = (
        UniqueConstraint(
            "simulation_id", "question_id", name="uq_simulation_questions_sim_question"
        ),
    )

    simulation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("simulations.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id", ondelete="CASCADE")
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    simulation: Mapped[Simulation] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship(lazy="selectin")


class SimulationAttempt(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Execução do simulado: cronômetro, respostas e resultado."""

    __tablename__ = "simulation_attempts"
    __table_args__ = (Index("ix_simulation_attempts_user_status", "user_id", "status"),)

    simulation_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("simulations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=SimulationAttemptStatus.IN_PROGRESS)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0)

    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    blank_count: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    # Correção completa calculada em Python no encerramento.
    analysis: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    simulation: Mapped[Simulation] = relationship(lazy="selectin")
