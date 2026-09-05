"""Rodadas de desafio: Boss Battle, Sobrevivência, Combo e Contra o Relógio.

Uma rodada é uma **lista congelada de questões reais** mais um estado derivado
das respostas. O serviço não inventa pergunta, não ajusta gabarito e não “deixa
mais fácil” — só decide quando a rodada acaba e quanto ela valeu.

As respostas são registradas pelo mesmo caminho da prática avulsa. Elas contam
nas estatísticas do candidato porque **são** respostas de verdade; a marca
``game_run_id`` existe para que se possa separá-las na análise, não para
escondê-las.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.game import (
    MODES_BY_KEY,
    ChallengeMode,
    GameEvent,
    GameEventKind,
    ModeSpec,
    RunAnswer,
    RunScore,
    RunState,
    RunStatus,
    evaluate_run,
    score_run,
)
from app.models.catalog import Subject
from app.models.game import GameRun
from app.models.intelligence import UserPriority
from app.models.question import Question, QuestionAttempt
from app.models.user import User
from app.repositories.game import GameRunRepository
from app.repositories.question import QuestionRepository
from app.services.game_engine import GameEngine
from app.services.practice import AnswerFeedback, PracticeService

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RunView:
    run: GameRun
    spec: ModeSpec
    state: RunState
    #: A próxima questão a responder. Nula quando a rodada acabou.
    question: Question | None
    score: RunScore | None = None


class ChallengeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runs = GameRunRepository(session)
        self.questions = QuestionRepository(session)
        self.practice = PracticeService(session)
        self.engine = GameEngine(session)

    # ------------------------------------------------------------------ #
    # Largada
    # ------------------------------------------------------------------ #
    async def start(self, user: User, mode: str, *, subject_id: int | None = None) -> RunView:
        spec = MODES_BY_KEY.get(mode)
        if spec is None:
            raise ValidationError("Modo de desafio desconhecido.", code="unknown_mode")

        running = await self.runs.running_for(user.id)
        if running is not None:
            raise ConflictError(
                "Você já tem uma rodada em andamento. Termine ou abandone antes de começar outra.",
                code="run_already_running",
            )

        questions, selection, subject = await self._select(user, spec, subject_id=subject_id)
        if len(questions) < spec.questions:
            # Sem questões suficientes a rodada não acontece. Repetir enunciado
            # para completar o número seria fabricar desafio.
            raise ConflictError(
                (
                    f"O banco tem {len(questions)} questão(ões) elegíveis para este modo e "
                    f"são necessárias {spec.questions}. A rodada não foi criada."
                ),
                code="not_enough_questions",
            )

        run = GameRun(
            user_id=user.id,
            mode=spec.mode,
            status=RunStatus.RUNNING,
            question_ids=[question.id for question in questions],
            selection=selection,
            subject_id=subject.id if subject else None,
            subject_label=subject.name if subject else None,
            started_at=datetime.now(UTC),
        )
        self.session.add(run)
        await self.session.commit()

        logger.info("challenge.started", user=user.public_id, mode=spec.mode, run=run.public_id)
        return await self.view(user, run.public_id)

    async def _select(
        self, user: User, spec: ModeSpec, *, subject_id: int | None = None
    ) -> tuple[list[Question], dict[str, Any], Subject | None]:
        """Escolhe as questões da rodada e registra **por que** foram estas."""
        if subject_id is not None:
            # Estágio de campanha: a disciplina vem do mapa, não do topo da lista.
            # Sem isso a campanha só teria um estágio jogável — o primeiro.
            subject = await self.session.get(Subject, subject_id)
            if subject is None:
                raise NotFoundError("Disciplina não encontrada.")
            questions = list(
                await self.questions.pick_for_simulation(
                    limit=spec.questions, subject_id=subject_id
                )
            )
            return (
                questions,
                {"rule": "estágio de campanha", "subject": subject.name},
                subject,
            )

        if spec.mode in (ChallengeMode.BOSS, ChallengeMode.BATTLE_BOSS):
            priority = (
                (
                    await self.session.execute(
                        select(UserPriority)
                        .where(
                            UserPriority.user_id == user.id, UserPriority.subject_id.is_not(None)
                        )
                        # Mesma ordenação da tela de Inteligência: o boss que o
                        # candidato vê em primeiro lugar é o que ele enfrenta.
                        .order_by(UserPriority.score.desc(), UserPriority.label)
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if priority is None:
                raise ConflictError(
                    (
                        "O Boss Battle enfrenta a sua disciplina mais frágil, e ela sai do "
                        "Priority Score. Calcule a prioridade em Inteligência para liberar "
                        "o modo."
                    ),
                    code="no_priority_score",
                )
            subject = await self.session.get(Subject, priority.subject_id)
            questions = list(
                await self.questions.pick_for_simulation(
                    limit=spec.questions, subject_id=priority.subject_id
                )
            )
            return (
                questions,
                {
                    "rule": "disciplina de maior Priority Score",
                    "subject": priority.label,
                    "priority_score": priority.score,
                },
                subject,
            )

        questions = list(await self.questions.pick_for_simulation(limit=spec.questions))
        return questions, {"rule": "seleção livre do banco publicado"}, None

    # ------------------------------------------------------------------ #
    # Estado
    # ------------------------------------------------------------------ #
    async def answers_of(self, run: GameRun) -> list[QuestionAttempt]:
        """As respostas de uma rodada, na ordem. Leitura pública: outras telas
        (a Batalha RPG, por exemplo) derivam o próprio estado a partir delas."""
        return list(
            (
                await self.session.execute(
                    select(QuestionAttempt)
                    .where(QuestionAttempt.game_run_id == run.id)
                    .order_by(QuestionAttempt.id)
                )
            )
            .scalars()
            .all()
        )

    async def _answers(self, run: GameRun) -> list[RunAnswer]:
        return [
            RunAnswer(is_correct=bool(item.is_correct), time_seconds=item.time_seconds)
            for item in await self.answers_of(run)
        ]

    @staticmethod
    def _aware(moment: datetime) -> datetime:
        """SQLite devolve datas sem fuso; o resto do sistema trabalha em UTC."""
        return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)

    def _elapsed(self, run: GameRun) -> int:
        reference = self._aware(run.ended_at) if run.ended_at else datetime.now(UTC)
        return int((reference - self._aware(run.started_at)).total_seconds())

    async def view(self, user: User, public_id: str) -> RunView:
        run = await self.runs.get_by_public_id(public_id, user.id)
        if run is None:
            raise NotFoundError("Rodada não encontrada.")

        spec = MODES_BY_KEY[run.mode]
        answers = await self._answers(run)
        state = evaluate_run(spec, answers, elapsed_seconds=self._elapsed(run))

        question: Question | None = None
        if run.status == RunStatus.RUNNING and not state.is_over:
            remaining = run.question_ids[len(answers) :]
            if remaining:
                question = await self.questions.get_full(remaining[0])

        score = None
        if run.status != RunStatus.RUNNING:
            score = score_run(spec, state)

        return RunView(run=run, spec=spec, state=state, question=question, score=score)

    async def current(self, user: User) -> RunView | None:
        run = await self.runs.running_for(user.id)
        return None if run is None else await self.view(user, run.public_id)

    # ------------------------------------------------------------------ #
    # Resposta
    # ------------------------------------------------------------------ #
    async def answer(
        self, user: User, public_id: str, *, letter: str | None, time_seconds: int
    ) -> tuple[RunView, AnswerFeedback]:
        run = await self.runs.get_by_public_id(public_id, user.id)
        if run is None:
            raise NotFoundError("Rodada não encontrada.")
        if run.status != RunStatus.RUNNING:
            raise ConflictError("Esta rodada já foi encerrada.", code="run_not_running")

        spec = MODES_BY_KEY[run.mode]
        answers = await self._answers(run)
        state = evaluate_run(spec, answers, elapsed_seconds=self._elapsed(run))
        if state.is_over:
            # O tempo pode ter acabado entre a última resposta e esta.
            raise ConflictError(state.over_reason or "Esta rodada já terminou.", code="run_over")

        remaining = run.question_ids[len(answers) :]
        if not remaining:
            raise ConflictError("Não há mais questões nesta rodada.", code="run_exhausted")

        question = await self.questions.get_full(remaining[0])
        if question is None:
            raise NotFoundError("Questão da rodada não encontrada.")

        feedback = await self.practice.answer(
            user,
            question.public_id,
            letter=letter,
            time_seconds=time_seconds,
        )
        feedback.attempt.game_run_id = run.id
        await self.session.commit()

        view = await self.view(user, public_id)
        if view.state.is_over:
            view = await self.finish(user, public_id)
        return view, feedback

    # ------------------------------------------------------------------ #
    # Encerramento
    # ------------------------------------------------------------------ #
    async def finish(self, user: User, public_id: str, *, abandoned: bool = False) -> RunView:
        run = await self.runs.get_by_public_id(public_id, user.id)
        if run is None:
            raise NotFoundError("Rodada não encontrada.")
        if run.status != RunStatus.RUNNING:
            return await self.view(user, public_id)

        spec = MODES_BY_KEY[run.mode]
        answers = await self._answers(run)
        run.ended_at = datetime.now(UTC)
        state = evaluate_run(spec, answers, elapsed_seconds=self._elapsed(run))
        result = score_run(spec, state)

        run.status = RunStatus.ABANDONED if abandoned else RunStatus.FINISHED
        run.score = result.score
        run.best_combo = state.best_combo
        run.achieved = result.achieved
        run.summary = {
            "headline": result.headline,
            "answered": state.answered,
            "correct": state.correct,
            "wrong": state.wrong,
            "accuracy": state.accuracy,
            "elapsed_seconds": state.elapsed_seconds,
            "over_reason": state.over_reason,
            "breakdown": [{"label": line.label, "value": line.value} for line in result.breakdown],
        }
        await self.session.commit()

        # Rodada abandonada não pontua: parar no meio não é desempenho.
        if not abandoned:
            award = await self.engine.award(
                user,
                GameEvent(
                    GameEventKind.CHALLENGE_FINISHED,
                    {
                        "xp": float(result.xp),
                        "answered": float(state.answered),
                        "label": f"{spec.name}: {result.headline}.",
                    },
                    reference=run.public_id,
                ),
            )
            run.xp_awarded = award.award.amount
            await self.session.commit()

        logger.info(
            "challenge.finished",
            user=user.public_id,
            mode=spec.mode,
            score=run.score,
            abandoned=abandoned,
        )
        return await self.view(user, public_id)

    async def history(self, user: User, *, limit: int = 20) -> list[GameRun]:
        return list(await self.runs.history(user.id, limit=limit))
