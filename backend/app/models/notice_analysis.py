"""Resultado da análise de um edital, sempre com prova de origem.

Regra do produto: nenhum campo vira "fato" sem que a citação exista literalmente no
PDF. O validador em Python confere a citação; o que não passa é rebaixado a
``INFERRED`` ou marcado ``NOT_FOUND`` — a IA não decide sozinha o que é oficial.
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
    from app.models.notice import Notice


class EvidenceLevel(StrEnum):
    """Como o dado chegou até aqui — a interface mostra os três de forma distinta."""

    OFFICIAL = "OFFICIAL"  # citação conferida literalmente no PDF
    INFERRED = "INFERRED"  # a IA deduziu; precisa de confirmação humana
    NOT_FOUND = "NOT_FOUND"  # não localizado no documento
    CONFIRMED = "CONFIRMED"  # revisado e confirmado por uma pessoa


class NoticeSectionKind(StrEnum):
    GENERAL = "GENERAL"
    POSITIONS = "POSITIONS"
    DISCIPLINES = "DISCIPLINES"
    SCHEDULE = "SCHEDULE"
    REGISTRATION = "REGISTRATION"
    EXAM_RULES = "EXAM_RULES"
    ELIMINATION = "ELIMINATION"
    PHYSICAL_TEST = "PHYSICAL_TEST"
    APPEALS = "APPEALS"
    ATTACHMENT = "ATTACHMENT"


class NoticeEventKind(StrEnum):
    REGISTRATION_START = "REGISTRATION_START"
    REGISTRATION_END = "REGISTRATION_END"
    FEE_DEADLINE = "FEE_DEADLINE"
    EXEMPTION_PERIOD = "EXEMPTION_PERIOD"
    EXAM = "EXAM"
    RESULT = "RESULT"
    APPEAL = "APPEAL"
    PHYSICAL_TEST = "PHYSICAL_TEST"
    OTHER = "OTHER"


class NoticeSection(IdMixin, TimestampMixin, Base):
    """Bloco do edital identificado na estruturação (antes de qualquer IA)."""

    __tablename__ = "notice_sections"
    __table_args__ = (Index("ix_notice_sections_notice_kind", "notice_id", "kind"),)

    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str | None] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(30), default=NoticeSectionKind.GENERAL)
    content: Mapped[str | None] = mapped_column(MediumText)
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer, default=0)


class NoticeFact(IdMixin, TimestampMixin, Base):
    """Um campo extraído, com o trecho que o comprova."""

    __tablename__ = "notice_facts"
    __table_args__ = (
        UniqueConstraint("notice_id", "field_path", name="uq_notice_facts_notice_field"),
        Index("ix_notice_facts_evidence_level", "notice_id", "evidence_level"),
    )

    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    field_path: Mapped[str] = mapped_column(String(120))
    label: Mapped[str] = mapped_column(String(160))
    value: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    evidence_level: Mapped[str] = mapped_column(String(20), default=EvidenceLevel.NOT_FOUND)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    page_number: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(MediumText)
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    chunk_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("document_chunks.id", ondelete="SET NULL")
    )

    extracted_by: Mapped[str] = mapped_column(String(20), default="AI")
    model_slug: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notice: Mapped[Notice] = relationship(back_populates="facts")


class NoticeEvent(IdMixin, TimestampMixin, Base):
    """Data do cronograma do edital."""

    __tablename__ = "notice_events"
    __table_args__ = (Index("ix_notice_events_notice_date", "notice_id", "date_start"),)

    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(30), default=NoticeEventKind.OTHER)
    title: Mapped[str] = mapped_column(String(255))
    date_start: Mapped[date | None] = mapped_column(Date)
    date_end: Mapped[date | None] = mapped_column(Date)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_fact_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notice_facts.id", ondelete="SET NULL")
    )
    evidence_level: Mapped[str] = mapped_column(String(20), default=EvidenceLevel.INFERRED)
    page_number: Mapped[int | None] = mapped_column(Integer)
    #: A citação conferida no PDF. Era a única coisa extraída deste projeto que
    #: não guardava a própria prova: o nível de evidência dizia que a data tinha
    #: citação, e a citação não ficava em lugar nenhum. Sem ela não há como o
    #: cronograma do concurso mostrar de onde cada data veio.
    quote: Mapped[str | None] = mapped_column(MediumText)


class NoticePosition(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um cargo do edital, como o edital o descreve.

    Edital de concurso raramente tem um cargo só. A tabela existe porque a
    alternativa — espremer vinte cargos nos campos escalares ``position.*`` —
    obrigaria a escolher um e jogar dezenove fora, e o candidato que estuda para
    o cargo descartado não existiria para a plataforma.

    Cada linha carrega a própria procedência: citação literal, página e nível de
    evidência, conferidos pela mesma regra dos outros campos. Cargo sem citação
    conferida **não** vira cargo no catálogo — vira lacuna declarada.
    """

    __tablename__ = "notice_positions"
    __table_args__ = (Index("ix_notice_positions_notice", "notice_id", "order_index"),)

    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    #: O cargo já cadastrado no catálogo, quando o cadastro aconteceu. Anulável
    #: porque "extraído mas não cadastrado" é um estado real e frequente.
    position_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("positions.id", ondelete="SET NULL")
    )
    raw_label: Mapped[str] = mapped_column(String(200))
    education_level: Mapped[str | None] = mapped_column(String(20))
    salary_cents: Mapped[int | None] = mapped_column(BigInteger)
    #: Vagas imediatas. Separada do cadastro de reserva de propósito: somar as
    #: duas infla o número que o candidato usa para decidir se vale estudar.
    vacancies: Mapped[int | None] = mapped_column(Integer)
    cr_vacancies: Mapped[int | None] = mapped_column(Integer)
    workload_hours: Mapped[int | None] = mapped_column(Integer)
    requirements: Mapped[str | None] = mapped_column(MediumText)
    questions_count: Mapped[int | None] = mapped_column(Integer)
    exam_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    evidence_level: Mapped[str] = mapped_column(String(20), default=EvidenceLevel.INFERRED)
    page_number: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(MediumText)


class NoticeSubject(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Disciplina cobrada, como aparece no edital (e o vínculo com a disciplina canônica)."""

    __tablename__ = "notice_subjects"
    __table_args__ = (Index("ix_notice_subjects_notice", "notice_id", "order_index"),)

    notice_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="CASCADE"), index=True
    )
    #: De qual cargo é esta disciplina, como o edital o nomeia. Nulo quando a
    #: grade é comum a todos os cargos — o caso mais frequente. É o que permite
    #: montar a grade cargo por cargo sem duplicar o conteúdo programático.
    position_label: Mapped[str | None] = mapped_column(String(200))
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    raw_label: Mapped[str] = mapped_column(String(255))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    questions_count: Mapped[int | None] = mapped_column(Integer)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    evidence_level: Mapped[str] = mapped_column(String(20), default=EvidenceLevel.INFERRED)
    page_number: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(MediumText)

    topics: Mapped[list[NoticeTopic]] = relationship(
        back_populates="notice_subject", cascade="all, delete-orphan", lazy="selectin"
    )


class NoticeTopic(IdMixin, TimestampMixin, Base):
    """Conteúdo programático de uma disciplina do edital."""

    __tablename__ = "notice_topics"
    __table_args__ = (Index("ix_notice_topics_subject_order", "notice_subject_id", "order_index"),)

    notice_subject_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notice_subjects.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )
    raw_label: Mapped[str] = mapped_column(String(500))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer)

    notice_subject: Mapped[NoticeSubject] = relationship(back_populates="topics")
