"""Priority Score: reúne os sinais reais do candidato e calcula a ordem de estudo.

O serviço apenas *coleta* — o cálculo vive no domínio, em Python puro, e devolve
as parcelas que somam o score. Nenhum sinal é estimado: o que não existe entra
como ausente e vale zero, e a interface mostra isso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.intelligence import PriorityInput, PriorityScore, rank_priorities
from app.models.catalog import Competition
from app.models.intelligence import TopicIncidence, UserPriority
from app.models.question import QuestionAttempt
from app.models.study import StudyPlan, UserSubjectProgress
from app.models.user import User
from app.repositories.intelligence import TopicIncidenceRepository, UserPriorityRepository
from app.repositories.study import StudyPlanRepository

logger = get_logger(__name__)

# Sem este número de respostas na disciplina, o sinal de desempenho não entra.
MIN_ATTEMPTS = 5


@dataclass(frozen=True, slots=True)
class PriorityReport:
    scores: list[PriorityScore]
    computed_at: datetime
    board_slug: str | None
    # O que faltou para o cálculo ficar completo — dito, não escondido.
    notes: list[str]


class PriorityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.plans = StudyPlanRepository(session)
        self.priorities = UserPriorityRepository(session)
        self.incidence = TopicIncidenceRepository(session)

    async def _board_id(self, plan: StudyPlan) -> tuple[int | None, str | None]:
        if plan.competition_id is None:
            return None, None
        row = (
            await self.session.execute(
                select(Competition).where(Competition.id == plan.competition_id)
            )
        ).scalar_one_or_none()
        if row is None or row.exam_board_id is None:
            return None, None
        board = row.exam_board
        return row.exam_board_id, board.slug if board else None

    async def _accuracy_by_subject(self, user_id: int) -> dict[int, tuple[float, int]]:
        """Acerto e número de respostas por disciplina, direto das tentativas."""
        rows = (
            await self.session.execute(
                select(
                    QuestionAttempt.subject_id,
                    func.count(),
                    func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0),
                )
                .where(
                    QuestionAttempt.user_id == user_id,
                    QuestionAttempt.subject_id.is_not(None),
                )
                .group_by(QuestionAttempt.subject_id)
            )
        ).all()
        return {
            int(row[0]): (float(row[2]) / float(row[1]), int(row[1]))
            for row in rows
            if int(row[1]) > 0
        }

    async def compute(self, user: User) -> PriorityReport:
        """Recalcula e grava as prioridades do candidato a partir do plano ativo."""
        now = datetime.now(UTC)
        notes: list[str] = []

        plan = await self.plans.get_active(user.id)
        if plan is None:
            return PriorityReport(
                scores=[],
                computed_at=now,
                board_slug=None,
                notes=[
                    "Sem plano de estudo ativo não há disciplinas para priorizar. "
                    "Monte o plano para que o Priority Score passe a existir."
                ],
            )

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
            return PriorityReport(
                scores=[],
                computed_at=now,
                board_slug=None,
                notes=["O plano ainda não tem disciplinas com tempo alocado."],
            )

        board_id, board_slug = await self._board_id(plan)
        incidence: dict[int, TopicIncidence] = {}
        if board_id is None:
            notes.append(
                "O concurso do seu plano não tem banca definida, então a incidência "
                "histórica não entra no cálculo."
            )
        else:
            incidence = dict(await self.incidence.by_subject(board_id))
            if not incidence:
                notes.append(
                    "Ainda não há mapa de incidência calculado para esta banca — "
                    "o sinal de incidência fica de fora até haver amostra."
                )

        accuracy = await self._accuracy_by_subject(user.id)
        if not accuracy:
            notes.append(
                "Você ainda não respondeu questões suficientes para que o desempenho "
                "pese na prioridade."
            )

        total_planned = sum(row.planned_minutes for row in progress) or 0
        inputs: list[PriorityInput] = []
        for row in progress:
            subject_id = row.subject_id
            row_incidence = incidence.get(subject_id) if subject_id is not None else None
            performance = accuracy.get(subject_id) if subject_id is not None else None
            days = None
            if row.last_studied_at is not None:
                last = row.last_studied_at
                if last.tzinfo is None:
                    last = last.replace(tzinfo=UTC)
                days = max(0, (now - last).days)

            inputs.append(
                PriorityInput(
                    scope_key=row.subject_key,
                    label=row.subject_label,
                    color_token=row.color_token,
                    subject_id=subject_id,
                    incidence_pct=(
                        float(row_incidence.incidence_pct) if row_incidence is not None else None
                    ),
                    notice_share=(
                        round(row.planned_minutes / total_planned, 6) if total_planned else None
                    ),
                    accuracy=performance[0] if performance else None,
                    attempts=performance[1] if performance else 0,
                    days_since_studied=days,
                    completion=float(row.completion),
                )
            )

        scores = rank_priorities(inputs)
        await self._store(user, plan, scores, now)
        logger.info("priority.computed", user=user.public_id, scopes=len(scores))
        return PriorityReport(scores=scores, computed_at=now, board_slug=board_slug, notes=notes)

    async def _store(
        self, user: User, plan: StudyPlan, scores: list[PriorityScore], now: datetime
    ) -> None:
        existing = {
            row.scope_key: row
            for row in (
                await self.session.execute(
                    select(UserPriority).where(UserPriority.user_id == user.id)
                )
            )
            .scalars()
            .all()
        }
        seen: set[str] = set()
        for score in scores:
            seen.add(score.scope_key)
            row = existing.get(score.scope_key)
            if row is None:
                row = UserPriority(user_id=user.id, scope_key=score.scope_key)
                self.session.add(row)
            row.study_plan_id = plan.id
            row.subject_id = score.subject_id
            row.topic_id = score.topic_id
            row.label = score.label
            row.color_token = score.color_token
            row.score = score.score
            row.contributions = [
                {
                    "key": item.key,
                    "label": item.label,
                    "points": item.points,
                    "max_points": item.max_points,
                    "detail": item.detail,
                }
                for item in score.contributions
            ]
            row.missing_signals = list(score.missing_signals)
            row.coverage = Decimal(str(score.coverage))
            row.computed_at = now

        for scope_key, row in existing.items():
            if scope_key not in seen:
                await self.session.delete(row)
        await self.session.commit()

    async def stored(self, user: User) -> list[UserPriority]:
        return list(await self.priorities.for_user(user.id))

    async def scores_for_plan(self, user: User) -> dict[str, int]:
        """Mapa scope_key → score, usado pelo planejador ao redistribuir o tempo."""
        return await self.priorities.scores_by_scope(user.id)
