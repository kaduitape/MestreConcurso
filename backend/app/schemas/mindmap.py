"""Contratos dos mapas mentais."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.mindmap import MAX_ITEMS_PER_PANEL, MAX_PANELS, MIN_PANELS

_READ = ConfigDict(from_attributes=True)


class MindMapCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=140)
    topic: str = Field(min_length=2, max_length=240)
    level: str = "INTERMEDIARIO"
    max_panels: int = Field(default=MAX_PANELS, ge=MIN_PANELS, le=MAX_PANELS)
    #: O material de estudo. Quanto mais fiel, menos a IA precisa supor.
    source_content: str | None = None


class MindMapItemRead(BaseModel):
    text: str
    tone: str = "NEUTRO"
    tone_color: str = "slate"
    #: Só vem preenchida quando a fonte estava no material enviado.
    source: str | None = None


class MindMapPanelRead(BaseModel):
    kind: str
    title: str
    label: str
    color_token: str
    icon: str
    items: list[MindMapItemRead] = Field(default_factory=list, max_length=MAX_ITEMS_PER_PANEL)


class MindMapContentRead(BaseModel):
    version: str = ""
    subject: str = ""
    topic: str = ""
    center_label: str = ""
    #: Dúvidas que a IA registrou para a revisão humana.
    review_notes: list[str] = Field(default_factory=list)
    panels: list[MindMapPanelRead] = Field(default_factory=list)


class MindMapRead(BaseModel):
    model_config = _READ

    public_id: str
    subject: str
    topic: str
    title: str
    level: str
    max_panels: int
    status: str
    content: dict[str, Any] = Field(default_factory=dict)
    generation_error: str | None = None
    model_slug: str | None = None
    generated_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime


class MindMapContentUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: dict[str, Any]


class MindMapPanelSpecRead(BaseModel):
    """O catálogo de painéis, para o editor explicar o que entra em cada um."""

    kind: str
    label: str
    guidance: str
    color_token: str
    icon: str
