"""Mestre Game Engine — orquestração.

O motor recebe **eventos já consumados** e decide o que valem. Ele não sabe o que
é uma questão ou um flashcard: recebe a métrica pronta e aplica regra.

Essa separação existe para que mudar "simulado vale 300 XP" não obrigue ninguém a
abrir o corretor de simulados. E porque regra de pontuação muda com frequência —
regra de correção, não.

Toda pontuação passa por aqui e vira **transação**. O saldo do perfil é leitura
rápida; a verdade é o razão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.game import (
    DEFAULT_RULES,
    DayRecord,
    GameEvent,
    GameEventKind,
    RankInput,
    RankResult,
    StreakState,
    XPAward,
    XPRule,
    build_streak,
    compute_rank,
    evaluate,
    level_for_xp,
    qualifies,
    score_event,
)
from app.domain.game.achievements import ACHIEVEMENTS_BY_SLUG
from app.domain.game.streak import SHIELDS_PER_MONTH
from app.models.flashcard import FlashcardReview
from app.models.game import (
    Achievement,
    GameRule,
    GamificationProfile,
    StreakDay,
    UserAchievement,
    XPTransaction,
)
from app.models.intelligence import ErrorAnalysis
from app.models.question import QuestionAttempt, SimulationAttempt, SimulationAttemptStatus
from app.models.study import StudyPlan, StudyPlanStatus, StudySession, UserSubjectProgress
from app.models.user import User
from app.repositories.game import (
    AchievementRepository,
    GameRuleRepository,
    MissionRepository,
    ProfileRepository,
    StreakRepository,
    XPTransactionRepository,
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AwardResult:
    award: XPAward
    transaction: XPTransaction | None
    # Falso quando o evento já havia pontuado: idempotência, não erro.
    recorded: bool = True
    level_before: int = 1
    level_after: int = 1

    @property
    def leveled_up(self) -> bool:
        return self.level_after > self.level_before


class GameEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rules = GameRuleRepository(session)
        self.profiles = ProfileRepository(session)
        self.transactions = XPTransactionRepository(session)
        self.missions = MissionRepository(session)
        self.achievements = AchievementRepository(session)
        self.streaks = StreakRepository(session)

    # ------------------------------------------------------------------ #
    # Regras
    # ------------------------------------------------------------------ #
    async def rule_for(self, kind: str) -> XPRule:
        """A regra vigente: a tabela vence sobre o padrão de fábrica."""
        stored = await self.rules.get_by_key(kind)
        if stored is not None:
            return XPRule(
                key=stored.key,
                label=stored.label,
                xp_value=stored.xp_value,
                daily_cap=stored.daily_cap,
                is_enabled=stored.is_enabled,
            )
        default = next((item for item in DEFAULT_RULES if item.key == kind), None)
        if default is None:
            raise ValueError(f"Regra desconhecida: {kind}")
        return default

    async def sync_rules(self) -> int:
        """Semeia as regras de fábrica que ainda não existem no banco."""
        existing = {rule.key for rule in await self.rules.all_rules()}
        created = 0
        for rule in DEFAULT_RULES:
            if rule.key in existing:
                continue
            self.session.add(
                GameRule(
                    key=rule.key,
                    label=rule.label,
                    xp_value=rule.xp_value,
                    daily_cap=rule.daily_cap,
                    is_enabled=rule.is_enabled,
                )
            )
            created += 1
        if created:
            await self.session.commit()
        return created

    async def sync_achievements(self) -> int:
        """Semeia o catálogo de conquistas a partir do domínio."""
        existing = {item.slug for item in await self.achievements.all_active()}
        created = 0
        for spec in ACHIEVEMENTS_BY_SLUG.values():
            if spec.slug in existing:
                continue
            self.session.add(
                Achievement(
                    slug=spec.slug,
                    name=spec.name,
                    description=spec.description,
                    category=spec.category,
                    icon=spec.icon,
                    tier=spec.tier,
                    criteria={"metric": spec.metric, "threshold": spec.threshold},
                    xp_reward=spec.xp_reward,
                    is_secret=spec.is_secret,
                )
            )
            created += 1
        if created:
            await self.session.commit()
        return created

    # ------------------------------------------------------------------ #
    # Perfil
    # ------------------------------------------------------------------ #
    async def profile_for(self, user: User) -> GamificationProfile:
        profile = await self.profiles.for_user(user.id)
        if profile is None:
            profile = GamificationProfile(
                user_id=user.id,
                streak_shields_left=SHIELDS_PER_MONTH,
                streak_shield_renewed_on=datetime.now(UTC).date().replace(day=1),
            )
            self.session.add(profile)
            await self.session.commit()
        return profile

    # ------------------------------------------------------------------ #
    # Pontuação
    # ------------------------------------------------------------------ #
    async def award(
        self, user: User, event: GameEvent, *, today: date | None = None
    ) -> AwardResult:
        """Pontua um evento e grava a transação correspondente."""
        reference = event.reference or ""
        day = today or datetime.now(UTC).date()

        if reference and await self.transactions.exists_for(user.id, event.kind, reference):
            # Já pontuado: repetir a chamada não repete o ganho.
            profile = await self.profile_for(user)
            return AwardResult(
                award=XPAward(
                    kind=event.kind,
                    amount=0,
                    base_amount=0,
                    multiplier=0.0,
                    reason="Este evento já havia sido pontuado.",
                ),
                transaction=None,
                recorded=False,
                level_before=profile.level,
                level_after=profile.level,
            )

        rule = await self.rule_for(event.kind)
        earned = await self.transactions.earned_today(user.id, event.kind, day)
        award = score_event(event, rule, earned_today=earned)

        profile = await self.profile_for(user)
        level_before = profile.level

        # Recusa por antiabuso não vira linha: nada aconteceu que valha registro.
        if award.amount == 0 and not award.capped:
            return AwardResult(
                award=award,
                transaction=None,
                recorded=False,
                level_before=level_before,
                level_after=level_before,
            )

        transaction = XPTransaction(
            user_id=user.id,
            event_kind=event.kind,
            amount=award.amount,
            base_amount=award.base_amount,
            multiplier=Decimal(str(round(award.multiplier, 2))),
            reason=award.reason[:400],
            reference=reference,
            metrics=dict(event.metrics),
            capped=award.capped,
            cap_reason=award.cap_reason,
            day=day,
        )
        self.session.add(transaction)
        try:
            await self.session.flush()
        except IntegrityError:
            # Corrida entre duas chamadas para o mesmo evento: a primeira venceu.
            await self.session.rollback()
            profile = await self.profile_for(user)
            return AwardResult(
                award=award,
                transaction=None,
                recorded=False,
                level_before=profile.level,
                level_after=profile.level,
            )

        profile.xp_total = await self.transactions.total_for(user.id)
        profile.level = level_for_xp(profile.xp_total).level
        await self.session.commit()

        logger.info(
            "game.awarded",
            user=user.public_id,
            event_kind=event.kind,
            amount=award.amount,
            capped=award.capped,
        )
        return AwardResult(
            award=award,
            transaction=transaction,
            recorded=True,
            level_before=level_before,
            level_after=profile.level,
        )

    # ------------------------------------------------------------------ #
    # Sinais reais para rank e conquistas
    # ------------------------------------------------------------------ #
    async def collect_metrics(self, user: User, *, today: date | None = None) -> dict[str, float]:
        """Reúne os números reais do candidato. Nenhum deles é estimado."""
        reference = today or datetime.now(UTC).date()

        attempts_row = (
            await self.session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0),
                ).where(QuestionAttempt.user_id == user.id)
            )
        ).one()
        attempts = int(attempts_row[0])
        correct = int(attempts_row[1])

        reviews_row = (
            await self.session.execute(
                select(func.count()).where(FlashcardReview.user_id == user.id)
            )
        ).scalar_one()
        reviews = int(reviews_row)
        again = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        FlashcardReview.user_id == user.id, FlashcardReview.rating == "AGAIN"
                    )
                )
            ).scalar_one()
        )

        focus_seconds = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(StudySession.focus_seconds), 0)).where(
                        StudySession.user_id == user.id
                    )
                )
            ).scalar_one()
        )
        sessions = int(
            (
                await self.session.execute(
                    select(func.count()).where(StudySession.user_id == user.id)
                )
            ).scalar_one()
        )

        finished = list(
            (
                await self.session.execute(
                    select(SimulationAttempt).where(
                        SimulationAttempt.user_id == user.id,
                        SimulationAttempt.status == SimulationAttemptStatus.FINISHED,
                    )
                )
            )
            .scalars()
            .all()
        )
        simulation_accuracies = [
            float(item.analysis.get("accuracy", 0)) for item in finished if item.analysis
        ]

        errors = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        ErrorAnalysis.user_id == user.id,
                        ErrorAnalysis.confirmed_at.is_not(None),
                    )
                )
            ).scalar_one()
        )

        coverage_rows = (
            (
                await self.session.execute(
                    select(UserSubjectProgress.completion).where(
                        UserSubjectProgress.user_id == user.id
                    )
                )
            )
            .scalars()
            .all()
        )
        coverage = (
            round(sum(float(item) for item in coverage_rows) / len(coverage_rows), 4)
            if coverage_rows
            else None
        )

        streak_days = list(await self.streaks.recent(user.id))
        active_days = len(
            [item for item in streak_days if item.qualified and (reference - item.day).days < 30]
        )

        metrics: dict[str, float] = {
            "questions_answered": attempts,
            "accuracy": round(correct / attempts, 4) if attempts else 0.0,
            "flashcard_reviews": reviews,
            "recall_rate": round((reviews - again) / reviews, 4) if reviews else 0.0,
            "focus_hours": round(focus_seconds / 3600, 2),
            "study_sessions": sessions,
            "simulations_finished": len(finished),
            "errors_classified": errors,
            "active_days": active_days,
        }
        if simulation_accuracies:
            metrics["simulation_accuracy"] = round(
                sum(simulation_accuracies) / len(simulation_accuracies), 4
            )
        if coverage is not None:
            metrics["coverage"] = coverage
        return metrics

    async def compute_rank_for(self, user: User, metrics: dict[str, float]) -> RankResult:
        has_plan = (
            await self.session.execute(
                select(StudyPlan.id).where(
                    StudyPlan.user_id == user.id, StudyPlan.status == StudyPlanStatus.ACTIVE
                )
            )
        ).scalar_one_or_none() is not None

        return compute_rank(
            RankInput(
                accuracy=metrics.get("accuracy"),
                attempts=int(metrics.get("questions_answered", 0)),
                retention=metrics.get("recall_rate"),
                reviews=int(metrics.get("flashcard_reviews", 0)),
                coverage=metrics.get("coverage"),
                has_plan=has_plan,
                simulation_accuracy=metrics.get("simulation_accuracy"),
                simulations=int(metrics.get("simulations_finished", 0)),
                active_days=int(metrics.get("active_days", 0)),
            )
        )

    # ------------------------------------------------------------------ #
    # Sequência
    # ------------------------------------------------------------------ #
    async def touch_day(
        self,
        user: User,
        *,
        minutes: int = 0,
        tasks_done: int = 0,
        mission_completed: bool = False,
        today: date | None = None,
    ) -> StreakDay:
        """Acumula a atividade do dia. É daqui que a sequência nasce."""
        day = today or datetime.now(UTC).date()
        record = await self.streaks.get_day(user.id, day)
        if record is None:
            record = StreakDay(user_id=user.id, day=day, minutes=0, tasks_done=0)
            self.session.add(record)

        record.minutes += max(0, minutes)
        record.tasks_done += max(0, tasks_done)
        record.mission_completed = record.mission_completed or mission_completed
        record.qualified = qualifies(record.minutes, record.tasks_done, record.mission_completed)
        await self.session.commit()
        return record

    async def streak_state(self, user: User, *, today: date | None = None) -> StreakState:
        day = today or datetime.now(UTC).date()
        profile = await self.profile_for(user)

        # As proteções renovam no dia 1 de cada mês.
        first_of_month = day.replace(day=1)
        if profile.streak_shield_renewed_on != first_of_month:
            profile.streak_shields_left = SHIELDS_PER_MONTH
            profile.streak_shield_renewed_on = first_of_month
            await self.session.commit()

        records = [
            DayRecord(
                day=item.day,
                minutes=item.minutes,
                tasks_done=item.tasks_done,
                mission_completed=item.mission_completed,
                shield_used=item.shield_used,
            )
            for item in await self.streaks.recent(user.id)
        ]
        return build_streak(records, today=day, shields_left=profile.streak_shields_left)

    # ------------------------------------------------------------------ #
    # Conquistas
    # ------------------------------------------------------------------ #
    async def check_achievements(
        self, user: User, metrics: dict[str, float] | None = None
    ) -> list[Achievement]:
        """Confere e concede as conquistas alcançadas, com o XP de cada uma."""
        data = metrics if metrics is not None else await self.collect_metrics(user)
        state = await self.streak_state(user)
        data = {**data, "current_streak": state.current}

        unlocked_rows = list(await self.achievements.unlocked_for(user.id))
        already = {row.achievement.slug for row in unlocked_rows}
        result = evaluate(data, already_unlocked=already)

        granted: list[Achievement] = []
        now = datetime.now(UTC)
        for spec in result.unlocked:
            achievement = await self.achievements.get_by_slug(spec.slug)
            if achievement is None:
                continue
            self.session.add(
                UserAchievement(
                    user_id=user.id,
                    achievement_id=achievement.id,
                    unlocked_at=now,
                    progress={"metric": spec.metric, "value": data.get(spec.metric, 0)},
                )
            )
            granted.append(achievement)

        if granted:
            await self.session.commit()
            for achievement in granted:
                await self.award(
                    user,
                    GameEvent(
                        GameEventKind.ACHIEVEMENT_UNLOCKED,
                        {
                            "xp": float(achievement.xp_reward),
                            "label": f"Conquista: {achievement.name}.",
                        },
                        reference=achievement.slug,
                    ),
                )
            profile = await self.profile_for(user)
            profile.achievements_count = len(already) + len(granted)
            await self.session.commit()

        return granted

    # ------------------------------------------------------------------ #
    # Recomputação do perfil
    # ------------------------------------------------------------------ #
    async def refresh_profile(self, user: User) -> GamificationProfile:
        """Recalcula rank, sequência e contadores a partir dos dados reais."""
        profile = await self.profile_for(user)
        metrics = await self.collect_metrics(user)
        rank = await self.compute_rank_for(user, metrics)
        streak = await self.streak_state(user)

        profile.xp_total = await self.transactions.total_for(user.id)
        profile.level = level_for_xp(profile.xp_total).level
        profile.rank_slug = rank.slug
        profile.rank_score = Decimal(str(rank.score))
        profile.rank_components = [
            {
                "key": item.key,
                "label": item.label,
                "weight": item.weight,
                "value": item.value,
                "points": item.points,
                "available": item.available,
                "detail": item.detail,
            }
            for item in rank.components
        ]
        profile.rank_missing_signals = list(rank.missing_signals)
        profile.current_streak = streak.current
        profile.longest_streak = max(profile.longest_streak, streak.longest)
        profile.streak_shields_left = streak.shields_left
        profile.last_active_on = streak.last_qualified_on
        profile.missions_completed = await self.missions.completed_count(user.id)
        profile.achievements_count = len(list(await self.achievements.unlocked_for(user.id)))
        profile.computed_at = datetime.now(UTC)
        await self.session.commit()
        return profile

    async def snapshot(self, user: User) -> dict[str, Any]:
        """Tudo o que o perfil precisa mostrar, já calculado."""
        profile = await self.refresh_profile(user)
        metrics = await self.collect_metrics(user)
        rank = await self.compute_rank_for(user, metrics)
        streak = await self.streak_state(user)
        level = level_for_xp(profile.xp_total)
        today = datetime.now(UTC).date()

        return {
            "profile": profile,
            "level": level,
            "rank": rank,
            "streak": streak,
            "metrics": metrics,
            "xp_today": await self.transactions.day_total(user.id, today),
        }
