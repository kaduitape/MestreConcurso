"""Contratos da geração em massa."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class GenerationItemRead(BaseModel):
    topic_name: str
    subject_name: str
    kind: str
    #: GENERATE ou REUSE — decidido quando o plano foi montado.
    decision: str
    status: str
    #: Por que esta decisão, e depois o que aconteceu.
    reason: str | None = None
    target_public_id: str | None = None
    cost_cents: Decimal = Decimal("0")


class GenerationPlanRead(BaseModel):
    public_id: str
    competition_public_id: str | None = None
    status: str
    kinds: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    #: Estimativa a partir do custo medido. Com ``estimate_is_known`` falso, o
    #: valor é só a parte que deu para estimar — a tela precisa dizer isso.
    estimate_cents: Decimal = Decimal("0")
    estimate_is_known: bool = False
    estimate_basis: dict[str, Any] = Field(default_factory=dict)
    spent_cents: Decimal = Decimal("0")
    confirmed_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    items: list[GenerationItemRead] = Field(default_factory=list)
    #: Contagens derivadas dos itens, nunca acumuladas.
    progress: dict[str, int] = Field(default_factory=dict)


class GenerationPlanCreate(BaseModel):
    competition_public_id: str
    kinds: list[str] = Field(min_length=1)
    character_name: str = Field(default="Mestre", max_length=120)
    level: str = Field(default="INTERMEDIARIO", max_length=20)
    style: str = Field(default="AULA", max_length=40)
    target_duration_minutes: int = Field(default=10, ge=3, le=60)
    max_panels: int = Field(default=6, ge=3, le=12)
    #: Quantos cartões por tópico o baralho oficial recebe por passada.
    cards_per_topic: int = Field(default=8, ge=1, le=10)
    #: Quantas questões por tópico são escritas por passada.
    questions_per_topic: int = Field(default=5, ge=1, le=10)
    #: A partir de quantas questões no banco o tópico conta como coberto — e o
    #: item vira reaproveitamento em vez de geração. É escolha editorial, por
    #: isso o painel manda.
    min_questions_per_topic: int = Field(default=5, ge=1, le=100)
