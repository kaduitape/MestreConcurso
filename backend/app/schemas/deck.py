"""Contratos do baralho oficial por tópico."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.flashcard import FlashcardRead

_READ = ConfigDict(from_attributes=True)


class OfficialDeckRead(BaseModel):
    model_config = _READ

    public_id: str
    title: str
    description: str | None = None
    status: str
    #: EDITORIAL, LESSON, NOTICE ou MATERIAL — governa o selo de procedência.
    source_kind: str
    source_ref: str | None = None
    topic_public_id: str | None = None
    topic_name: str | None = None
    subject_name: str | None = None
    #: Contagens derivadas dos cartões e das assinaturas, nunca acumuladas.
    active_cards: int = 0
    inactive_cards: int = 0
    ai_cards: int = 0
    subscribers: int = 0
    is_subscribed: bool = False
    published_at: datetime | None = None
    created_at: datetime


class OfficialDeckCreate(BaseModel):
    topic_public_id: str = Field(max_length=26)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class DeckCardCreate(BaseModel):
    front: str = Field(min_length=3)
    back: str = Field(min_length=1)
    hint: str | None = None
    tags: list[str] = Field(default_factory=list)


class DeckCardReview(BaseModel):
    is_active: bool


class DeckGenerateInput(BaseModel):
    material: str = Field(min_length=80, max_length=20000)
    quantity: int = Field(default=8, ge=1, le=10)
    source_document: str | None = Field(default=None, max_length=255)
    source_page: int | None = Field(default=None, ge=1)


class DeckGenerationRead(BaseModel):
    created: list[FlashcardRead] = Field(default_factory=list)
    #: Cartões descartados por citação não conferida — dito, não escondido.
    discarded: list[str] = Field(default_factory=list)
    #: Cartões iguais a um que o baralho já tinha, inclusive desativado.
    duplicated: int = 0
    skipped_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None


class DeckCardsRead(BaseModel):
    deck: OfficialDeckRead
    cards: list[FlashcardRead] = Field(default_factory=list)


class DeckCatalogueRead(BaseModel):
    items: list[OfficialDeckRead] = Field(default_factory=list)
    total: int = 0
    #: De onde vem esta lista, em português. Sem concurso principal escolhido ela
    #: diz isso em vez de despejar todo baralho publicado da plataforma.
    scope: str = ""
    competition_name: str | None = None
