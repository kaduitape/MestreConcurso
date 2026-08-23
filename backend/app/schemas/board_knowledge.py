"""Schemas do conhecimento acumulado sobre bancas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True, protected_namespaces=())


class BoardKnowledgeRead(BaseModel):
    model_config = _READ

    id: int
    kind: str
    entry_key: str
    title: str
    content: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    source: str
    confidence: Decimal | None = None
    sample_exams: int | None = None
    sample_questions: int | None = None
    period_start_year: int | None = None
    period_end_year: int | None = None
    provider_slug: str | None = None
    model_slug: str | None = None
    prompt_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    collected_at: datetime
    expires_at: datetime | None = None
    is_expired: bool = False


class BoardKnowledgeInput(BaseModel):
    kind: str = Field(
        pattern=(
            "^(PROFILE_SUMMARY|STYLE_TRAIT|TRAP_PATTERN|SUBJECT_FOCUS|QUESTION_FORMAT|STUDY_TIP)$"
        )
    )
    entry_key: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=2, max_length=200)
    content: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    source: str = Field(default="EDITORIAL", pattern="^(COMPUTED|AI|EDITORIAL|OFFICIAL)$")
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    sample_exams: int | None = Field(default=None, ge=0)
    sample_questions: int | None = Field(default=None, ge=0)
    period_start_year: int | None = Field(default=None, ge=1900, le=2100)
    period_end_year: int | None = Field(default=None, ge=1900, le=2100)
    ttl_days: int | None = Field(
        default=None, ge=1, le=3650, description="Validade; vazio = permanente"
    )


class BoardKnowledgeCoverage(BaseModel):
    total: int
    by_kind: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    expired: int = 0
    ai_tokens_stored: int = 0
