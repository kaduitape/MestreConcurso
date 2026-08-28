"""Schemas do Mestre IA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    mode: str = Field(default="TUTOR", pattern="^(TUTOR|TEACHER)$")
    notice_public_id: str | None = None
    subject_public_id: str | None = None


class ConversationRead(BaseModel):
    model_config = _READ

    public_id: str
    title: str
    mode: str
    message_count: int
    last_message_at: datetime | None = None
    created_at: datetime


class ClaimRead(BaseModel):
    text: str
    kind: str
    status: str
    quote: str | None = None
    chunk_id: int | None = None
    page_number: int | None = None
    document_title: str | None = None
    # Por que a afirmação ficou sem origem, quando for o caso.
    note: str | None = None


class SourceRead(BaseModel):
    chunk_id: int
    document_title: str
    page_number: int
    score: float
    excerpt: str


class VideoRead(BaseModel):
    model_config = _READ

    public_id: str
    title: str
    url: str
    provider: str
    channel: str | None = None
    duration_seconds: int | None = None
    summary: str | None = None
    verified_at: datetime | None = None


class MessageRead(BaseModel):
    public_id: str
    role: str
    content: str
    claims: list[ClaimRead] = Field(default_factory=list)
    sources: list[SourceRead] = Field(default_factory=list)
    computed_context: dict[str, Any] = Field(default_factory=dict)
    is_refusal: bool = False
    refusal_reason: str | None = None
    # Fração das afirmações factuais com origem conferida.
    grounding_ratio: float | None = None
    model_slug: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    created_at: datetime


class ConversationDetailRead(ConversationRead):
    messages: list[MessageRead] = Field(default_factory=list)


class AskInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class AskResultRead(BaseModel):
    message: MessageRead
    videos: list[VideoRead] = Field(default_factory=list)
    suggested_terms: list[dict[str, str]] = Field(default_factory=list)


class VocabularyCreate(BaseModel):
    term: str = Field(min_length=2, max_length=160)
    definition: str = Field(min_length=2)
    subject_public_id: str | None = None
    message_public_id: str | None = None


class VocabularyRead(BaseModel):
    model_config = _READ

    public_id: str
    term: str
    definition: str
    subject_name: str | None = None
    # CITED quando a definição herdou uma citação conferida; GENERATED quando é
    # redação do modelo. A interface não trata as duas como a mesma coisa.
    origin: str
    source_quote: str | None = None
    source_page: int | None = None
    source_document: str | None = None
    times_reviewed: int = 0
    created_at: datetime


class VideoCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    url: str = Field(min_length=8, max_length=500)
    provider: str = Field(default="YOUTUBE", max_length=40)
    channel: str | None = Field(default=None, max_length=160)
    duration_seconds: int | None = Field(default=None, ge=0, le=86400)
    subject_public_id: str | None = None
    summary: str | None = None


class VideoAdminRead(VideoRead):
    subject_name: str | None = None
    is_active: bool = True
    is_verified: bool = False
