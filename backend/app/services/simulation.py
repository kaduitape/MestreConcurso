"""Simulados: composição por tipo, execução com cronômetro e correção completa.

Cada tipo de simulado tem uma regra explícita de montagem. Quando não há dados
para o tipo pedido (por exemplo, "simulado dos erros" sem erros registrados), a
plataforma diz isso — não devolve um simulado qualquer no lugar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.game import GameEvent, GameEventKind
from app.domain.questions import AnswerInput, QuestionInfo, correct_attempt, distribute_by_weight
from app.models.audit import AuditAction
from app.models.catalog import Position, PositionSubject
from app.models.question import (
    Question,
    QuestionAttempt,
    Simulation,
    SimulationAttempt,
    SimulationAttemptStatus,
    SimulationKind,
    SimulationQuestion,
)
from app.models.study import StudyPlan, StudyPlanStatus
from app.models.user import User
from app.repositories.intelligence import UserPriorityRepository
from app.repositories.question import (
    QuestionAttemptRepository,
    QuestionRepository,
    SimulationAttemptRepository,
    SimulationRepository,
)
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.game_engine import GameEngine
from app.services.practice import PracticeService

logger = get_logger(__name__)

MAX_QUESTIONS = 180
MIN_QUESTIONS = 5

KIND_LABELS: dict[str, str] = {
    SimulationKind.OFFICIAL.value: "Simulado oficial",
    SimulationKind.BOARD.value: "Simulado da banca",
    SimulationKind.ERRORS.value: "Simulado dos erros",
    SimulationKind.FINAL_STRETCH.value: "Simulado reta final",
    SimulationKind.FLASH.value: "Simulado relâmpago",
    SimulationKind.CUSTOM.value: "Simulado personalizado",
    SimulationKind.ADAPTIVE.value: "Simulado adaptativo",
}

# Tempo por questão usado quando a prova não informa duração (padrão de mercado).
DEFAULT_SECONDS_PER_QUESTION = 150


class SimulationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.questions = QuestionRepository(session)
        self.simulations = SimulationRepository(session)
        self.attempts = SimulationAttemptRepository(session)
        self.question_attempts = QuestionAttemptRepository(session)
        self.practice = PracticeService(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Montagem
    # ------------------------------------------------------------------ #
    async def create(
        self,
        user: User,
        *,
        kind: str,
        questions_count: int,
        subject_public_id: str | None = None,
        board_slug: str | None = None,
        duration_minutes: int | None = None,
        context: RequestContext,
    ) -> Simulation:
        if not MIN_QUESTIONS <= questions_count <= MAX_QUESTIONS:
            raise ValidationError(
                f"Escolha entre {MIN_QUESTIONS} e {MAX_QUESTIONS} questões.",
                code="invalid_questions_count",
            )

        selected, config = await self._select_questions(
            user,
            kind=kind,
            questions_count=questions_count,
            subject_public_id=subject_public_id,
            board_slug=board_slug,
        )
        if not selected:
            raise ConflictError(self._empty_reason(kind), code="no_questions_available")

        simulation = Simulation(
            user_id=user.id,
            kind=kind,
            name=KIND_LABELS.get(kind, "Simulado"),
            questions_count=len(selected),
            duration_minutes=duration_minutes
            or max(5, len(selected) * DEFAULT_SECONDS_PER_QUESTION // 60),
            config=config,
        )
        simulation.questions = [
            SimulationQuestion(question_id=question.id, order_index=index)
            for index, question in enumerate(selected)
        ]
        self.session.add(simulation)
        await self.session.flush()

        await self.audit.record(
            AuditAction.SIMULATION_CREATED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="simulation",
            resource_id=simulation.public_id,
            meta={"kind": kind, "questions": len(selected)},
        )
        await self.session.commit()
        result = await self.simulations.get_by_public_id(simulation.public_id, user.id)
        assert result is not None
        return result

    def _empty_reason(self, kind: str) -> str:
        return {
            SimulationKind.ERRORS.value: (
                "Você ainda não tem questões erradas registradas. Resolva questões "
                "para que o simulado dos erros faça sentido."
            ),
            SimulationKind.BOARD.value: ("Não há questões cadastradas para esta banca ainda."),
            SimulationKind.OFFICIAL.value: (
                "As disciplinas do seu plano ainda não têm questões suficientes no banco."
            ),
            SimulationKind.ADAPTIVE.value: (
                "O simulado adaptativo usa o seu Priority Score. Monte o plano de estudo "
                "e resolva algumas questões para que ele exista."
            ),
        }.get(kind, "Não há questões suficientes no banco para montar este simulado.")

    async def _select_questions(
        self,
        user: User,
        *,
        kind: str,
        questions_count: int,
        subject_public_id: str | None,
        board_slug: str | None,
    ) -> tuple[list[Question], dict[str, Any]]:
        """Cada tipo tem uma regra própria, registrada em ``config`` para auditoria."""
        if kind == SimulationKind.ERRORS:
            wrong_ids = await self.question_attempts.wrong_question_ids(user.id)
            questions = list(
                await self.questions.pick_for_simulation(limit=questions_count, only_ids=wrong_ids)
            )
            return questions, {"rule": "questões erradas ainda não recuperadas"}

        if kind == SimulationKind.BOARD and board_slug:
            questions = list(
                await self.questions.pick_for_simulation(
                    limit=questions_count, board_slug=board_slug
                )
            )
            return questions, {"rule": "somente questões da banca", "board": board_slug}

        if kind == SimulationKind.OFFICIAL:
            quotas = await self._official_quotas(user, questions_count)
            if not quotas:
                return [], {"rule": "distribuição do cargo indisponível"}
            picked: list[Question] = []
            used: list[int] = []
            for quota in quotas:
                batch = await self.questions.pick_for_simulation(
                    limit=quota.questions,
                    subject_id=quota.subject_id,
                    exclude_ids=used,
                )
                picked.extend(batch)
                used.extend(question.id for question in batch)
            return picked, {
                "rule": "distribuição equivalente à da prova",
                "quotas": [
                    {"subject": quota.subject_name, "questions": quota.questions}
                    for quota in quotas
                ],
            }

        if kind == SimulationKind.ADAPTIVE:
            picked, quotas = await self._adaptive_selection(user, questions_count)
            if not picked:
                return [], {"rule": "sem Priority Score calculado"}
            return picked, {
                "rule": "mais tempo para as disciplinas de maior Priority Score",
                "quotas": quotas,
            }

        if kind == SimulationKind.FLASH:
            questions = list(
                await self.questions.pick_for_simulation(limit=min(questions_count, 10))
            )
            return questions, {"rule": "amostra curta para revisão rápida"}

        subject_id = None
        if subject_public_id:
            from app.models.catalog import Subject

            subject = (
                await self.session.execute(
                    select(Subject).where(Subject.public_id == subject_public_id)
                )
            ).scalar_one_or_none()
            if subject is None:
                raise NotFoundError("Disciplina não encontrada.")
            subject_id = subject.id

        questions = list(
            await self.questions.pick_for_simulation(
                limit=questions_count, subject_id=subject_id, board_slug=board_slug
            )
        )
        return questions, {"rule": "seleção livre do banco", "subject_id": subject_id}

    async def _adaptive_selection(
        self, user: User, total: int
    ) -> tuple[list[Question], list[dict[str, Any]]]:
        """Distribui as questões conforme o Priority Score já calculado.

        Sem score, devolve vazio — e o candidato recebe o motivo, não um simulado
        genérico disfarçado de adaptativo.
        """
        priorities = [
            row
            for row in await UserPriorityRepository(self.session).for_user(user.id)
            if row.subject_id is not None and row.score > 0
        ]
        if not priorities:
            return [], []

        weight_total = sum(row.score for row in priorities)
        picked: list[Question] = []
        used: list[int] = []
        quotas: list[dict[str, Any]] = []
        for row in priorities:
            quota = max(1, round(total * row.score / weight_total))
            batch = await self.questions.pick_for_simulation(
                limit=quota, subject_id=row.subject_id, exclude_ids=used
            )
            if not batch:
                continue
            picked.extend(batch)
            used.extend(question.id for question in batch)
            quotas.append(
                {"subject": row.label, "priority_score": row.score, "questions": len(batch)}
            )
            if len(picked) >= total:
                break
        return picked[:total], quotas

    async def _official_quotas(self, user: User, total: int) -> list[Any]:
        """Distribuição por disciplina conforme o cargo do plano ativo."""
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
        if plan is None or plan.position_id is None:
            return []

        position = (
            await self.session.execute(
                select(Position)
                .where(Position.id == plan.position_id)
                .options(selectinload(Position.subjects).selectinload(PositionSubject.subject))
            )
        ).scalar_one_or_none()
        if position is None or not position.subjects:
            return []

        return distribute_by_weight(
            [
                (link.subject_id, link.subject.name, link.weight, link.questions_count)
                for link in position.subjects
            ],
            total,
        )

    # ------------------------------------------------------------------ #
    # Execução
    # ------------------------------------------------------------------ #
    async def start(self, user: User, simulation_public_id: str) -> SimulationAttempt:
        running = await self.attempts.get_running(user.id)
        if running is not None:
            raise ConflictError(
                "Você já tem um simulado em andamento.",
                code="simulation_already_running",
                details={"attempt_public_id": running.public_id},
            )

        simulation = await self.simulations.get_by_public_id(simulation_public_id, user.id)
        if simulation is None:
            raise NotFoundError("Simulado não encontrado.")

        attempt = SimulationAttempt(
            simulation_id=simulation.id,
            user_id=user.id,
            started_at=datetime.now(UTC),
        )
        self.session.add(attempt)
        await self.session.commit()
        result = await self.attempts.get_by_public_id(attempt.public_id, user.id)
        assert result is not None
        return result

    async def get_attempt(self, user: User, public_id: str) -> SimulationAttempt:
        attempt = await self.attempts.get_by_public_id(public_id, user.id)
        if attempt is None:
            raise NotFoundError("Execução não encontrada.")
        return attempt

    async def save_answer(
        self,
        user: User,
        attempt_public_id: str,
        *,
        question_public_id: str,
        letter: str | None,
        time_seconds: int = 0,
    ) -> QuestionAttempt:
        """Salvamento automático: cada resposta é gravada assim que marcada."""
        attempt = await self.get_attempt(user, attempt_public_id)
        if attempt.status not in {
            SimulationAttemptStatus.IN_PROGRESS,
            SimulationAttemptStatus.PAUSED,
        }:
            raise ConflictError("Este simulado já foi encerrado.", code="simulation_finished")

        question_ids = {item.question.public_id for item in attempt.simulation.questions}
        if question_public_id not in question_ids:
            raise ValidationError(
                "Esta questão não faz parte do simulado.", code="question_not_in_simulation"
            )

        # Regravar a mesma questão substitui a resposta anterior desta execução.
        existing = (
            await self.session.execute(
                select(QuestionAttempt)
                .join(Question, Question.id == QuestionAttempt.question_id)
                .where(
                    QuestionAttempt.simulation_attempt_id == attempt.id,
                    Question.public_id == question_public_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()

        feedback = await self.practice.answer(
            user,
            question_public_id,
            letter=letter,
            time_seconds=time_seconds,
            simulation_attempt_id=attempt.id,
        )
        return feedback.attempt

    async def pause(self, user: User, public_id: str) -> SimulationAttempt:
        attempt = await self.get_attempt(user, public_id)
        if attempt.status != SimulationAttemptStatus.IN_PROGRESS:
            raise ConflictError("O simulado não está em andamento.", code="not_in_progress")
        now = datetime.now(UTC)
        attempt.elapsed_seconds += self._elapsed(attempt, now)
        attempt.paused_at = now
        attempt.status = SimulationAttemptStatus.PAUSED
        await self.session.commit()
        return attempt

    async def resume(self, user: User, public_id: str) -> SimulationAttempt:
        attempt = await self.get_attempt(user, public_id)
        if attempt.status != SimulationAttemptStatus.PAUSED:
            raise ConflictError("O simulado não está pausado.", code="not_paused")
        attempt.started_at = datetime.now(UTC)
        attempt.paused_at = None
        attempt.status = SimulationAttemptStatus.IN_PROGRESS
        await self.session.commit()
        return attempt

    def _elapsed(self, attempt: SimulationAttempt, now: datetime) -> int:
        started = attempt.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        return max(0, int((now - started).total_seconds()))

    async def finish(
        self, user: User, public_id: str, *, context: RequestContext
    ) -> SimulationAttempt:
        """Encerra e produz a correção completa — não apenas o placar."""
        attempt = await self.get_attempt(user, public_id)
        if attempt.status == SimulationAttemptStatus.FINISHED:
            return attempt

        now = datetime.now(UTC)
        if attempt.status == SimulationAttemptStatus.IN_PROGRESS:
            attempt.elapsed_seconds += self._elapsed(attempt, now)

        answers_rows = list(
            (
                await self.session.execute(
                    select(QuestionAttempt).where(
                        QuestionAttempt.simulation_attempt_id == attempt.id
                    )
                )
            )
            .scalars()
            .all()
        )
        by_question = {row.question_id: row for row in answers_rows}

        questions_info: list[QuestionInfo] = []
        answers: list[AnswerInput] = []
        for item in attempt.simulation.questions:
            question = item.question
            correct = next((alt.letter for alt in question.alternatives if alt.is_correct), None)
            questions_info.append(
                QuestionInfo(
                    question_id=question.id,
                    subject_id=question.subject_id,
                    subject_name=question.subject.name if question.subject else "Sem disciplina",
                    difficulty=question.difficulty,
                    correct_letter=correct,
                )
            )
            row = by_question.get(question.id)
            answers.append(
                AnswerInput(
                    question_id=question.id,
                    selected_letter=row.selected_letter if row else None,
                    time_seconds=row.time_seconds if row else 0,
                )
            )

        previous = await self._previous_accuracy(user, attempt.id)
        analysis = correct_attempt(answers, questions_info, previous_accuracy=previous)

        attempt.status = SimulationAttemptStatus.FINISHED
        attempt.finished_at = now
        attempt.correct_count = analysis.correct
        attempt.wrong_count = analysis.wrong
        attempt.blank_count = analysis.blank
        attempt.score = Decimal(str(analysis.score))
        attempt.analysis = {
            "score": analysis.score,
            "accuracy": analysis.accuracy,
            "total": analysis.total,
            "correct": analysis.correct,
            "wrong": analysis.wrong,
            "blank": analysis.blank,
            "total_time_seconds": analysis.total_time_seconds,
            "average_time_seconds": analysis.average_time_seconds,
            "previous_accuracy": analysis.previous_accuracy,
            "accuracy_delta": analysis.accuracy_delta,
            "by_subject": [
                {
                    "subject_id": item.subject_id,
                    "subject_name": item.subject_name,
                    "total": item.total,
                    "correct": item.correct,
                    "wrong": item.wrong,
                    "blank": item.blank,
                    "accuracy": item.accuracy,
                    "average_time_seconds": item.average_time_seconds,
                }
                for item in analysis.by_subject
            ],
            "by_difficulty": [
                {
                    "difficulty": item.difficulty,
                    "total": item.total,
                    "correct": item.correct,
                    "accuracy": item.accuracy,
                }
                for item in analysis.by_difficulty
            ],
            "weakest_subjects": analysis.weakest_subjects,
            "strongest_subjects": analysis.strongest_subjects,
            "recommendations": analysis.recommendations,
        }

        await self.audit.record(
            AuditAction.SIMULATION_FINISHED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="simulation_attempt",
            resource_id=attempt.public_id,
            meta={"score": analysis.score, "total": analysis.total},
        )
        await self.session.commit()

        await GameEngine(self.session).award(
            user,
            GameEvent(
                GameEventKind.SIMULATION_FINISHED,
                {"questions": float(analysis.total), "accuracy": float(analysis.accuracy)},
                reference=attempt.public_id,
            ),
        )

        logger.info(
            "simulation.finished",
            user=user.public_id,
            attempt=attempt.public_id,
            score=analysis.score,
        )
        return attempt

    async def _previous_accuracy(self, user: User, current_attempt_id: int) -> float | None:
        """Média das execuções anteriores — base da comparação histórica."""
        finished = [
            item
            for item in await self.attempts.list_finished(user.id, limit=10)
            if item.id != current_attempt_id and item.analysis
        ]
        if not finished:
            return None
        values = [float(item.analysis.get("accuracy", 0)) for item in finished]
        return round(sum(values) / len(values), 4)

    async def history(self, user: User, *, limit: int = 20) -> list[SimulationAttempt]:
        return list(await self.attempts.list_finished(user.id, limit=limit))
