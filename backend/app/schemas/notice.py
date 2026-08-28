"""Schemas de editais."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class NoticeFileRead(BaseModel):
    model_config = _READ

    public_id: str
    original_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    page_count: int | None = None
    status: str
    error_message: str | None = None
    created_at: datetime


class NoticeRead(BaseModel):
    model_config = _READ

    public_id: str
    title: str
    kind: str
    number: str | None = None
    published_at: datetime | None = None
    source_url: str | None = None
    status: str
    summary: str | None = None
    created_at: datetime
    files: list[NoticeFileRead] = Field(default_factory=list)


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    competition_public_id: str | None = None
    kind: str = Field(default="MAIN", pattern="^(MAIN|RECTIFICATION|ADDENDUM|RESULT)$")
    number: str | None = Field(default=None, max_length=60)
    published_at: datetime | None = None
    source_url: str | None = Field(default=None, max_length=500)
    summary: str | None = None


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    kind: str | None = Field(default=None, pattern="^(MAIN|RECTIFICATION|ADDENDUM|RESULT)$")
    number: str | None = Field(default=None, max_length=60)
    published_at: datetime | None = None
    source_url: str | None = Field(default=None, max_length=500)
    summary: str | None = None


# --------------------------------------------------------------------------- #
# Análise do edital
# --------------------------------------------------------------------------- #
class AnalysisStepRead(BaseModel):
    model_config = _READ

    key: str
    label: str
    status: str
    detail: str | None = None
    at: datetime | None = None


class AnalysisStateRead(BaseModel):
    notice_public_id: str
    status: str
    steps: list[AnalysisStepRead] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    coverage: dict[str, float] = Field(default_factory=dict)


class AnalysisStartedResponse(BaseModel):
    notice_public_id: str
    status: str
    message: str
    executed_inline: bool = Field(
        description="True quando a análise rodou na própria requisição (modo eager)"
    )


class FactRead(BaseModel):
    model_config = _READ

    id: int
    field_path: str
    label: str
    value: Any = None
    evidence_level: str
    confidence: float | None = None
    page_number: int | None = None
    quote: str | None = None
    extracted_by: str
    model_slug: str | None = None
    prompt_version: str | None = None


class FactReviewInput(BaseModel):
    value: Any = Field(description="Valor correto do campo, conforme o edital")


class SubjectRead(BaseModel):
    model_config = _READ

    public_id: str
    name: str
    weight: float | None = None
    questions_count: int | None = None
    topics_count: int
    topics: list[str] = Field(default_factory=list)
    evidence_level: str
    page_number: int | None = None


class EventRead(BaseModel):
    model_config = _READ

    kind: str
    title: str
    date_start: date | None = None
    date_end: date | None = None
    is_critical: bool
    days_until: int | None = None
    evidence_level: str
    page_number: int | None = None


class AttentionPointRead(BaseModel):
    model_config = _READ

    kind: str
    title: str
    detail: str


class RadiographyRead(BaseModel):
    model_config = _READ

    """Raio-X do edital: números calculados em Python, cada um com sua prova."""

    notice_public_id: str
    title: str
    status: str
    exam_date: date | None = None
    days_until_exam: int | None = None
    page_count: int | None = None
    subjects_count: int
    topics_count: int
    questions_count: int | None = None
    vacancies: int | None = None
    salary_cents: int | None = None
    facts: list[FactRead] = Field(default_factory=list)
    subjects: list[SubjectRead] = Field(default_factory=list)
    events: list[EventRead] = Field(default_factory=list)
    critical_events: list[EventRead] = Field(default_factory=list)
    largest_subjects: list[SubjectRead] = Field(default_factory=list)
    attention_points: list[AttentionPointRead] = Field(default_factory=list)
    coverage: dict[str, float] = Field(default_factory=dict)
