"""Plano de estudo, agenda, sessões e progresso.

O plano é gerado por cálculo (``app/domain/planner``) e cada tarefa guarda o
``score_breakdown`` que a colocou ali — é o que permite responder "por quê?" sem
precisar perguntar a um modelo.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

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


class StudyPlanStatus(StrEnum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ARCHIVED = "ARCHIVED"


class StudyTaskKind(StrEnum):
    THEORY = "THEORY"
    QUESTIONS = "QUESTIONS"
    REVIEW = "REVIEW"
    FLASHCARDS = "FLASHCARDS"
    SIMULATION = "SIMULATION"
    SPRINT = "SPRINT"


class StudyTaskStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    RESCHEDULED = "RESCHEDULED"
    DROPPED = "DROPPED"


class StudyTaskSource(StrEnum):
    PLANNER = "PLANNER"
    REBALANCE = "REBALANCE"
    SPRINT = "SPRINT"
    USER = "USER"


class StudySessionStatus(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ABANDONED = "ABANDONED"


class StudyPeriod(StrEnum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    NIGHT = "NIGHT"


class StudyPlan(IdMixin, PublicIdMixin, TimestampMixin, Base):
    __tablename__ = "study_plans"
    __table_args__ = (Index("ix_study_plans_user_status", "user_id", "status"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )
    notice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="SET NULL")
    )
    position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("positions.id", ondelete="SET NULL")
    )

    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=StudyPlanStatus.ACTIVE)
    exam_date: Mapped[date | None] = mapped_column(Date)
    starts_on: Mapped[date] = mapped_column(Date)
    weekly_minutes_target: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recalculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Distribuição das disciplinas e composição por tipo de atividade.
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    availability: Mapped[list[StudyAvailability]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )
    tasks: Mapped[list[StudyTask]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="noload"
    )


class StudyAvailability(IdMixin, TimestampMixin, Base):
    """Minutos que o candidato tem em cada dia da semana."""

    __tablename__ = "study_availability"
    __table_args__ = (
        UniqueConstraint("study_plan_id", "weekday", name="uq_study_availability_plan_weekday"),
    )

    study_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("study_plans.id", ondelete="CASCADE"), index=True
    )
    weekday: Mapped[int] = mapped_column(Integer)  # 0 = segunda … 6 = domingo
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    period: Mapped[str | None] = mapped_column(String(20))

    plan: Mapped[StudyPlan] = relationship(back_populates="availability")


class StudyTask(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma tarefa concreta em um dia do plano."""

    __tablename__ = "study_tasks"
    __table_args__ = (
        Index("ix_study_tasks_user_day_status", "user_id", "scheduled_for", "status"),
        Index("ix_study_tasks_plan_day", "study_plan_id", "scheduled_for"),
    )

    study_plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("study_plans.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scheduled_for: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(20))

    # A disciplina pode vir do edital (ainda sem vínculo canônico) ou do catálogo.
    subject_key: Mapped[str | None] = mapped_column(String(60))
    subject_label: Mapped[str | None] = mapped_column(String(200))
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    notice_subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notice_subjects.id", ondelete="SET NULL")
    )
    color_token: Mapped[str] = mapped_column(String(40), default="subject-especifica")

    planned_minutes: Mapped[int] = mapped_column(Integer)
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=StudyTaskStatus.PENDING)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default=StudyTaskSource.PLANNER)
    reschedule_count: Mapped[int] = mapped_column(Integer, default=0)
    rescheduled_from: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Contribuições que puseram a tarefa aqui — base do "POR QUÊ?" da interface.
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    plan: Mapped[StudyPlan] = relationship(back_populates="tasks")
    sessions: Mapped[list[StudySession]] = relationship(
        back_populates="task", cascade="all, delete-orphan", lazy="noload"
    )


class StudySession(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Cronômetro: tempo real dedicado, separado do tempo planejado."""

    __tablename__ = "study_sessions"
    __table_args__ = (Index("ix_study_sessions_user_started", "user_id", "started_at"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    study_task_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("study_tasks.id", ondelete="SET NULL")
    )
    subject_key: Mapped[str | None] = mapped_column(String(60))
    subject_label: Mapped[str | None] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default=StudyTaskKind.THEORY)

    status: Mapped[str] = mapped_column(String(20), default=StudySessionStatus.RUNNING)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    focus_seconds: Mapped[int] = mapped_column(Integer, default=0)
    pause_seconds: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(MediumText)

    task: Mapped[StudyTask | None] = relationship(back_populates="sessions", lazy="selectin")


class UserSubjectProgress(IdMixin, TimestampMixin, Base):
    """Acúmulo por disciplina — tempo real, tarefas concluídas, último estudo."""

    __tablename__ = "user_subject_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "subject_key", name="uq_user_subject_progress_user_key"),
        Index("ix_user_subject_progress_user", "user_id", "last_studied_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subject_key: Mapped[str] = mapped_column(String(60))
    subject_label: Mapped[str] = mapped_column(String(200))
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    color_token: Mapped[str] = mapped_column(String(40), default="subject-especifica")

    planned_minutes: Mapped[int] = mapped_column(Integer, default=0)
    studied_minutes: Mapped[int] = mapped_column(Integer, default=0)
    tasks_done: Mapped[int] = mapped_column(Integer, default=0)
    tasks_skipped: Mapped[int] = mapped_column(Integer, default=0)
    last_studied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Percentual do plano já cumprido nesta disciplina (0..1), calculado em Python.
    completion: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    is_weak_point: Mapped[bool] = mapped_column(Boolean, default=False)
