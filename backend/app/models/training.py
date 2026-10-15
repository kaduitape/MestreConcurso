"""Treinamentos interativos: roteiro estruturado, não vídeo monolítico."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class TrainingStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class TrainingProgressStatus(StrEnum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"


class TrainingLesson(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma aula composta por JSON, timeline e assets reutilizáveis.

    ``script`` guarda as cenas editáveis. Áudio, avatar e efeitos são referências
    futuras dessa mesma timeline — nunca um MP4 obrigatório para toda a aula.
    """

    __tablename__ = "training_lessons"
    __table_args__ = (
        Index("ix_training_lessons_status_created_at", "status", "created_at"),
        Index(
            "ix_training_lessons_created_by_user_id_created_at", "created_by_user_id", "created_at"
        ),
    )

    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(140))
    topic: Mapped[str] = mapped_column(String(240))
    character_name: Mapped[str] = mapped_column(String(120))
    additional_prompt: Mapped[str | None] = mapped_column(MediumText)
    level: Mapped[str] = mapped_column(String(20), default="INTERMEDIARIO")
    style: Mapped[str] = mapped_column(String(40), default="AULA")
    target_duration_minutes: Mapped[int] = mapped_column(Integer, default=10)
    board_name: Mapped[str | None] = mapped_column(String(120))
    research_before_generate: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Voz desta aula. Vazio usa a voz padrão da funcionalidade — personagens
    #: diferentes merecem vozes diferentes, e quem decide isso é uma pessoa.
    narration_voice: Mapped[str | None] = mapped_column(String(40))

    status: Mapped[str] = mapped_column(String(20), default=TrainingStatus.DRAFT, index=True)
    script: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    generation_error: Mapped[str | None] = mapped_column(MediumText)
    model_slug: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TrainingProgress(IdMixin, TimestampMixin, Base):
    """Progresso real por candidato, usado para retomar e concluir a missão."""

    __tablename__ = "training_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_training_progress_user_lesson"),
        Index("ix_training_progress_lesson_status", "lesson_id", "status"),
        Index("ix_training_progress_user_updated", "user_id", "updated_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    lesson_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("training_lessons.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=TrainingProgressStatus.STARTED)
    current_scene: Mapped[int] = mapped_column(Integer, default=0)
    completed_scenes: Mapped[int] = mapped_column(Integer, default=0)
    focus_seconds: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)


class TrainingNarration(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um trecho de narração já gerado, guardado para não ser gerado de novo.

    A chave é o ``checksum``: texto + direção de cena + voz + modelo. Reescrever
    uma vírgula do roteiro produz outro trecho e outro áudio; reabrir a mesma
    aula não produz nada. É a mesma regra do cache de IA do resto da plataforma
    — **o token é pago uma vez**.

    A linha aponta para a aula e para a cena, mas o áudio não morre com uma
    edição: dois roteiros com a mesma frase reaproveitam o mesmo arquivo.
    """

    __tablename__ = "training_narrations"
    __table_args__ = (
        UniqueConstraint("checksum", name="uq_training_narrations_checksum"),
        Index("ix_training_narrations_lesson_scene", "lesson_id", "scene_id"),
    )

    lesson_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("training_lessons.id", ondelete="CASCADE")
    )
    scene_id: Mapped[int] = mapped_column(Integer, default=0)
    segment_index: Mapped[int] = mapped_column(Integer, default=0)

    checksum: Mapped[str] = mapped_column(String(64), index=True)
    text: Mapped[str] = mapped_column(MediumText)
    #: A direção de cena usada. Fica guardada para o áudio ser explicável.
    direction: Mapped[str] = mapped_column(MediumText)

    storage_key: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(60), default="audio/mpeg")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    voice: Mapped[str] = mapped_column(String(40))
    model_slug: Mapped[str] = mapped_column(String(120))
    provider_slug: Mapped[str] = mapped_column(String(40), default="")
    characters: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
