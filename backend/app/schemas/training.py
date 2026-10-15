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
    #: Voz desta aula. Vazio usa a voz padrão da funcionalidade.
    narration_voice: str | None = None
    status: str
    script: dict[str, Any] = Field(default_factory=dict)
    generation_error: str | None = None
    model_slug: str | None = None
    generated_at: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NarrationSegmentRead(BaseModel):
    """Um trecho falado: o texto, onde ele está na cena e o áudio dele."""

    index: int
    text: str
    #: Posição dentro do texto da cena — é o que acende a frase que está tocando.
    offset: int
    length: int
    #: ``None`` enquanto este trecho ainda não foi gerado.
    audio_url: str | None = None
    #: Estimativa só para a interface não nascer zerada; o player usa a duração
    #: real do arquivo assim que ele carrega.
    duration_hint_ms: int = 0


class NarrationSceneRead(BaseModel):
    scene_id: int
    segments: list[NarrationSegmentRead] = Field(default_factory=list)


class TrainingNarrationRead(BaseModel):
    voice: str
    model_slug: str | None = None
    scenes: list[NarrationSceneRead] = Field(default_factory=list)
    ready: int = 0
    total: int = 0
    is_complete: bool = False
    #: Por que ainda não há áudio. A tela mostra isto em vez de ficar muda.
    unavailable_reason: str | None = None


class TrainingVoiceRead(BaseModel):
    slug: str
    label: str


class TrainingVoiceUpdate(BaseModel):
    #: Vazio devolve a aula à voz padrão da funcionalidade.
    voice: str | None = None
