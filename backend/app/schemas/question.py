"""Schemas do banco de questões e dos simulados."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Questões
# --------------------------------------------------------------------------- #
class AlternativeRead(BaseModel):
    model_config = _READ

    public_id: str
    letter: str
    content: str


class AlternativeAdminRead(AlternativeRead):
    is_correct: bool
    feedback: str | None = None


class AlternativeInput(BaseModel):
    letter: str = Field(min_length=1, max_length=2)
    content: str = Field(min_length=1)
    is_correct: bool = False
    feedback: str | None = None


class QuestionStatsRead(BaseModel):
    attempts: int
    # Nulo enquanto a amostra for pequena: a interface mostra "dados insuficientes".
    accuracy: float | None = None
    average_time_seconds: int | None = None


class QuestionRead(BaseModel):
    """Questão como o candidato vê: sem gabarito antes de responder."""

    model_config = _READ

    public_id: str
    statement: str
    kind: str
    difficulty: str
    origin: str
    year: int | None = None
    subject_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    alternatives: list[AlternativeRead] = Field(default_factory=list)
    stats: QuestionStatsRead | None = None


class QuestionAdminRead(BaseModel):
    model_config = _READ

    public_id: str
    statement: str
    kind: str
    difficulty: str
    origin: str
    status: str
    year: int | None = None
    subject_name: str | None = None
    explanation: str | None = None
    source_note: str | None = None
    tags: list[str] = Field(default_factory=list)
    alternatives: list[AlternativeAdminRead] = Field(default_factory=list)
    ai_suggestion: dict[str, Any] = Field(default_factory=dict)
    stats: QuestionStatsRead | None = None
    created_at: datetime


class QuestionCreate(BaseModel):
    statement: str = Field(min_length=10)
    alternatives: list[AlternativeInput]
    kind: str = Field(
        default="MULTIPLE_CHOICE", pattern="^(MULTIPLE_CHOICE|TRUE_FALSE|DISCURSIVE)$"
    )
    difficulty: str = Field(default="MEDIUM", pattern="^(EASY|MEDIUM|HARD)$")
    origin: str = Field(default="OFFICIAL", pattern="^(OFFICIAL|AI_GENERATED|EDITORIAL)$")
    status: str = Field(default="PUBLISHED", pattern="^(DRAFT|PUBLISHED|ARCHIVED|NEEDS_REVIEW)$")
    year: int | None = Field(default=None, ge=1990, le=2100)
    explanation: str | None = None
    source_note: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list)
    subject_public_id: str | None = None
    exam_public_id: str | None = None
    board_slug: str | None = None


class QuestionUpdate(BaseModel):
    statement: str | None = Field(default=None, min_length=10)
    difficulty: str | None = Field(default=None, pattern="^(EASY|MEDIUM|HARD)$")
    status: str | None = Field(default=None, pattern="^(DRAFT|PUBLISHED|ARCHIVED|NEEDS_REVIEW)$")
    explanation: str | None = None
    tags: list[str] | None = None
    subject_public_id: str | None = None


class QuestionImportInput(BaseModel):
    questions: list[dict[str, Any]] = Field(min_length=1)
    subject_public_id: str | None = None
    exam_public_id: str | None = None
    board_slug: str | None = None


class ImportSummaryRead(BaseModel):
    created: int
    skipped_duplicates: int
    errors: list[str] = Field(default_factory=list)


class ClassificationSuggestionRead(BaseModel):
    subject: str | None = None
    topic: str | None = None
    difficulty: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = None
    rationale: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    applied: bool = False


class ApplyClassificationInput(BaseModel):
    subject_public_id: str | None = None
    difficulty: str | None = Field(default=None, pattern="^(EASY|MEDIUM|HARD)$")


class ExamCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    year: int = Field(ge=1990, le=2100)
    board_slug: str | None = None
    phase: str | None = Field(default=None, max_length=60)
    applied_on: date | None = None
    questions_count: int | None = Field(default=None, ge=0, le=500)
    duration_minutes: int | None = Field(default=None, ge=0, le=1440)
    source_url: str | None = Field(default=None, max_length=500)


class ExamRead(BaseModel):
    model_config = _READ

    public_id: str
    name: str
    year: int
    phase: str | None = None
    applied_on: date | None = None
    questions_count: int | None = None
    duration_minutes: int | None = None
    is_official: bool


# --------------------------------------------------------------------------- #
# Prática
# --------------------------------------------------------------------------- #
class AnswerInputSchema(BaseModel):
    letter: str | None = Field(default=None, max_length=2)
    time_seconds: int = Field(default=0, ge=0, le=3600)
    confidence: str | None = Field(default=None, pattern="^(GUESS|LOW|MEDIUM|HIGH)$")


class AnswerFeedbackRead(BaseModel):
    """Correção de uma questão: por que a certa está certa e a marcada não."""

    is_correct: bool
    is_blank: bool
    selected_letter: str | None = None
    correct_letter: str | None = None
    correct_feedback: str | None = None
    selected_feedback: str | None = None
    explanation: str | None = None
    time_seconds: int = 0


class AttemptHistoryRead(BaseModel):
    model_config = _READ

    public_id: str
    question_public_id: str = ""
    question_statement: str = ""
    selected_letter: str | None = None
    is_correct: bool
    is_blank: bool
    time_seconds: int
    created_at: datetime


# --------------------------------------------------------------------------- #
# Simulados
# --------------------------------------------------------------------------- #
class SimulationCreate(BaseModel):
    kind: str = Field(
        default="CUSTOM",
        pattern="^(OFFICIAL|BOARD|ERRORS|FINAL_STRETCH|FLASH|CUSTOM|ADAPTIVE)$",
    )
    questions_count: int = Field(default=20, ge=5, le=180)
    subject_public_id: str | None = None
    board_slug: str | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=480)


class SimulationRead(BaseModel):
    model_config = _READ

    public_id: str
    kind: str
    name: str
    questions_count: int
    duration_minutes: int | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SimulationAttemptRead(BaseModel):
    model_config = _READ

    public_id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    elapsed_seconds: int
    correct_count: int
    wrong_count: int
    blank_count: int
    score: float | None = None
    simulation: SimulationRead | None = None
    analysis: dict[str, Any] = Field(default_factory=dict)


class SimulationQuestionRead(BaseModel):
    order_index: int
    question: QuestionRead
    selected_letter: str | None = None


class SimulationRunRead(BaseModel):
    """Estado completo da execução, suficiente para retomar de onde parou."""

    attempt: SimulationAttemptRead
    questions: list[SimulationQuestionRead] = Field(default_factory=list)
    remaining_seconds: int | None = None


class SaveAnswerInput(BaseModel):
    question_public_id: str
    letter: str | None = Field(default=None, max_length=2)
    time_seconds: int = Field(default=0, ge=0, le=3600)
