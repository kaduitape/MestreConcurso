"""Fase 2 da gamificação: as telas comparativas.

Aqui mora o que a Fase 1 não tinha: **contexto**. O rank sozinho é um selo; o
rank com histórico mostra se a preparação está subindo ou escorregando. O mesmo
vale para o placar contra a banca, a jornada e o mapa do edital.

O serviço apenas **reúne números reais** e entrega ao domínio, que decide o que
pode ser afirmado. Nenhum cálculo de regra acontece neste arquivo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.game import (
    AnswerSample,
    BoardBattle,
    Journey,
    JourneyInput,
    Territory,
    TerritoryInput,
    build_battle,
    build_journey,
    build_map,
)
from app.models.catalog import Competition, ExamBoard, Subject
from app.models.flashcard import Flashcard, FlashcardReview
from app.models.game import RankSnapshot
from app.models.question import Question, QuestionAttempt
from app.models.study import StudyPlan, StudyPlanStatus, UserSubjectProgress
from app.models.user import User
from app.repositories.game import RankSnapshotRepository
from app.services.game_engine import GameEngine

# Janela padrão do histórico de rank exibido.
DEFAULT_HISTORY_DAYS = 90


@dataclass(frozen=True, slots=True)
class RankPoint:
    day: date
    rank_slug: str
    rank_score: float
    xp_total: int
    level: int


@dataclass(frozen=True, slots=True)
class RankHistory:
    points: list[RankPoint]
    first: RankPoint | None = None
    last: RankPoint | None = None
    empty_reason: str | None = None

    @property
    def delta(self) -> float | None:
        """Variação do score no período. ``None`` com menos de duas fotos."""
        if self.first is None or self.last is None or len(self.points) < 2:
            return None
        return round(self.last.rank_score - self.first.rank_score, 4)


class GameProgressService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.engine = GameEngine(session)
        self.snapshots = RankSnapshotRepository(session)

    # ------------------------------------------------------------------ #
    # Plano ativo — origem do contexto de quase tudo nesta fase
    # ------------------------------------------------------------------ #
    async def active_plan(self, user: User) -> StudyPlan | None:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.user_id == user.id, StudyPlan.status == StudyPlanStatus.ACTIVE)
            .order_by(StudyPlan.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    # ------------------------------------------------------------------ #
    # Histórico de rank
    # ------------------------------------------------------------------ #
    async def record_snapshot(self, user: User) -> RankSnapshot:
        """Grava (ou atualiza) a foto do rank de hoje.

        Uma foto por dia: o rank oscila durante o dia conforme o candidato
        responde, e o histórico interessa em escala de dias, não de minutos.
        """
        profile = await self.engine.refresh_profile(user)
        metrics = await self.engine.collect_metrics(user)
        rank = await self.engine.compute_rank_for(user, metrics)
        day = datetime.now(UTC).date()

        stored = await self.snapshots.get_day(user.id, day)
        if stored is None:
            stored = RankSnapshot(user_id=user.id, day=day)
            self.session.add(stored)

        stored.rank_slug = rank.slug
        stored.rank_score = Decimal(str(rank.score))
        stored.components = [
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
        stored.missing_signals = list(rank.missing_signals)
        stored.xp_total = profile.xp_total
        stored.level = profile.level

        try:
            await self.session.commit()
        except IntegrityError:
            # Duas requisições no mesmo dia: a primeira já gravou, basta reler.
            await self.session.rollback()
            existing = await self.snapshots.get_day(user.id, day)
            if existing is None:
                raise
            return existing
        return stored

    async def rank_history(self, user: User, *, days: int = DEFAULT_HISTORY_DAYS) -> RankHistory:
        """A evolução do rank, sempre gravando a foto de hoje antes de ler."""
        await self.record_snapshot(user)
        rows = list(await self.snapshots.history(user.id, limit=days))
        points = [
            RankPoint(
                day=item.day,
                rank_slug=item.rank_slug,
                rank_score=float(item.rank_score),
                xp_total=item.xp_total,
                level=item.level,
            )
            for item in sorted(rows, key=lambda item: item.day)
        ]
        if len(points) < 2:
            return RankHistory(
                points=points,
                first=points[0] if points else None,
                last=points[-1] if points else None,
                empty_reason=(
                    "Ainda não há histórico para comparar: a evolução aparece a partir do "
                    "segundo dia de uso."
                ),
            )
        return RankHistory(points=points, first=points[0], last=points[-1])

    # ------------------------------------------------------------------ #
    # Você vs Banca
    # ------------------------------------------------------------------ #
    async def board_battle(self, user: User) -> BoardBattle:
        """Placar contra a banca do concurso-alvo do plano ativo."""
        plan = await self.active_plan(user)
        if plan is None or plan.competition_id is None:
            return BoardBattle(
                board_slug="",
                board_name="",
                answers=0,
                correct=0,
                you=0,
                board=0,
                is_sufficient=False,
                empty_reason=(
                    "O placar precisa de um concurso-alvo. Monte um plano vinculado ao "
                    "concurso para saber contra qual banca você está jogando."
                ),
            )

        board = (
            (
                await self.session.execute(
                    select(ExamBoard)
                    .join(Competition, Competition.exam_board_id == ExamBoard.id)
                    .where(Competition.id == plan.competition_id)
                )
            )
            .scalars()
            .first()
        )
        if board is None:
            return BoardBattle(
                board_slug="",
                board_name="",
                answers=0,
                correct=0,
                you=0,
                board=0,
                is_sufficient=False,
                empty_reason=(
                    "O concurso do seu plano ainda não tem banca definida no catálogo. "
                    "Sem banca, não há adversário para o placar."
                ),
            )

        stmt = (
            select(
                QuestionAttempt.subject_id,
                Question.subject_id,
                QuestionAttempt.is_correct,
                QuestionAttempt.created_at,
            )
            .join(Question, Question.id == QuestionAttempt.question_id)
            .where(
                QuestionAttempt.user_id == user.id,
                QuestionAttempt.is_blank.is_(False),
                Question.exam_board_id == board.id,
            )
        )
        rows = list((await self.session.execute(stmt)).all())

        subject_ids = {row[0] or row[1] for row in rows if (row[0] or row[1]) is not None}
        names = await self._subject_names(subject_ids)

        samples = [
            AnswerSample(
                subject_id=row[0] or row[1],
                subject_name=names.get(row[0] or row[1], "Sem disciplina"),
                is_correct=bool(row[2]),
                answered_on=row[3].date() if row[3] is not None else datetime.now(UTC).date(),
            )
            for row in rows
        ]
        return build_battle(samples, board_slug=board.slug, board_name=board.name)

    async def _subject_names(self, subject_ids: set[int]) -> dict[int, str]:
        if not subject_ids:
            return {}
        rows = (
            await self.session.execute(
                select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))
            )
        ).all()
        return {int(row[0]): str(row[1]) for row in rows}

    # ------------------------------------------------------------------ #
    # Jornada da Aprovação
    # ------------------------------------------------------------------ #
    async def journey(self, user: User) -> Journey:
        plan = await self.active_plan(user)
        metrics = await self.engine.collect_metrics(user)

        days_until_exam: int | None = None
        if plan is not None and plan.exam_date is not None:
            days_until_exam = max(0, (plan.exam_date - datetime.now(UTC).date()).days)

        return build_journey(
            JourneyInput(
                study_sessions=int(metrics.get("study_sessions", 0)),
                questions_answered=int(metrics.get("questions_answered", 0)),
                simulations_finished=int(metrics.get("simulations_finished", 0)),
                coverage=metrics.get("coverage"),
                days_until_exam=days_until_exam,
                has_plan=plan is not None,
            )
        )

    # ------------------------------------------------------------------ #
    # Mapa do Edital
    # ------------------------------------------------------------------ #
    async def territory_map(self, user: User) -> list[Territory]:
        """Uma disciplina por território, com os três sinais que existirem."""
        progress = list(
            (
                await self.session.execute(
                    select(UserSubjectProgress).where(UserSubjectProgress.user_id == user.id)
                )
            )
            .scalars()
            .all()
        )
        if not progress:
            return []

        accuracy = await self._accuracy_by_subject(user)
        retention = await self._retention_by_subject(user)
        today = datetime.now(UTC).date()

        items: list[TerritoryInput] = []
        for row in progress:
            answers, correct = accuracy.get(row.subject_id or -1, (0, 0))
            reviews, recalled = retention.get(row.subject_id or -1, (0, 0))
            days_since = (
                (today - row.last_studied_at.date()).days
                if row.last_studied_at is not None
                else None
            )
            items.append(
                TerritoryInput(
                    subject_key=row.subject_key,
                    subject_name=row.subject_label,
                    color_token=row.color_token,
                    subject_id=row.subject_id,
                    coverage=float(row.completion),
                    planned_minutes=row.planned_minutes,
                    studied_minutes=row.studied_minutes,
                    accuracy=round(correct / answers, 4) if answers else None,
                    answers=answers,
                    retention=round(recalled / reviews, 4) if reviews else None,
                    reviews=reviews,
                    days_since_studied=days_since,
                )
            )
        return build_map(items)

    async def _accuracy_by_subject(self, user: User) -> dict[int, tuple[int, int]]:
        subject = func.coalesce(QuestionAttempt.subject_id, Question.subject_id)
        stmt = (
            select(
                subject,
                func.count(),
                func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0),
            )
            .join(Question, Question.id == QuestionAttempt.question_id)
            .where(QuestionAttempt.user_id == user.id, QuestionAttempt.is_blank.is_(False))
            .group_by(subject)
        )
        rows = (await self.session.execute(stmt)).all()
        return {int(row[0]): (int(row[1]), int(row[2])) for row in rows if row[0] is not None}

    async def _retention_by_subject(self, user: User) -> dict[int, tuple[int, int]]:
        """Retenção = revisões que não foram "errei" — o mesmo critério do rank."""
        recalled = func.sum(func.cast(FlashcardReview.rating != "AGAIN", Integer))
        stmt = (
            select(Flashcard.subject_id, func.count(), func.coalesce(recalled, 0))
            .join(Flashcard, Flashcard.id == FlashcardReview.flashcard_id)
            .where(FlashcardReview.user_id == user.id)
            .group_by(Flashcard.subject_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {int(row[0]): (int(row[1]), int(row[2])) for row in rows if row[0] is not None}
