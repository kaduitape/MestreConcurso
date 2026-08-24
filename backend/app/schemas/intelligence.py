"""Schemas da camada de inteligência."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Mapa de incidência e DNA da banca
# --------------------------------------------------------------------------- #
class IncidenceRowRead(BaseModel):
    subject_name: str
    topic_name: str | None = None
    questions_count: int
    exams_count: int
    incidence_pct: float
    # Nulo quando a amostra não cobre dois anos — "estável" seria afirmação sem base.
    trend: float | None = None
    confidence: float
    board_questions_count: int


class IncidenceMapRead(BaseModel):
    board_slug: str
    board_name: str
    period_start_year: int | None = None
    period_end_year: int | None = None
    board_questions_count: int
    rows: list[IncidenceRowRead] = Field(default_factory=list)
    computed_at: datetime | None = None
    # Por que o mapa está vazio, quando estiver.
    empty_reason: str | None = None


class BoardMetricRead(BaseModel):
    metric_slug: str
    label: str
    value: float
    unit: str
    detail: dict[str, float] = Field(default_factory=dict)
    sample_questions: int
    sample_exams: int
    period_start_year: int | None = None
    period_end_year: int | None = None
    confidence: float


class BoardDnaRead(BaseModel):
    board_slug: str
    board_name: str
    metrics: list[BoardMetricRead] = Field(default_factory=list)
    computed_at: datetime | None = None
    empty_reason: str | None = None


class RecomputeResultRead(BaseModel):
    board_slug: str
    questions_sampled: int
    incidence_rows: int
    profile_metrics: int
    incidence_blocked: str | None = None
    profile_blocked: str | None = None


# --------------------------------------------------------------------------- #
# Priority Score
# --------------------------------------------------------------------------- #
class ContributionRead(BaseModel):
    key: str
    label: str
    points: int
    max_points: int
    detail: str


class PriorityRead(BaseModel):
    scope_key: str
    label: str
    color_token: str
    score: int
    contributions: list[ContributionRead] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    coverage: float
    computed_at: datetime | None = None


class PriorityListRead(BaseModel):
    items: list[PriorityRead] = Field(default_factory=list)
    computed_at: datetime | None = None
    board_slug: str | None = None
    # O que ficou de fora do cálculo e por quê.
    notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Caderno de erros
# --------------------------------------------------------------------------- #
class TrapPatternRead(BaseModel):
    model_config = _READ

    public_id: str
    slug: str
    name: str
    category: str
    description: str | None = None
    detection_hint: str | None = None


class ErrorAnalysisRead(BaseModel):
    public_id: str
    cause: str
    cause_label: str
    question_public_id: str
    question_statement: str
    subject_name: str | None = None
    selected_letter: str | None = None
    trap_slug: str | None = None
    trap_name: str | None = None
    note: str | None = None
    source: str
    model_slug: str | None = None
    rationale: str | None = None
    # Sugestão de IA aparece com isto falso e não entra em estatística alguma.
    is_confirmed: bool
    is_resolved: bool
    created_at: datetime


class PendingAttemptRead(BaseModel):
    attempt_public_id: str
    question_public_id: str
    question_statement: str
    subject_name: str | None = None
    selected_letter: str | None = None
    created_at: datetime


class ClassifyErrorInput(BaseModel):
    cause: str = Field(
        pattern="^(UNKNOWN_CONTENT|INTERPRETATION|CONFUSION|FORGETTING|RUSH|TRAP|ALTERNATIVE_DOUBT)$"
    )
    trap_slug: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=2000)


class CauseSuggestionRead(BaseModel):
    cause: str | None = None
    cause_label: str | None = None
    trap_slug: str | None = None
    confidence: float | None = None
    rationale: str | None = None
    study_tip: str | None = None
    model: str
    prompt_version: str
    confirmed: bool = False


class CauseSummaryRead(BaseModel):
    cause: str
    label: str
    count: int
    share: float
    action: str


class TrapSummaryRead(BaseModel):
    slug: str
    name: str
    count: int
    share: float


class SubjectErrorRead(BaseModel):
    subject_name: str
    count: int
    dominant_cause: str | None = None
    dominant_cause_label: str | None = None


class ErrorNotebookRead(BaseModel):
    total: int
    resolved: int
    by_cause: list[CauseSummaryRead] = Field(default_factory=list)
    by_subject: list[SubjectErrorRead] = Field(default_factory=list)
    traps: list[TrapSummaryRead] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    causes_catalogue: dict[str, Any] = Field(default_factory=dict)
