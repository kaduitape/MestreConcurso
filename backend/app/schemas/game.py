"""Schemas da gamificação."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class LevelRead(BaseModel):
    level: int
    xp_total: int
    xp_into_level: int
    xp_for_next: int | None = None
    ratio: float
    is_max: bool


class RankComponentRead(BaseModel):
    key: str
    label: str
    weight: float
    # Nulo quando o sinal ainda não tem amostra.
    value: float | None = None
    points: float
    available: bool
    detail: str


class RankRead(BaseModel):
    slug: str
    name: str
    color_token: str
    score: float
    # As contribuições somam exatamente o score exibido.
    components: list[RankComponentRead] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    coverage: float
    next_tier: str | None = None
    next_tier_name: str | None = None
    progress_to_next: float = 0.0


class StreakRead(BaseModel):
    current: int
    longest: int
    average: float
    active_days: int
    shields_left: int
    last_qualified_on: date | None = None
    history: list[dict[str, Any]] = Field(default_factory=list)
    # Texto factual, sem linguagem de ameaça.
    message: str


class ProfileRead(BaseModel):
    level: LevelRead
    rank: RankRead
    streak: StreakRead
    xp_today: int
    missions_completed: int
    achievements_count: int
    # Números reais do candidato — nenhum estimado.
    metrics: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime | None = None
    # O Mestre Score chega na Fase 9; o lugar dele é declarado, não inventado.
    master_score: int | None = None
    master_score_note: str


class MissionRead(BaseModel):
    model_config = _READ

    public_id: str
    scope: str
    kind: str
    title: str
    description: str
    target_metric: str
    target_value: int
    current_value: int
    progress_ratio: float
    xp_reward: int
    priority: str
    difficulty: str
    estimated_minutes: int
    status: str
    # O número real que gerou a missão.
    rationale: str
    valid_from: date


class DailyBoardRead(BaseModel):
    missions: list[MissionRead] = Field(default_factory=list)
    completed: int
    total: int
    bonus_xp: int
    bonus_claimed: bool
    all_done: bool
    xp_today: int
    has_plan: bool
    empty_reason: str | None = None


class ClaimResultRead(BaseModel):
    mission: MissionRead
    xp_awarded: int
    leveled_up: bool
    level: int
    bonus: dict[str, Any] | None = None


class AchievementRead(BaseModel):
    slug: str
    name: str
    description: str
    category: str
    icon: str
    tier: str
    xp_reward: int
    is_secret: bool
    unlocked: bool
    unlocked_at: datetime | None = None
    current: float = 0
    threshold: float = 0
    # Nulo quando há condição adicional não atendida — progresso sozinho enganaria.
    ratio: float | None = None
    blocked_reason: str | None = None


class AchievementListRead(BaseModel):
    items: list[AchievementRead] = Field(default_factory=list)
    unlocked_count: int
    total_visible: int
    secret_count: int
    secret_unlocked: int


class XPTransactionRead(BaseModel):
    model_config = _READ

    public_id: str
    event_kind: str
    amount: int
    reason: str
    capped: bool
    cap_reason: str | None = None
    day: date
    created_at: datetime


class GameRuleRead(BaseModel):
    model_config = _READ

    key: str
    label: str
    xp_value: int
    daily_cap: int
    is_enabled: bool
    updated_at: datetime


class GameRuleUpdate(BaseModel):
    xp_value: int | None = Field(default=None, ge=0, le=5000)
    daily_cap: int | None = Field(default=None, ge=0, le=20000)
    is_enabled: bool | None = None


# --------------------------------------------------------------------------- #
# Fase 2 — telas comparativas
# --------------------------------------------------------------------------- #
class RankPointRead(BaseModel):
    day: date
    rank_slug: str
    rank_score: float
    # XP aparece ao lado do rank para mostrar a diferença entre acumular e dominar.
    xp_total: int
    level: int


class RankHistoryRead(BaseModel):
    points: list[RankPointRead] = Field(default_factory=list)
    first: RankPointRead | None = None
    last: RankPointRead | None = None
    # Nulo com menos de duas fotos: uma medição não é uma tendência.
    delta: float | None = None
    empty_reason: str | None = None


class SubjectScoreRead(BaseModel):
    subject_id: int | None = None
    subject_name: str
    answers: int
    correct: int
    you: int
    board: int
    is_sufficient: bool
    insufficient_reason: str | None = None


class WeekPointRead(BaseModel):
    week_start: date
    answers: int
    accuracy: float


class BoardBattleRead(BaseModel):
    board_slug: str
    board_name: str
    answers: int
    correct: int
    # you + board somam 100 quando há placar.
    you: int
    board: int
    is_sufficient: bool
    is_winning: bool
    subjects: list[SubjectScoreRead] = Field(default_factory=list)
    evolution: list[WeekPointRead] = Field(default_factory=list)
    empty_reason: str | None = None


class MilestoneRead(BaseModel):
    key: str
    label: str
    description: str
    state: str
    current: float
    target: float
    ratio: float
    detail: str


class JourneyRead(BaseModel):
    milestones: list[MilestoneRead] = Field(default_factory=list)
    current_key: str | None = None
    completed: int
    total: int
    days_until_exam: int | None = None
    # Obrigatório na tela: a jornada não prevê aprovação.
    disclaimer: str
    empty_reason: str | None = None


class TerritoryPartRead(BaseModel):
    key: str
    label: str
    weight: float
    value: float | None = None
    points: float
    available: bool
    detail: str


class TerritoryRead(BaseModel):
    subject_key: str
    subject_name: str
    color_token: str
    subject_id: int | None = None
    state: str
    mastery: float
    parts: list[TerritoryPartRead] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    studied_minutes: int
    planned_minutes: int
    days_since_studied: int | None = None
    note: str


class TerritoryMapRead(BaseModel):
    territories: list[TerritoryRead] = Field(default_factory=list)
    mastered: int = 0
    needs_review: int = 0
    empty_reason: str | None = None
