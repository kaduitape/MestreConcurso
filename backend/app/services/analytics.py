"""Fase 9 — Analytics: o serviço que reúne números reais para o domínio medir.

Nenhum cálculo estatístico acontece aqui. Este arquivo consulta o banco e passa
os números crus para ``app.domain.analytics``, que é onde vivem o intervalo de
Wilson, a propagação da faixa e o arredondamento que faz as parcelas somarem.

A separação não é preciosismo: cálculo estatístico misturado com consulta SQL é
impossível de testar sozinho e é onde erros de medição costumam se esconder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.analytics import (
    Chart,
    DayEffort,
    ExamProjection,
    MasterScore,
    MasterScoreInput,
    Path,
    SubjectCoverage,
    SubjectExam,
    SubjectPerformance,
    WeeklyAttempts,
    accuracy_evolution,
    build_path,
    compute_master_score,
    consistency,
    coverage_by_subject,
    project,
    retention,
)
from app.models.analytics import MasterScoreSnapshot
from app.models.catalog import PositionSubject, Subject
from app.models.flashcard import FlashcardReview
from app.models.game import StreakDay
from app.models.question import QuestionAttempt
from app.models.study import StudyPlan, StudyPlanStatus, UserSubjectProgress
from app.models.user import User
from app.repositories.analytics import MasterScoreRepository

logger = get_logger(__name__)

# Janelas padrão das telas.
EVOLUTION_WEEKS = 12
CONSISTENCY_DAYS = 30
HISTORY_DAYS = 90


@dataclass(frozen=True, slots=True)
class ScorePoint:
    day: date
    value: int
    low: int
    high: int
    band: str
    confidence: str


@dataclass(frozen=True, slots=True)
class ScoreHistory:
    points: list[ScorePoint]
    delta: int | None = None
    empty_reason: str | None = None


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.snapshots = MasterScoreRepository(session)

    # ------------------------------------------------------------------ #
    # Coleta
    # ------------------------------------------------------------------ #
    async def _active_plan(self, user: User) -> StudyPlan | None:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.user_id == user.id, StudyPlan.status == StudyPlanStatus.ACTIVE)
            .order_by(StudyPlan.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def _attempts(
        self, user: User, *, simulations_only: bool | None = None
    ) -> tuple[int, int]:
        correct = func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0)
        stmt = select(func.count(), correct).where(
            QuestionAttempt.user_id == user.id, QuestionAttempt.is_blank.is_(False)
        )
        if simulations_only is True:
            stmt = stmt.where(QuestionAttempt.simulation_attempt_id.is_not(None))
        elif simulations_only is False:
            stmt = stmt.where(QuestionAttempt.simulation_attempt_id.is_(None))
        row = (await self.session.execute(stmt)).one()
        return int(row[0]), int(row[1])

    async def _reviews(self, user: User) -> tuple[int, int]:
        total = int(
            (
                await self.session.execute(
                    select(func.count()).where(FlashcardReview.user_id == user.id)
                )
            ).scalar_one()
        )
        again = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        FlashcardReview.user_id == user.id, FlashcardReview.rating == "AGAIN"
                    )
                )
            ).scalar_one()
        )
        return total, total - again

    async def _coverage(self, user: User) -> tuple[float | None, int, int]:
        rows = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(UserSubjectProgress.studied_minutes), 0),
                    func.coalesce(func.sum(UserSubjectProgress.planned_minutes), 0),
                ).where(UserSubjectProgress.user_id == user.id)
            )
        ).one()
        studied, planned = int(rows[0]), int(rows[1])
        coverage = round(min(1.0, studied / planned), 4) if planned else None
        return coverage, studied, planned

    async def _active_days(self, user: User, *, today: date) -> int:
        since = today - timedelta(days=CONSISTENCY_DAYS)
        return int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        StreakDay.user_id == user.id,
                        StreakDay.qualified.is_(True),
                        StreakDay.day >= since,
                    )
                )
            ).scalar_one()
        )

    # ------------------------------------------------------------------ #
    # Mestre Score
    # ------------------------------------------------------------------ #
    async def master_score(self, user: User, *, today: date | None = None) -> MasterScore:
        day = today or datetime.now(UTC).date()
        attempts, correct = await self._attempts(user)
        sim_attempts, sim_correct = await self._attempts(user, simulations_only=True)
        reviews, recalled = await self._reviews(user)
        coverage, studied, planned = await self._coverage(user)
        plan = await self._active_plan(user)

        return compute_master_score(
            MasterScoreInput(
                correct=correct,
                attempts=attempts,
                recalled=recalled,
                reviews=reviews,
                coverage=coverage,
                covered_minutes=studied,
                planned_minutes=planned,
                simulation_correct=sim_correct,
                simulation_questions=sim_attempts,
                active_days=await self._active_days(user, today=day),
                has_plan=plan is not None,
            )
        )

    async def record_snapshot(
        self, user: User, *, today: date | None = None
    ) -> MasterScoreSnapshot:
        """Grava (ou atualiza) a foto do dia. Uma por dia, como o rank."""
        day = today or datetime.now(UTC).date()
        score = await self.master_score(user, today=day)

        stored = await self.snapshots.get_day(user.id, day)
        if stored is None:
            stored = MasterScoreSnapshot(user_id=user.id, day=day)
            self.session.add(stored)

        stored.value = score.value
        stored.low = score.low
        stored.high = score.high
        stored.band = score.band
        stored.confidence = score.confidence
        stored.available_weight = Decimal(str(score.available_weight))
        stored.components = [
            {
                "key": item.key,
                "label": item.label,
                "weight": item.weight,
                "points": item.points,
                "value": item.value,
                "low": item.low,
                "high": item.high,
                "sample": item.sample,
                "available": item.available,
                "confidence": item.confidence,
                "detail": item.detail,
            }
            for item in score.components
        ]
        stored.missing_signals = list(score.missing_signals)

        try:
            await self.session.commit()
        except IntegrityError:
            # Duas requisições no mesmo dia: a primeira já gravou.
            await self.session.rollback()
            existing = await self.snapshots.get_day(user.id, day)
            if existing is None:
                raise
            return existing
        return stored

    async def history(self, user: User, *, days: int = HISTORY_DAYS) -> ScoreHistory:
        await self.record_snapshot(user)
        rows = sorted(await self.snapshots.history(user.id, limit=days), key=lambda item: item.day)
        points = [
            ScorePoint(
                day=item.day,
                value=item.value,
                low=item.low,
                high=item.high,
                band=item.band,
                confidence=item.confidence,
            )
            for item in rows
        ]
        if len(points) < 2:
            return ScoreHistory(
                points=points,
                empty_reason=(
                    "A evolução aparece a partir do segundo dia. Uma medição não é tendência."
                ),
            )
        return ScoreHistory(points=points, delta=points[-1].value - points[0].value)

    # ------------------------------------------------------------------ #
    # Se a prova fosse hoje
    # ------------------------------------------------------------------ #
    async def _exam_layout(self, user: User) -> list[SubjectExam]:
        """A distribuição oficial da prova do cargo-alvo, como o edital a define."""
        plan = await self._active_plan(user)
        if plan is None or plan.position_id is None:
            return []

        rows = (
            await self.session.execute(
                select(PositionSubject, Subject)
                .join(Subject, Subject.id == PositionSubject.subject_id)
                .where(PositionSubject.position_id == plan.position_id)
            )
        ).all()

        layout: list[SubjectExam] = []
        for link, subject in rows:
            if not link.questions_count:
                # Sem número de questões não há o que projetar nesta disciplina.
                continue
            layout.append(
                SubjectExam(
                    subject_id=subject.id,
                    name=subject.name,
                    questions=int(link.questions_count),
                    weight=float(link.weight or 1),
                    is_eliminatory=bool(link.is_eliminatory),
                    min_score=float(link.min_score) if link.min_score is not None else None,
                )
            )
        return layout

    async def _performance_by_subject(self, user: User) -> list[SubjectPerformance]:
        correct = func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0)
        rows = (
            await self.session.execute(
                select(QuestionAttempt.subject_id, func.count(), correct)
                .where(
                    QuestionAttempt.user_id == user.id,
                    QuestionAttempt.is_blank.is_(False),
                    QuestionAttempt.subject_id.is_not(None),
                )
                .group_by(QuestionAttempt.subject_id)
            )
        ).all()
        return [
            SubjectPerformance(subject_id=int(row[0]), attempts=int(row[1]), correct=int(row[2]))
            for row in rows
        ]

    async def projection(self, user: User) -> ExamProjection:
        return project(await self._exam_layout(user), await self._performance_by_subject(user))

    async def path(self, user: User) -> Path:
        return build_path((await self.projection(user)).subjects)

    # ------------------------------------------------------------------ #
    # Painéis
    # ------------------------------------------------------------------ #
    @staticmethod
    def _week_start(day: date) -> date:
        return day - timedelta(days=day.weekday())

    async def _weekly_attempts(self, user: User, *, today: date) -> list[WeeklyAttempts]:
        since = today - timedelta(weeks=EVOLUTION_WEEKS)
        rows = (
            await self.session.execute(
                select(
                    QuestionAttempt.created_at,
                    QuestionAttempt.is_correct,
                ).where(
                    QuestionAttempt.user_id == user.id,
                    QuestionAttempt.is_blank.is_(False),
                    func.date(QuestionAttempt.created_at) >= since,
                )
            )
        ).all()

        buckets: dict[date, list[int]] = {}
        for row in rows:
            moment = row[0]
            week = self._week_start(moment.date() if hasattr(moment, "date") else moment)
            entry = buckets.setdefault(week, [0, 0])
            entry[0] += 1
            entry[1] += 1 if row[1] else 0
        return [
            WeeklyAttempts(week_start=week, total=value[0], correct=value[1])
            for week, value in sorted(buckets.items())
        ]

    async def _weekly_reviews(self, user: User, *, today: date) -> list[WeeklyAttempts]:
        since = today - timedelta(weeks=EVOLUTION_WEEKS)
        rows = (
            await self.session.execute(
                select(FlashcardReview.created_at, FlashcardReview.rating).where(
                    FlashcardReview.user_id == user.id,
                    func.date(FlashcardReview.created_at) >= since,
                )
            )
        ).all()

        buckets: dict[date, list[int]] = {}
        for row in rows:
            moment = row[0]
            week = self._week_start(moment.date() if hasattr(moment, "date") else moment)
            entry = buckets.setdefault(week, [0, 0])
            entry[0] += 1
            entry[1] += 0 if row[1] == "AGAIN" else 1
        return [
            WeeklyAttempts(week_start=week, total=value[0], correct=value[1])
            for week, value in sorted(buckets.items())
        ]

    async def dashboard(self, user: User, *, today: date | None = None) -> list[Chart]:
        """Os quatro painéis. Cada um carrega a decisão que ele serve."""
        day = today or datetime.now(UTC).date()

        progress = list(
            (
                await self.session.execute(
                    select(UserSubjectProgress).where(UserSubjectProgress.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        since = day - timedelta(days=CONSISTENCY_DAYS)
        days = list(
            (
                await self.session.execute(
                    select(StreakDay)
                    .where(StreakDay.user_id == user.id, StreakDay.day >= since)
                    .order_by(StreakDay.day)
                )
            )
            .scalars()
            .all()
        )

        return [
            accuracy_evolution(await self._weekly_attempts(user, today=day)),
            retention(await self._weekly_reviews(user, today=day)),
            coverage_by_subject(
                [
                    SubjectCoverage(
                        name=item.subject_label,
                        covered_minutes=item.studied_minutes,
                        planned_minutes=item.planned_minutes,
                    )
                    for item in progress
                ]
            ),
            consistency(
                [
                    DayEffort(day=item.day, minutes=item.minutes, qualified=item.qualified)
                    for item in days
                ]
            ),
        ]
