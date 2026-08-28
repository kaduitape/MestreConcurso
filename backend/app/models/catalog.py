"""Catálogo de concursos: bancas, órgãos, certames, cargos, disciplinas e assuntos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
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
    from app.models.notice import Notice


class CompetitionStatus(StrEnum):
    ANNOUNCED = "ANNOUNCED"  # previsto / comissão formada
    REGISTRATIONS_OPEN = "OPEN"  # inscrições abertas
    IN_PROGRESS = "IN_PROGRESS"  # inscrições encerradas, provas por vir
    CONCLUDED = "CONCLUDED"
    CANCELED = "CANCELED"


class EducationLevel(StrEnum):
    FUNDAMENTAL = "FUNDAMENTAL"
    MEDIO = "MEDIO"
    TECNICO = "TECNICO"
    SUPERIOR = "SUPERIOR"


class GovernmentSphere(StrEnum):
    FEDERAL = "FEDERAL"
    ESTADUAL = "ESTADUAL"
    MUNICIPAL = "MUNICIPAL"
    DISTRITAL = "DISTRITAL"


class ExamBoard(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Banca organizadora (CESPE/Cebraspe, FGV, FCC…)."""

    __tablename__ = "exam_boards"
    __table_args__ = (UniqueConstraint("slug", name="uq_exam_boards_slug"),)

    slug: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(160))
    short_name: Mapped[str] = mapped_column(String(60))
    aliases: Mapped[list[str]] = mapped_column(JsonType, default=list)
    website: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(MediumText)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    competitions: Mapped[list[Competition]] = relationship(
        back_populates="exam_board", lazy="noload"
    )


class Organization(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Órgão que abre o concurso (PF, PCDF, TRT…)."""

    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)

    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str] = mapped_column(String(60))
    sphere: Mapped[str] = mapped_column(String(20), default=GovernmentSphere.FEDERAL)
    uf: Mapped[str | None] = mapped_column(String(2))
    website: Mapped[str | None] = mapped_column(String(255))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Competition(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um certame específico (órgão + banca + ano)."""

    __tablename__ = "competitions"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_competitions_slug"),
        Index("ix_competitions_status_exam_date", "status", "exam_date"),
        Index("ix_competitions_exam_board_id_year", "exam_board_id", "year"),
    )

    slug: Mapped[str] = mapped_column(String(140), index=True)
    name: Mapped[str] = mapped_column(String(200))
    organization_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    exam_board_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("exam_boards.id", ondelete="SET NULL"), index=True
    )
    year: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(20), default=CompetitionStatus.ANNOUNCED)
    education_level: Mapped[str | None] = mapped_column(String(20))
    vacancies_total: Mapped[int | None] = mapped_column(Integer)
    salary_max_cents: Mapped[int | None] = mapped_column(BigInteger)
    registration_start: Mapped[date | None] = mapped_column(Date)
    registration_end: Mapped[date | None] = mapped_column(Date)
    exam_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(MediumText)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    organization: Mapped[Organization] = relationship(lazy="selectin")
    exam_board: Mapped[ExamBoard | None] = relationship(
        back_populates="competitions", lazy="selectin"
    )
    positions: Mapped[list[Position]] = relationship(
        back_populates="competition", cascade="all, delete-orphan", lazy="selectin"
    )
    notices: Mapped[list[Notice]] = relationship(back_populates="competition", lazy="noload")


class Position(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Cargo dentro de um concurso."""

    __tablename__ = "positions"
    __table_args__ = (Index("ix_positions_competition_id_name", "competition_id", "name"),)

    competition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    education_level: Mapped[str | None] = mapped_column(String(20))
    salary_cents: Mapped[int | None] = mapped_column(BigInteger)
    vacancies: Mapped[int | None] = mapped_column(Integer)
    cr_vacancies: Mapped[int | None] = mapped_column(Integer)
    workload_hours: Mapped[int | None] = mapped_column(Integer)
    requirements: Mapped[str | None] = mapped_column(MediumText)
    questions_count: Mapped[int | None] = mapped_column(Integer)
    exam_duration_minutes: Mapped[int | None] = mapped_column(Integer)

    competition: Mapped[Competition] = relationship(back_populates="positions")
    subjects: Mapped[list[PositionSubject]] = relationship(
        back_populates="position", cascade="all, delete-orphan", lazy="selectin"
    )


class Subject(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Disciplina canônica (Português, Direito Constitucional…)."""

    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("slug", name="uq_subjects_slug"),)

    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(140))
    area: Mapped[str | None] = mapped_column(String(80))
    # Token do design system — mantém a cor da disciplina igual em todas as telas.
    color_token: Mapped[str] = mapped_column(String(40), default="subject-especifica")
    description: Mapped[str | None] = mapped_column(MediumText)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    topics: Mapped[list[Topic]] = relationship(
        back_populates="subject", cascade="all, delete-orphan", lazy="noload"
    )


class Topic(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Assunto/subassunto em árvore, com caminho materializado para consultas rápidas."""

    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("subject_id", "slug", name="uq_topics_subject_id_slug"),
        Index("ix_topics_subject_id_parent_id", "subject_id", "parent_id"),
        Index("ix_topics_path", "path"),
    )

    subject_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220))
    depth: Mapped[int] = mapped_column(Integer, default=0)
    path: Mapped[str] = mapped_column(String(512), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str | None] = mapped_column(MediumText)

    subject: Mapped[Subject] = relationship(back_populates="topics")
    children: Mapped[list[Topic]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", lazy="noload"
    )
    parent: Mapped[Topic | None] = relationship(back_populates="children", remote_side="Topic.id")


class PositionSubject(IdMixin, TimestampMixin, Base):
    """Disciplina cobrada por um cargo, com peso e número de questões."""

    __tablename__ = "position_subjects"
    __table_args__ = (
        UniqueConstraint(
            "position_id", "subject_id", name="uq_position_subjects_position_id_subject_id"
        ),
    )

    position_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("positions.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="CASCADE"), index=True
    )
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("1.00"))
    questions_count: Mapped[int | None] = mapped_column(Integer)
    min_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_eliminatory: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="MANUAL")  # MANUAL | NOTICE | AI
    extra: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    position: Mapped[Position] = relationship(back_populates="subjects")
    subject: Mapped[Subject] = relationship(lazy="selectin")
