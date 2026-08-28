"""Schemas de flashcards e revisão."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)

_ORIGIN = "^(USER|AI|QUESTION|ERROR|NOTICE|EDITORIAL)$"


class FlashcardRead(BaseModel):
    model_config = _READ

    public_id: str
    front: str
    back: str
    hint: str | None = None
    tags: list[str] = Field(default_factory=list)
    subject_name: str | None = None
    # Governa o selo de procedência exibido na interface.
    origin: str
    source_ref: str | None = None
    source_quote: str | None = None
    source_page: int | None = None
    source_document: str | None = None
    model_slug: str | None = None
    is_owned: bool = True
    created_at: datetime


class FlashcardCreate(BaseModel):
    front: str = Field(min_length=3)
    back: str = Field(min_length=1)
    hint: str | None = None
    tags: list[str] = Field(default_factory=list)
    subject_public_id: str | None = None


class FlashcardUpdate(BaseModel):
    front: str | None = Field(default=None, min_length=3)
    back: str | None = Field(default=None, min_length=1)
    hint: str | None = None
    tags: list[str] | None = None
    subject_public_id: str | None = None
    is_active: bool | None = None


class GenerateInput(BaseModel):
    material: str = Field(min_length=80, max_length=20000)
    quantity: int = Field(default=5, ge=1, le=10)
    subject_public_id: str | None = None
    source_document: str | None = Field(default=None, max_length=255)
    source_page: int | None = Field(default=None, ge=1)


class GenerationRead(BaseModel):
    created: list[FlashcardRead] = Field(default_factory=list)
    # Cartões descartados por citação não conferida — dito, não escondido.
    discarded: list[str] = Field(default_factory=list)
    skipped_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None


class CardStateRead(BaseModel):
    state: str
    interval_days: int
    due_on: date
    repetitions: int
    lapses: int
    ease_factor: float
    last_rating: str | None = None
    postponed_count: int = 0


class QueueItemRead(BaseModel):
    card: FlashcardRead
    state: CardStateRead
    is_new: bool


class QueuePlanRead(BaseModel):
    review_count: int
    new_count: int
    overdue_count: int
    absence_days: int
    rescheduled_count: int
    # Frase que explica o que aconteceu com a fila hoje.
    summary: str


class ReviewQueueRead(BaseModel):
    items: list[QueueItemRead] = Field(default_factory=list)
    plan: QueuePlanRead
    total_cards: int
    reviewed_today: int
    upcoming: list[dict[str, Any]] = Field(default_factory=list)


class AnswerInput(BaseModel):
    rating: str = Field(pattern="^(AGAIN|HARD|GOOD|EASY)$")
    time_seconds: int = Field(default=0, ge=0, le=3600)


class ReviewResultRead(BaseModel):
    interval_days: int
    due_on: date
    state: str
    # Como o intervalo foi calculado — o "por quê?" do próximo encontro.
    breakdown: dict[str, Any] = Field(default_factory=dict)
    remaining_today: int


class ReviewStatsRead(BaseModel):
    total_cards: int
    by_state: dict[str, int] = Field(default_factory=dict)
    due_today: int
    mature_cards: int
    total_reviews: int
    reviewed_today: int
    # Nulo enquanto não houver revisão registrada: zero seria outra afirmação.
    recall_rate: float | None = None
    ratings: dict[str, int] = Field(default_factory=dict)
    upcoming: list[dict[str, Any]] = Field(default_factory=list)


class FromSourceInput(BaseModel):
    question_public_id: str | None = None
    error_public_id: str | None = None
