"""Contratos do Estúdio de Treinamento."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class TrainingCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=140)
    topic: str = Field(min_length=2, max_length=240)
    character_name: str = Field(min_length=2, max_length=120)
    additional_prompt: str | None = Field(default=None, max_length=4000)
    level: str = Field(
        default="INTERMEDIARIO", pattern="^(BASICO|INTERMEDIARIO|AVANCADO|ESPECIALISTA)$"
    )
    style: str = Field(
        default="AULA",
        pattern="^(AULA|HISTORIA|MISSAO|BATALHA|INVESTIGACAO|MILITAR|DESAFIO|REVISAO)$",
    )
    target_duration_minutes: int = Field(default=10, ge=3, le=60)
    board_name: str | None = Field(default=None, max_length=120)
    competition_public_id: str | None = None
    research_before_generate: bool = False


class TrainingScriptUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    script: dict[str, Any]


class TrainingProgressUpdate(BaseModel):
    current_scene: int = Field(ge=0, le=500)


class TrainingProgressRead(BaseModel):
    model_config = _READ

    status: str
    current_scene: int
    completed_scenes: int
    focus_seconds: int
    started_at: datetime
    last_seen_at: datetime
    completed_at: datetime | None = None
    xp_awarded: int


class TrainingMetricsRead(BaseModel):
    starts: int = 0
    completions: int = 0
    completion_rate: float = 0
    total_focus_seconds: int = 0
    average_focus_seconds: int = 0


class TrainingRead(BaseModel):
    model_config = _READ

    public_id: str
    title: str
    subject: str
    topic: str
    character_name: str
    additional_prompt: str | None = None
    level: str
    style: str
    target_duration_minutes: int
    board_name: str | None = None
    research_before_generate: bool
    status: str
    script: dict[str, Any] = Field(default_factory=dict)
    generation_error: str | None = None
    model_slug: str | None = None
    generated_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
