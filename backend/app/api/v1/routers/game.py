"""Gamificação: perfil, missões, conquistas e extrato de XP."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, RequestCtx, rate_limit, require_permissions
from app.api.v1.routers.questions import question_read
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.domain.game import ACHIEVEMENTS_BY_SLUG, MODES, MODES_BY_KEY, evaluate
from app.models.audit import AuditAction
from app.models.game import GameRun, Mission, SeasonParticipation
from app.models.user import User
from app.repositories.game import AchievementRepository, GameRuleRepository
from app.schemas.game import (
    AchievementListRead,
    AchievementRead,
    BoardBattleRead,
    ChallengeModeRead,
    ClaimResultRead,
    DailyBoardRead,
    GameRuleRead,
    GameRuleUpdate,
    JourneyRead,
    LeagueMemberRead,
    LeaguePreferencesRead,
    LeaguePreferencesUpdate,
    LeagueRead,
    LevelRead,
    MilestoneRead,
    MissionRead,
    ProfileRead,
    RankComponentRead,
    RankHistoryRead,
    RankPointRead,
    RankRead,
    RunAnswerResultRead,
    RunHistoryRead,
    RunRead,
    RunScoreRead,
    RunStateRead,
    ScoreLineRead,
    SeasonCreate,
    SeasonHistoryRead,
    SeasonRead,
    SeasonRewardRead,
    SeasonStandingRead,
    StreakRead,
    SubjectScoreRead,
    TerritoryMapRead,
    TerritoryPartRead,
    TerritoryRead,
    WeekPointRead,
    XPTransactionRead,
)
from app.schemas.question import SaveAnswerInput
from app.services.audit import AuditService
from app.services.game_challenges import ChallengeService, RunView
from app.services.game_engine import GameEngine
from app.services.game_missions import MissionService
from app.services.game_progress import DEFAULT_HISTORY_DAYS, GameProgressService
from app.services.game_seasons import SeasonService

router = APIRouter(tags=["gamificação"])
game_router = APIRouter(prefix="/game", tags=["gamificação"])
admin_router = APIRouter(prefix="/admin/game", tags=["admin · gamificação"])

GameAdmin = Annotated[User, Depends(require_permissions(perms.INTELLIGENCE_WRITE))]
PageDep = Annotated[PageParams, Depends(page_params)]

# O Mestre Score pertence à Fase 9 e ainda não existe. Declaramos isso em vez de
# exibir um número inventado no lugar dele.
MASTER_SCORE_NOTE = (
    "O Mestre Score chega na Fase 9 (Analytics). Ele medirá competência real e "
    "não será alimentado por XP."
)


def _mission_read(mission: Mission) -> MissionRead:
    return MissionRead(
        public_id=mission.public_id,
        scope=mission.scope,
        kind=mission.kind,
        title=mission.title,
        description=mission.description,
        target_metric=mission.target_metric,
        target_value=mission.target_value,
        current_value=mission.current_value,
        progress_ratio=mission.progress_ratio,
        xp_reward=mission.xp_reward,
        priority=mission.priority,
        difficulty=mission.difficulty,
        estimated_minutes=mission.estimated_minutes,
        status=mission.status,
        rationale=mission.rationale,
        valid_from=mission.valid_from,
    )


def _reward_read(item: dict[str, Any] | Any) -> SeasonRewardRead:
    """Aceita tanto o objeto do domínio quanto a cópia congelada no banco."""
    if isinstance(item, dict):
        return SeasonRewardRead(
            slug=item["slug"],
            label=item["label"],
            utility=item["utility"],
            criterion=item["criterion"],
        )
    return SeasonRewardRead(
        slug=item.slug, label=item.label, utility=item.utility, criterion=item.criterion
    )


def _run_read(view: RunView) -> RunRead:
    state = view.state
    return RunRead(
        public_id=view.run.public_id,
        mode=view.run.mode,
        mode_name=view.spec.name,
        status=view.run.status,
        subject_label=view.run.subject_label,
        selection=view.run.selection or {},
        state=RunStateRead(
            answered=state.answered,
            correct=state.correct,
            wrong=state.wrong,
            lives_left=state.lives_left,
            combo=state.combo,
            best_combo=state.best_combo,
            multiplier=state.multiplier,
            elapsed_seconds=state.elapsed_seconds,
            seconds_left=state.seconds_left,
            questions_left=state.questions_left,
            accuracy=state.accuracy,
            is_over=state.is_over,
            over_reason=state.over_reason,
        ),
        question=question_read(view.question) if view.question else None,
        score=(
            RunScoreRead(
                score=view.score.score,
                xp=view.score.xp,
                achieved=view.score.achieved,
                headline=view.score.headline,
                breakdown=[
                    ScoreLineRead(label=line.label, value=line.value)
                    for line in view.score.breakdown
                ],
            )
            if view.score
            else None
        ),
        xp_awarded=view.run.xp_awarded,
        started_at=view.run.started_at,
        ended_at=view.run.ended_at,
    )


def _run_history_read(run: GameRun) -> RunHistoryRead:
    return RunHistoryRead(
        public_id=run.public_id,
        mode=run.mode,
        mode_name=MODES_BY_KEY[run.mode].name if run.mode in MODES_BY_KEY else run.mode,
        status=run.status,
        score=run.score,
        best_combo=run.best_combo,
        xp_awarded=run.xp_awarded,
        achieved=run.achieved,
        subject_label=run.subject_label,
        summary=run.summary or {},
        ended_at=run.ended_at,
    )


def _participation_read(record: SeasonParticipation, season_name: str) -> SeasonHistoryRead:
    return SeasonHistoryRead(
        season_name=season_name,
        context_label=record.context_label,
        seasonal_xp=record.seasonal_xp,
        qualified_days=record.qualified_days,
        position=record.position,
        participants=record.participants,
        rewards=[_reward_read(item) for item in record.rewards or []],
        closed_at=record.closed_at,
    )


@game_router.get("/profile", response_model=ProfileRead, summary="Meu perfil de progresso")
async def profile(user: CurrentUser, db: DbSession) -> ProfileRead:
    snapshot = await GameEngine(db).snapshot(user)
    level = snapshot["level"]
    rank = snapshot["rank"]
    streak = snapshot["streak"]
    stored = snapshot["profile"]

    return ProfileRead(
        level=LevelRead(
            level=level.level,
            xp_total=level.xp_total,
            xp_into_level=level.xp_into_level,
            xp_for_next=level.xp_for_next,
            ratio=level.ratio,
            is_max=level.is_max,
        ),
        rank=RankRead(
            slug=rank.slug,
            name=rank.name,
            color_token=rank.color_token,
            score=rank.score,
            components=[
                RankComponentRead(
                    key=item.key,
                    label=item.label,
                    weight=item.weight,
                    value=item.value,
                    points=item.points,
                    available=item.available,
                    detail=item.detail,
                )
                for item in rank.components
            ],
            missing_signals=list(rank.missing_signals),
            coverage=rank.coverage,
            next_tier=rank.next_tier.slug if rank.next_tier else None,
            next_tier_name=rank.next_tier.name if rank.next_tier else None,
            progress_to_next=rank.progress_to_next,
        ),
        streak=StreakRead(
            current=streak.current,
            longest=streak.longest,
            average=streak.average,
            active_days=streak.active_days,
            shields_left=streak.shields_left,
            last_qualified_on=streak.last_qualified_on,
            history=list(streak.history),
            message=streak.message,
        ),
        xp_today=snapshot["xp_today"],
        missions_completed=stored.missions_completed,
        achievements_count=stored.achievements_count,
        metrics=snapshot["metrics"],
        computed_at=stored.computed_at,
        master_score=None,
        master_score_note=MASTER_SCORE_NOTE,
    )


@game_router.get("/missions/today", response_model=DailyBoardRead, summary="Missões de hoje")
async def missions_today(user: CurrentUser, db: DbSession) -> DailyBoardRead:
    board = await MissionService(db).board(user)
    return DailyBoardRead(
        missions=[_mission_read(item) for item in board.missions],
        completed=board.completed,
        total=board.total,
        bonus_xp=board.bonus_xp,
        bonus_claimed=board.bonus_claimed,
        all_done=board.all_done,
        xp_today=board.xp_today,
        has_plan=board.has_plan,
        empty_reason=board.empty_reason,
    )


@game_router.post(
    "/missions/{public_id}/claim",
    response_model=ClaimResultRead,
    summary="Resgatar o XP de uma missão concluída",
    dependencies=[Depends(rate_limit("60/hour", scope="game:claim"))],
)
async def claim_mission(public_id: str, user: CurrentUser, db: DbSession) -> ClaimResultRead:
    result = await MissionService(db).claim(user, public_id)
    return ClaimResultRead(
        mission=_mission_read(result["mission"]),
        xp_awarded=result["xp_awarded"],
        leveled_up=result["leveled_up"],
        level=result["level"],
        bonus=result["bonus"],
    )


@game_router.get("/achievements", response_model=AchievementListRead, summary="Minhas conquistas")
async def achievements(user: CurrentUser, db: DbSession) -> AchievementListRead:
    """Conquista secreta só aparece depois de desbloqueada."""
    engine = GameEngine(db)
    metrics = await engine.collect_metrics(user)
    streak = await engine.streak_state(user)
    metrics = {**metrics, "current_streak": streak.current}

    unlocked_rows = list(await AchievementRepository(db).unlocked_for(user.id))
    unlocked_at = {row.achievement.slug: row.unlocked_at for row in unlocked_rows}
    already = set(unlocked_at)

    result = evaluate(metrics, already_unlocked=already)
    items: list[AchievementRead] = []
    secret_unlocked = 0

    for progress in result.progress:
        spec = progress.spec
        is_unlocked = spec.slug in already or progress.unlocked
        if spec.is_secret:
            if is_unlocked:
                secret_unlocked += 1
            else:
                # Não revelamos o que ainda não aconteceu.
                continue
        items.append(
            AchievementRead(
                slug=spec.slug,
                name=spec.name,
                description=spec.description,
                category=spec.category,
                icon=spec.icon,
                tier=spec.tier,
                xp_reward=spec.xp_reward,
                is_secret=spec.is_secret,
                unlocked=is_unlocked,
                unlocked_at=unlocked_at.get(spec.slug),
                current=progress.current,
                threshold=spec.threshold,
                ratio=progress.ratio,
                blocked_reason=progress.blocked_reason,
            )
        )

    secret_total = len([item for item in ACHIEVEMENTS_BY_SLUG.values() if item.is_secret])
    return AchievementListRead(
        items=items,
        unlocked_count=len([item for item in items if item.unlocked]) + secret_unlocked,
        total_visible=len(items),
        secret_count=secret_total,
        secret_unlocked=secret_unlocked,
    )


@game_router.get("/xp/history", response_model=Page[XPTransactionRead], summary="Extrato de XP")
async def xp_history(user: CurrentUser, db: DbSession, params: PageDep) -> Page[XPTransactionRead]:
    """O razão é visível ao candidato: cada ponto tem origem declarada."""
    rows, total = await GameEngine(db).transactions.history(
        user.id, limit=params.page_size, offset=params.offset
    )
    return Page.create([XPTransactionRead.model_validate(item) for item in rows], total, params)


@game_router.get("/streak", response_model=StreakRead, summary="Minha sequência")
async def streak(user: CurrentUser, db: DbSession) -> StreakRead:
    state = await GameEngine(db).streak_state(user)
    return StreakRead(
        current=state.current,
        longest=state.longest,
        average=state.average,
        active_days=state.active_days,
        shields_left=state.shields_left,
        last_qualified_on=state.last_qualified_on,
        history=list(state.history),
        message=state.message,
    )


# --------------------------------------------------------------------------- #
# Fase 2 — telas comparativas
# --------------------------------------------------------------------------- #
@game_router.get("/rank/history", response_model=RankHistoryRead, summary="Evolução do meu rank")
async def rank_history(
    user: CurrentUser,
    db: DbSession,
    days: Annotated[int, Query(ge=7, le=365)] = DEFAULT_HISTORY_DAYS,
) -> RankHistoryRead:
    """O rank ao longo do tempo — inclusive quando ele cai."""
    history = await GameProgressService(db).rank_history(user, days=days)
    points = [
        RankPointRead(
            day=item.day,
            rank_slug=item.rank_slug,
            rank_score=item.rank_score,
            xp_total=item.xp_total,
            level=item.level,
        )
        for item in history.points
    ]
    return RankHistoryRead(
        points=points,
        first=points[0] if points else None,
        last=points[-1] if points else None,
        delta=history.delta,
        empty_reason=history.empty_reason,
    )


@game_router.get("/board-battle", response_model=BoardBattleRead, summary="Você vs Banca")
async def board_battle(user: CurrentUser, db: DbSession) -> BoardBattleRead:
    """Placar real contra a banca do concurso-alvo: os pontos dela são seus erros."""
    battle = await GameProgressService(db).board_battle(user)
    return BoardBattleRead(
        board_slug=battle.board_slug,
        board_name=battle.board_name,
        answers=battle.answers,
        correct=battle.correct,
        you=battle.you,
        board=battle.board,
        is_sufficient=battle.is_sufficient,
        is_winning=battle.is_winning,
        subjects=[
            SubjectScoreRead(
                subject_id=item.subject_id,
                subject_name=item.subject_name,
                answers=item.answers,
                correct=item.correct,
                you=item.you,
                board=item.board,
                is_sufficient=item.is_sufficient,
                insufficient_reason=item.insufficient_reason,
            )
            for item in battle.subjects
        ],
        evolution=[
            WeekPointRead(week_start=item.week_start, answers=item.answers, accuracy=item.accuracy)
            for item in battle.evolution
        ],
        empty_reason=battle.empty_reason,
    )


@game_router.get("/journey", response_model=JourneyRead, summary="Jornada da aprovação")
async def journey(user: CurrentUser, db: DbSession) -> JourneyRead:
    """Marcos com critério verificável. Nenhum deles prevê aprovação."""
    result = await GameProgressService(db).journey(user)
    return JourneyRead(
        milestones=[
            MilestoneRead(
                key=item.key,
                label=item.label,
                description=item.description,
                state=item.state,
                current=item.current,
                target=item.target,
                ratio=item.ratio,
                detail=item.detail,
            )
            for item in result.milestones
        ],
        current_key=result.current_key,
        completed=result.completed,
        total=result.total,
        days_until_exam=result.days_until_exam,
        disclaimer=result.disclaimer,
        empty_reason=result.empty_reason,
    )


@game_router.get("/territory", response_model=TerritoryMapRead, summary="Mapa do edital")
async def territory_map(user: CurrentUser, db: DbSession) -> TerritoryMapRead:
    """Cada disciplina como território, do mais frágil ao mais consolidado."""
    territories = await GameProgressService(db).territory_map(user)
    if not territories:
        return TerritoryMapRead(
            empty_reason=(
                "O mapa é desenhado sobre as disciplinas do seu plano. Monte o plano para "
                "que os territórios existam."
            )
        )

    items = [
        TerritoryRead(
            subject_key=item.subject_key,
            subject_name=item.subject_name,
            color_token=item.color_token,
            subject_id=item.subject_id,
            state=item.state,
            mastery=item.mastery,
            parts=[
                TerritoryPartRead(
                    key=part.key,
                    label=part.label,
                    weight=part.weight,
                    value=part.value,
                    points=part.points,
                    available=part.available,
                    detail=part.detail,
                )
                for part in item.parts
            ],
            missing_signals=list(item.missing_signals),
            studied_minutes=item.studied_minutes,
            planned_minutes=item.planned_minutes,
            days_since_studied=item.days_since_studied,
            note=item.note,
        )
        for item in territories
    ]
    return TerritoryMapRead(
        territories=items,
        mastered=len([item for item in items if item.state == "MASTERED"]),
        needs_review=len([item for item in items if item.state == "NEEDS_REVIEW"]),
    )


# --------------------------------------------------------------------------- #
# Fase 3 — temporada, liga e desafios
# --------------------------------------------------------------------------- #
@game_router.get("/season", response_model=SeasonRead, summary="Temporada em curso")
async def season(user: CurrentUser, db: DbSession) -> SeasonRead:
    """A temporada mede esforço no período. Quem mede aprendizado é o rank."""
    view = await SeasonService(db).view(user)
    if view.season is None or view.window is None:
        return SeasonRead(empty_reason=view.empty_reason)

    outcome = view.outcome
    return SeasonRead(
        slug=view.season.slug,
        name=view.season.name,
        description=view.season.description,
        starts_on=view.season.starts_on,
        ends_on=view.season.ends_on,
        days_left=view.days_left,
        progress=view.progress,
        standing=SeasonStandingRead(
            seasonal_xp=view.standing.seasonal_xp,
            qualified_days=view.standing.qualified_days,
            questions=view.standing.questions,
            challenges=view.standing.challenges,
            position=view.standing.position,
            participants=view.standing.participants,
        ),
        rewards=[_reward_read(item) for item in (outcome.rewards if outcome else [])],
        missed_rewards=[_reward_read(item) for item in (outcome.missed if outcome else [])],
        note=outcome.note if outcome else "",
    )


@game_router.get(
    "/season/history",
    response_model=list[SeasonHistoryRead],
    summary="Temporadas anteriores",
)
async def season_history(user: CurrentUser, db: DbSession) -> list[SeasonHistoryRead]:
    service = SeasonService(db)
    records = await service.history(user)
    result: list[SeasonHistoryRead] = []
    for record in records:
        stored = await service.seasons.get(record.season_id)
        result.append(_participation_read(record, stored.name if stored else ""))
    return result


@game_router.get("/league", response_model=LeagueRead, summary="Minha liga")
async def league(user: CurrentUser, db: DbSession) -> LeagueRead:
    """Comparação entre candidatos ao mesmo cargo — e só entre eles (item 21)."""
    result = await SeasonService(db).league(user)
    return LeagueRead(
        context_label=result.context_label,
        participants=result.participants,
        division_index=result.division_index,
        division_label=result.division_label,
        members=[
            LeagueMemberRead(
                position=item.position,
                label=item.label,
                seasonal_xp=item.seasonal_xp,
                active_days=item.active_days,
                is_you=item.is_you,
                is_named=item.is_named,
            )
            for item in result.members
        ],
        your_position=result.your_position,
        your_division_position=result.your_division_position,
        note=result.note,
        empty_reason=result.empty_reason,
    )


@game_router.get(
    "/league/preferences",
    response_model=LeaguePreferencesRead,
    summary="Minhas preferências de comparação",
)
async def league_preferences(user: CurrentUser, db: DbSession) -> LeaguePreferencesRead:
    profile = await GameEngine(db).profile_for(user)
    return LeaguePreferencesRead(
        opt_out=profile.league_opt_out, display_name=profile.league_display_name
    )


@game_router.put(
    "/league/preferences",
    response_model=LeaguePreferencesRead,
    summary="Ligar, desligar ou identificar-se na comparação",
)
async def update_league_preferences(
    payload: LeaguePreferencesUpdate, user: CurrentUser, db: DbSession
) -> LeaguePreferencesRead:
    """Sair da comparação não afeta nada do estudo — e o anonimato é o padrão."""
    profile = await SeasonService(db).set_preferences(
        user, opt_out=payload.opt_out, display_name=payload.display_name
    )
    return LeaguePreferencesRead(
        opt_out=profile.league_opt_out, display_name=profile.league_display_name
    )


@game_router.get(
    "/challenges/modes", response_model=list[ChallengeModeRead], summary="Modos de desafio"
)
async def challenge_modes() -> list[ChallengeModeRead]:
    return [
        ChallengeModeRead(
            mode=item.mode,
            name=item.name,
            description=item.description,
            questions=item.questions,
            lives=item.lives,
            time_limit_seconds=item.time_limit_seconds,
            rule=item.rule,
        )
        for item in MODES
    ]


@game_router.get(
    "/challenges/current", response_model=RunRead | None, summary="Rodada em andamento"
)
async def current_run(user: CurrentUser, db: DbSession) -> RunRead | None:
    view = await ChallengeService(db).current(user)
    return _run_read(view) if view else None


@game_router.post(
    "/challenges/{mode}",
    response_model=RunRead,
    status_code=201,
    summary="Começar uma rodada",
    dependencies=[Depends(rate_limit("60/hour", scope="game:run"))],
)
async def start_run(mode: str, user: CurrentUser, db: DbSession) -> RunRead:
    """Sem questões suficientes no banco, a rodada não é criada — e o motivo é dito."""
    return _run_read(await ChallengeService(db).start(user, mode.upper()))


@game_router.get("/challenges/runs/{public_id}", response_model=RunRead, summary="Estado da rodada")
async def run_state(public_id: str, user: CurrentUser, db: DbSession) -> RunRead:
    return _run_read(await ChallengeService(db).view(user, public_id))


@game_router.post(
    "/challenges/runs/{public_id}/answer",
    response_model=RunAnswerResultRead,
    summary="Responder a questão da vez",
)
async def answer_run(
    public_id: str, payload: SaveAnswerInput, user: CurrentUser, db: DbSession
) -> RunAnswerResultRead:
    view, feedback = await ChallengeService(db).answer(
        user, public_id, letter=payload.letter, time_seconds=payload.time_seconds
    )
    return RunAnswerResultRead(
        run=_run_read(view),
        is_correct=feedback.attempt.is_correct,
        correct_letter=feedback.correct_letter,
        selected_feedback=feedback.selected_feedback,
        correct_feedback=feedback.correct_feedback,
        explanation=feedback.explanation,
    )


@game_router.post(
    "/challenges/runs/{public_id}/finish", response_model=RunRead, summary="Encerrar a rodada"
)
async def finish_run(
    public_id: str,
    user: CurrentUser,
    db: DbSession,
    abandon: Annotated[bool, Query()] = False,
) -> RunRead:
    """Rodada abandonada não pontua: parar no meio não é desempenho."""
    return _run_read(await ChallengeService(db).finish(user, public_id, abandoned=abandon))


@game_router.get(
    "/challenges/history", response_model=list[RunHistoryRead], summary="Rodadas anteriores"
)
async def run_history(user: CurrentUser, db: DbSession) -> list[RunHistoryRead]:
    return [_run_history_read(item) for item in await ChallengeService(db).history(user)]


# --------------------------------------------------------------------------- #
# Administração das regras
# --------------------------------------------------------------------------- #
@admin_router.get("/rules", response_model=list[GameRuleRead], summary="Regras de pontuação")
async def list_rules(_: GameAdmin, db: DbSession) -> list[GameRuleRead]:
    engine = GameEngine(db)
    await engine.sync_rules()
    rows = await GameRuleRepository(db).all_rules()
    return [GameRuleRead.model_validate(item) for item in rows]


@admin_router.put(
    "/rules/{key}", response_model=GameRuleRead, summary="Editar uma regra de pontuação"
)
async def update_rule(
    key: str, payload: GameRuleUpdate, actor: GameAdmin, db: DbSession, ctx: RequestCtx
) -> GameRuleRead:
    """Altera valor, teto e liga/desliga — sem deploy, com auditoria."""
    repository = GameRuleRepository(db)
    await GameEngine(db).sync_rules()
    rule = await repository.get_by_key(key)
    if rule is None:
        raise NotFoundError("Regra não encontrada.")

    before = {
        "xp_value": rule.xp_value,
        "daily_cap": rule.daily_cap,
        "is_enabled": rule.is_enabled,
    }
    data = payload.model_dump(exclude_unset=True)
    for field_name, value in data.items():
        if value is not None:
            setattr(rule, field_name, value)
    rule.updated_by_user_id = actor.id

    await AuditService(db).record(
        AuditAction.GAME_RULE_UPDATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="game_rule",
        resource_id=key,
        meta={"before": before, "after": data},
    )
    await db.commit()
    stored = await repository.get_fresh(key)
    assert stored is not None
    return GameRuleRead.model_validate(stored)


@admin_router.post(
    "/seasons", response_model=SeasonRead, status_code=201, summary="Abrir uma temporada"
)
async def create_season(payload: SeasonCreate, _: GameAdmin, db: DbSession) -> SeasonRead:
    """Temporadas são períodos definidos pela administração, não janelas implícitas."""
    season_row = await SeasonService(db).create(
        name=payload.name,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        description=payload.description,
    )
    return SeasonRead(
        slug=season_row.slug,
        name=season_row.name,
        description=season_row.description,
        starts_on=season_row.starts_on,
        ends_on=season_row.ends_on,
    )


@admin_router.post(
    "/seasons/{slug}/close",
    response_model=list[SeasonHistoryRead],
    summary="Fechar a temporada e conceder os prêmios",
)
async def close_season(slug: str, _: GameAdmin, db: DbSession) -> list[SeasonHistoryRead]:
    """Congela as posições e concede o que o critério de cada prêmio já garantia."""
    service = SeasonService(db)
    records = await service.close(slug)
    stored = await service.seasons.get_by_slug(slug)
    return [_participation_read(item, stored.name if stored else "") for item in records]


router.include_router(game_router)
router.include_router(admin_router)
