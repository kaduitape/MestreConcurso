"""Schemas da gamificação."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.question import QuestionRead

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
    #: A faixa do Mestre Score. Nula enquanto não houver amostra alguma.
    master_score_low: int | None = None
    master_score_high: int | None = None
    master_score_confidence: str | None = None
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


# --------------------------------------------------------------------------- #
# Fase 3 — temporadas, ligas e desafios
# --------------------------------------------------------------------------- #
class SeasonRewardRead(BaseModel):
    slug: str
    label: str
    #: Para que serve. Prêmio sem utilidade declarada não existe aqui.
    utility: str
    criterion: str


class SeasonStandingRead(BaseModel):
    seasonal_xp: int
    qualified_days: int
    questions: int
    challenges: int
    position: int | None = None
    participants: int = 0


class SeasonRead(BaseModel):
    slug: str | None = None
    name: str | None = None
    description: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    days_left: int | None = None
    progress: float = 0.0
    standing: SeasonStandingRead | None = None
    rewards: list[SeasonRewardRead] = Field(default_factory=list)
    missed_rewards: list[SeasonRewardRead] = Field(default_factory=list)
    #: A temporada mede esforço; quem mede aprendizado é o rank.
    note: str = ""
    empty_reason: str | None = None


class SeasonHistoryRead(BaseModel):
    season_name: str
    context_label: str
    seasonal_xp: int
    qualified_days: int
    position: int | None = None
    participants: int
    rewards: list[SeasonRewardRead] = Field(default_factory=list)
    closed_at: datetime | None = None


class LeagueMemberRead(BaseModel):
    position: int
    label: str
    seasonal_xp: int
    active_days: int
    is_you: bool
    #: Falso quando o candidato optou por permanecer anônimo (o padrão).
    is_named: bool


class LeagueRead(BaseModel):
    context_label: str
    participants: int
    division_index: int = 0
    division_label: str = ""
    members: list[LeagueMemberRead] = Field(default_factory=list)
    your_position: int | None = None
    your_division_position: int | None = None
    note: str = ""
    empty_reason: str | None = None


class LeaguePreferencesUpdate(BaseModel):
    #: Desliga a comparação por completo (item 21 do pedido).
    opt_out: bool | None = None
    #: Vazio devolve ao anonimato, que é o padrão.
    display_name: str | None = Field(default=None, max_length=40)


class LeaguePreferencesRead(BaseModel):
    opt_out: bool
    display_name: str | None = None


class ChallengeModeRead(BaseModel):
    mode: str
    name: str
    description: str
    questions: int
    lives: int | None = None
    time_limit_seconds: int | None = None
    #: O critério de vitória, escrito.
    rule: str


class RunStateRead(BaseModel):
    answered: int
    correct: int
    wrong: int
    lives_left: int | None = None
    combo: int
    best_combo: int
    multiplier: float
    elapsed_seconds: int
    seconds_left: int | None = None
    questions_left: int
    #: Nulo sem resposta alguma: zero de zero não é zero por cento.
    accuracy: float | None = None
    is_over: bool
    over_reason: str | None = None


class ScoreLineRead(BaseModel):
    label: str
    value: str


class RunScoreRead(BaseModel):
    score: int
    xp: int
    achieved: bool
    headline: str
    #: A conta aberta do XP da rodada.
    breakdown: list[ScoreLineRead] = Field(default_factory=list)


class RunRead(BaseModel):
    public_id: str
    mode: str
    mode_name: str
    status: str
    subject_label: str | None = None
    #: Por que estas questões e não outras.
    selection: dict[str, Any] = Field(default_factory=dict)
    state: RunStateRead
    question: QuestionRead | None = None
    score: RunScoreRead | None = None
    xp_awarded: int = 0
    started_at: datetime
    ended_at: datetime | None = None


class RunAnswerResultRead(BaseModel):
    run: RunRead
    is_correct: bool
    correct_letter: str | None = None
    selected_feedback: str | None = None
    correct_feedback: str | None = None
    explanation: str | None = None


class RunHistoryRead(BaseModel):
    public_id: str
    mode: str
    mode_name: str
    status: str
    score: int
    best_combo: int
    xp_awarded: int
    achieved: bool
    subject_label: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    ended_at: datetime | None = None


class SeasonCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    starts_on: date
    ends_on: date | None = None
    description: str | None = Field(default=None, max_length=400)


# --------------------------------------------------------------------------- #
# Fase 4 — duelos, eventos, Modo Guerra e card compartilhável
# --------------------------------------------------------------------------- #
class DuelSideRead(BaseModel):
    display_name: str
    answered: int
    correct: int
    time_seconds: int
    finished: bool


class DuelRead(BaseModel):
    public_id: str
    #: Código curto que o candidato compartilha para convidar alguém.
    code: str
    status: str
    outcome: str
    #: A frase do resultado. Vitória por ausência é dita com esse nome.
    headline: str
    #: Como o resultado foi decidido, linha a linha.
    lines: list[str] = Field(default_factory=list)
    is_challenger: bool
    challenger: DuelSideRead
    opponent: DuelSideRead | None = None
    you_won: bool | None = None
    my_run: RunRead | None = None
    expires_at: datetime
    resolved_at: datetime | None = None


class DuelHistoryRead(BaseModel):
    public_id: str
    code: str
    status: str
    outcome: str | None = None
    headline: str = ""
    is_challenger: bool
    you_won: bool | None = None
    resolved_at: datetime | None = None


class AcceptDuelInput(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class EventGoalRead(BaseModel):
    metric: str
    label: str
    current: int
    target: int
    ratio: float
    completed: bool


class EventRead(BaseModel):
    slug: str
    name: str
    description: str | None = None
    starts_on: date
    ends_on: date
    days_left: int | None = None
    is_open: bool
    goals: list[EventGoalRead] = Field(default_factory=list)
    completed: bool
    completed_goals: int
    total_goals: int
    reward_label: str | None = None
    #: Prêmio sem utilidade declarada não é aceito na criação.
    reward_utility: str | None = None
    note: str = ""


class EventGoalInput(BaseModel):
    metric: str = Field(max_length=40)
    target: int = Field(gt=0)


class EventCreate(BaseModel):
    name: str = Field(min_length=3, max_length=140)
    starts_on: date
    ends_on: date
    goals: list[EventGoalInput] = Field(min_length=1)
    description: str | None = Field(default=None, max_length=400)
    reward_label: str | None = Field(default=None, max_length=120)
    reward_utility: str | None = Field(default=None, max_length=400)


class WarDayRead(BaseModel):
    day: date
    minutes: int
    questions: int
    met: bool
    is_future: bool


class WarCampaignRead(BaseModel):
    public_id: str | None = None
    status: str | None = None
    starts_on: date | None = None
    days: int = 0
    daily_minutes: int = 0
    daily_questions: int = 0
    days_met: int = 0
    days_missed: int = 0
    days_left: int = 0
    ratio: float = 0.0
    is_over: bool = False
    succeeded: bool = False
    #: Texto factual. Descreve o período, não julga o candidato.
    message: str = ""
    schedule: list[WarDayRead] = Field(default_factory=list)
    #: Avisos dados na criação — meta muito acima do histórico, por exemplo.
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    empty_reason: str | None = None


class WarCampaignCreate(BaseModel):
    days: int = Field(ge=1, le=60)
    daily_minutes: int = Field(ge=0, le=1440)
    daily_questions: int = Field(default=0, ge=0, le=500)


class CardStatRead(BaseModel):
    key: str
    label: str
    value: str
    #: Explica o número em uma linha (amostra, período, origem).
    detail: str


class ShareCardRead(BaseModel):
    display_name: str
    headline: str
    stats: list[CardStatRead] = Field(default_factory=list)
    #: O que ficou de fora, com o motivo.
    omitted: list[str] = Field(default_factory=list)
    footer: str


class PublishedCardRead(ShareCardRead):
    public_id: str
    #: O link só existe porque o candidato pediu, e pode ser revogado.
    token: str
    revoked_at: datetime | None = None
    created_at: datetime


class ShareCardCreate(BaseModel):
    #: O candidato escolhe o que entra. Nada é publicado por padrão.
    include: list[str] = Field(default_factory=lambda: ["level", "rank", "streak", "questions"])
    display_name: str | None = Field(default=None, max_length=80)
