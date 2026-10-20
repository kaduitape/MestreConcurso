"""Mapas mentais do Game of Concursos.

O mapa é guardado como **dado estruturado**, não como imagem. Gerador de imagem
não escreve português confiável, e num mapa de estudo texto embaralhado não é um
defeito estético: é conteúdo errado sendo decorado. A arte medieval é moldura e
fundo; o texto é texto de verdade na tela.

O ciclo é o mesmo do Estúdio de Treinamento, e pela mesma razão: a IA propõe,
**uma pessoa revisa**, e só então o mapa é publicado para quem estuda.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class MindMapStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    READY = "READY"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class MindMap(IdMixin, PublicIdMixin, TimestampMixin, Base):
    __tablename__ = "mind_maps"
    __table_args__ = (Index("ix_mind_maps_status_created_at", "status", "created_at"),)

    created_by_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: Vínculo com o catálogo, confirmado por uma pessoa. O ``subject_id`` foi
    #: criado junto com o mapa mental e nunca chegou a ser preenchido — esta
    #: fase conserta isso e acrescenta o tópico.
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL"), index=True
    )

    subject: Mapped[str] = mapped_column(String(140))
    topic: Mapped[str] = mapped_column(String(240))
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20), default="INTERMEDIARIO")
    #: Teto de painéis pedido na criação. O pedido fixa o máximo em oito.
    max_panels: Mapped[int] = mapped_column(Integer, default=8)
    #: O material de estudo que a IA recebeu. Guardado para o mapa ser
    #: auditável: dá para conferir se o que saiu estava no que entrou.
    source_content: Mapped[str | None] = mapped_column(MediumText)

    status: Mapped[str] = mapped_column(String(20), default=MindMapStatus.DRAFT, index=True)
    content: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    generation_error: Mapped[str | None] = mapped_column(MediumText)

    model_slug: Mapped[str | None] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
