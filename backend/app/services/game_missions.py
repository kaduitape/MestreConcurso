"""Missões do dia: geradas de sinal real, medidas por atividade real.

Duas escolhas que sustentam a honestidade da Central:

* **nada de marcar missão à mão.** O progresso é recontado a partir do que o
  candidato fez — cartões revisados, erros classificados, minutos de foco. Uma
  caixinha de "concluído" clicável mediria disposição de clicar;
* **missão vencida expira.** Empilhar missão de ontem repetiria o erro que a
  Fase 8 evitou na revisão: fila que vira dívida faz a pessoa desistir.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.game import (
    GameEvent,
    GameEventKind,
    MissionSignals,
    daily_bonus_xp,
    generate_daily,
)
from app.models.flashcard import CardMemoryState, FlashcardReview
from app.models.game import Mission, MissionScope, MissionStatus
from app.models.intelligence import ErrorAnalysis, UserPriority
from app.models.question import QuestionAttempt
from app.models.study import (
    StudyPlan,
    StudyPlanStatus,
    StudySession,
    StudyTask,
    StudyTaskStatus,
)
from app.models.user import User
from app.repositories.game import MissionRepository
from app.services.game_engine import GameEngine

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DailyBoard:
    missions: list[Mission]
    bonus_xp: int
    bonus_claimed: bool
    xp_today: int
    completed: int
    total: int
    has_plan: bool
    # Motivo pelo qual não há missão, quando for o caso.
    empty_reason: str | None = None

    @property
    def all_done(self) -> bool:
        return self.total > 0 and self.completed == self.total


class MissionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.missions = MissionRepository(session)
        self.engine = GameEngine(session)

    # ------------------------------------------------------------------ #
    # Sinais
    # ------------------------------------------------------------------ #
    async def _signals(self, user: User, day: date) -> MissionSignals:
        plan = (
            (
                await self.session.execute(
                    select(StudyPlan)
                    .where(
                        StudyPlan.user_id == user.id,
                        StudyPlan.status == StudyPlanStatus.ACTIVE,
                    )
                    .order_by(StudyPlan.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
        if plan is None:
            return MissionSignals(has_plan=False)

        due_cards = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        CardMemoryState.user_id == user.id, CardMemoryState.due_on <= day
                    )
                )
            ).scalar_one()
        )

        classified = select(ErrorAnalysis.question_attempt_id).where(
            ErrorAnalysis.user_id == user.id
        )
        unclassified = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        QuestionAttempt.user_id == user.id,
                        QuestionAttempt.is_correct.is_(False),
                        QuestionAttempt.id.notin_(classified),
                    )
                )
            ).scalar_one()
        )

        top = (
            (
                await self.session.execute(
                    select(UserPriority)
                    .where(UserPriority.user_id == user.id)
                    .order_by(UserPriority.score.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )

        tasks = list(
            (
                await self.session.execute(
                    select(StudyTask).where(
                        StudyTask.user_id == user.id,
                        StudyTask.scheduled_for == day,
                        StudyTask.status == StudyTaskStatus.PENDING,
                    )
                )
            )
            .scalars()
            .all()
        )

        return MissionSignals(
            due_cards=due_cards,
            unclassified_errors=unclassified,
            top_subject=top.label if top else None,
            top_subject_score=top.score if top else 0,
            planned_minutes=sum(task.planned_minutes for task in tasks),
            pending_tasks=len(tasks),
            has_plan=True,
        )

    # ------------------------------------------------------------------ #
    # Geração
    # ------------------------------------------------------------------ #
    async def ensure_today(self, user: User, *, today: date | None = None) -> list[Mission]:
        """Cria as missões do dia se ainda não existirem."""
        day = today or datetime.now(UTC).date()
        await self.missions.expire_old(user.id, day)

        existing = list(await self.missions.for_day(user.id, day))
        if existing:
            return existing

        signals = await self._signals(user, day)
        blueprints = generate_daily(signals)
        if not blueprints:
            await self.session.commit()
            return []

        # A linha de base congela o contador do candidato no momento da criação:
        # sem isso, a missão nasceria "já concluída" por atividade de ontem.
        created: list[Mission] = []
        for blueprint in blueprints:
            baseline = await self._measure(user, blueprint.target_metric, day)
            created.append(
                Mission(
                    user_id=user.id,
                    scope=MissionScope.DAILY,
                    kind=blueprint.kind,
                    title=blueprint.title,
                    description=blueprint.description,
                    target_metric=blueprint.target_metric,
                    target_value=blueprint.target_value,
                    current_value=0,
                    baseline_value=baseline,
                    xp_reward=blueprint.xp_reward,
                    priority=blueprint.priority,
                    difficulty=blueprint.difficulty,
                    estimated_minutes=blueprint.estimated_minutes,
                    rationale=blueprint.rationale,
                    source=dict(blueprint.source),
                    valid_from=day,
                    valid_until=day,
                )
            )
        self.session.add_all(created)
        await self.session.commit()
        logger.info("game.missions_created", user=user.public_id, count=len(created))
        return list(await self.missions.for_day(user.id, day))

    async def _measure(self, user: User, metric: str, day: date) -> int:
        """Lê o contador real do candidato para a métrica da missão."""
        if metric == "cards_reviewed":
            return int(
                (
                    await self.session.execute(
                        select(func.count()).where(
                            FlashcardReview.user_id == user.id,
                            func.date(FlashcardReview.created_at) == day,
                        )
                    )
                ).scalar_one()
            )

        if metric == "errors_classified":
            return int(
                (
                    await self.session.execute(
                        select(func.count()).where(
                            ErrorAnalysis.user_id == user.id,
                            ErrorAnalysis.confirmed_at.is_not(None),
                            func.date(ErrorAnalysis.created_at) == day,
                        )
                    )
                ).scalar_one()
            )

        if metric == "focus_minutes":
            seconds = int(
                (
                    await self.session.execute(
                        select(func.coalesce(func.sum(StudySession.focus_seconds), 0)).where(
                            StudySession.user_id == user.id,
                            func.date(StudySession.started_at) == day,
                        )
                    )
                ).scalar_one()
            )
            return seconds // 60

        if metric == "tasks_done":
            return int(
                (
                    await self.session.execute(
                        select(func.count()).where(
                            StudyTask.user_id == user.id,
                            StudyTask.scheduled_for == day,
                            StudyTask.status == StudyTaskStatus.DONE,
                        )
                    )
                ).scalar_one()
            )

        if metric == "questions_answered":
            return int(
                (
                    await self.session.execute(
                        select(func.count()).where(
                            QuestionAttempt.user_id == user.id,
                            func.date(QuestionAttempt.created_at) == day,
                        )
                    )
                ).scalar_one()
            )

        return 0

    # ------------------------------------------------------------------ #
    # Progresso
    # ------------------------------------------------------------------ #
    async def refresh_progress(self, user: User, *, today: date | None = None) -> list[Mission]:
        """Recalcula o progresso a partir da atividade real do candidato."""
        day = today or datetime.now(UTC).date()
        missions = await self.ensure_today(user, today=day)
        now = datetime.now(UTC)

        changed = False
        for mission in missions:
            if mission.status in {MissionStatus.CLAIMED, MissionStatus.EXPIRED}:
                continue
            measured = await self._measure(user, mission.target_metric, day)
            current = max(0, measured - mission.baseline_value)
            if current != mission.current_value:
                mission.current_value = current
                changed = True
            if mission.is_complete and mission.status == MissionStatus.PENDING:
                mission.status = MissionStatus.DONE
                mission.completed_at = now
                changed = True

        if changed:
            await self.session.commit()
        return missions

    async def board(self, user: User, *, today: date | None = None) -> DailyBoard:
        day = today or datetime.now(UTC).date()
        missions = await self.refresh_progress(user, today=day)
        xp_today = await self.engine.transactions.day_total(user.id, day)

        if not missions:
            has_plan = (await self._signals(user, day)).has_plan
            return DailyBoard(
                missions=[],
                bonus_xp=daily_bonus_xp(),
                bonus_claimed=False,
                xp_today=xp_today,
                completed=0,
                total=0,
                has_plan=has_plan,
                empty_reason=(
                    "Monte o seu plano de estudo para que as missões diárias passem a existir. "
                    "Sem plano não há do que derivar objetivo — e missão inventada não aproxima "
                    "ninguém da aprovação."
                    if not has_plan
                    else "Nenhuma missão para hoje."
                ),
            )

        done_states = {MissionStatus.DONE, MissionStatus.CLAIMED}
        completed = len([item for item in missions if item.status in done_states])
        bonus_claimed = await self.engine.transactions.exists_for(
            user.id, GameEventKind.DAILY_MISSIONS_DONE, day.isoformat()
        )

        return DailyBoard(
            missions=missions,
            bonus_xp=daily_bonus_xp(),
            bonus_claimed=bonus_claimed,
            xp_today=xp_today,
            completed=completed,
            total=len(missions),
            has_plan=True,
        )

    # ------------------------------------------------------------------ #
    # Resgate
    # ------------------------------------------------------------------ #
    async def claim(self, user: User, public_id: str) -> dict[str, Any]:
        """Credita o XP de uma missão cumprida. Resgatar duas vezes não repete o ganho."""
        day = datetime.now(UTC).date()
        await self.refresh_progress(user, today=day)

        mission = await self.missions.get_by_public_id(public_id, user.id)
        if mission is None:
            raise NotFoundError("Missão não encontrada.")
        if mission.status == MissionStatus.CLAIMED:
            raise ConflictError("Esta missão já foi resgatada.", code="mission_already_claimed")
        if not mission.is_complete:
            raise ConflictError(
                f"A missão está em {mission.current_value} de {mission.target_value}.",
                code="mission_not_complete",
            )

        rule_kind = (
            GameEventKind.WEEKLY_MISSION_DONE
            if mission.scope == MissionScope.WEEKLY
            else GameEventKind.DAILY_MISSIONS_DONE
        )
        result = await self.engine.award(
            user,
            GameEvent(
                rule_kind,
                {"xp": float(mission.xp_reward), "mission": mission.title},
                reference=f"mission:{mission.public_id}",
            ),
            today=day,
        )

        mission.status = MissionStatus.CLAIMED
        mission.claimed_at = datetime.now(UTC)
        await self.session.commit()

        # Concluir todas as missões do dia libera o bônus, uma única vez.
        board = await self.board(user, today=day)
        bonus: dict[str, Any] | None = None
        if board.all_done and not board.bonus_claimed:
            bonus_result = await self.engine.award(
                user,
                GameEvent(
                    GameEventKind.DAILY_MISSIONS_DONE,
                    {"missions": board.total},
                    reference=day.isoformat(),
                ),
                today=day,
            )
            if bonus_result.recorded:
                bonus = {
                    "amount": bonus_result.award.amount,
                    "reason": "Todas as missões de hoje concluídas.",
                }
            await self.engine.touch_day(user, mission_completed=True, today=day)

        await self.engine.check_achievements(user)
        return {
            "mission": mission,
            "xp_awarded": result.award.amount,
            "leveled_up": result.leveled_up,
            "level": result.level_after,
            "bonus": bonus,
        }

    async def weekly(self, user: User, *, today: date | None = None) -> Mission | None:
        """A missão da semana, quando existir. Ainda não é gerada na Fase 1."""
        day = today or datetime.now(UTC).date()
        monday = day - timedelta(days=day.weekday())
        stmt = select(Mission).where(
            Mission.user_id == user.id,
            Mission.scope == MissionScope.WEEKLY,
            Mission.valid_from == monday,
        )
        return (await self.session.execute(stmt)).scalars().first()
