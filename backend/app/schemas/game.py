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
