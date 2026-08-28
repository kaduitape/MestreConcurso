"""Resolver questões avulsas: registrar a tentativa e devolver a correção."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.game import GameEvent, GameEventKind, valid_questions
from app.domain.game.xp import MIN_SECONDS_PER_QUESTION
from app.models.question import (
    Alternative,
    Question,
    QuestionAttempt,
    QuestionStats,
)
from app.models.user import User
from app.repositories.question import (
    QuestionAttemptRepository,
    QuestionRepository,
    QuestionStatsRepository,
)
from app.services.game_engine import GameEngine

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AnswerFeedback:
    attempt: QuestionAttempt
    question: Question
    correct_letter: str | None
    correct_feedback: str | None
    selected_feedback: str | None
    explanation: str | None


class PracticeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.questions = QuestionRepository(session)
        self.attempts = QuestionAttemptRepository(session)
        self.stats = QuestionStatsRepository(session)

    async def search(
        self, *, limit: int, offset: int, **filters: object
    ) -> tuple[Sequence[Question], int]:
        return await self.questions.search(limit=limit, offset=offset, **filters)

    async def answer(
        self,
        user: User,
        question_public_id: str,
        *,
        letter: str | None,
        time_seconds: int = 0,
        confidence: str | None = None,
        simulation_attempt_id: int | None = None,
    ) -> AnswerFeedback:
        """Registra a resposta e devolve a correção com o comentário de cada alternativa."""
        question = await self.questions.get_by_public_id(question_public_id)
        if question is None:
            raise NotFoundError("Questão não encontrada.")

        selected: Alternative | None = None
        if letter:
            normalized = letter.strip().upper()
            selected = next(
                (item for item in question.alternatives if item.letter == normalized), None
            )
            if selected is None:
                raise ValidationError(
                    "Alternativa inexistente nesta questão.", code="invalid_alternative"
                )

        correct = question.correct_alternative
        is_blank = selected is None
        is_correct = bool(selected and selected.is_correct)

        attempt = QuestionAttempt(
            user_id=user.id,
            question_id=question.id,
            simulation_attempt_id=simulation_attempt_id,
            selected_alternative_id=selected.id if selected else None,
            selected_letter=selected.letter if selected else None,
            is_correct=is_correct,
            is_blank=is_blank,
            time_seconds=max(0, min(time_seconds, 3600)),
            confidence=confidence,
            subject_id=question.subject_id,
        )
        self.session.add(attempt)
        await self._update_stats(question, is_correct=is_correct, time_seconds=attempt.time_seconds)
        await self.session.commit()

        await self._award_xp(user, question, attempt)

        logger.info(
            "practice.answered",
            user=user.public_id,
            question=question.public_id,
            correct=is_correct,
        )
        return AnswerFeedback(
            attempt=attempt,
            question=question,
            correct_letter=correct.letter if correct else None,
            correct_feedback=correct.feedback if correct else None,
            selected_feedback=selected.feedback if selected else None,
            explanation=question.explanation,
        )

    async def _award_xp(self, user: User, question: Question, attempt: QuestionAttempt) -> None:
        """Notifica o motor de gamificação da resposta.

        A referência inclui o dia, o que implementa a regra "questão repetida no
        mesmo dia não repontua" sem nenhuma verificação extra: a segunda tentativa
        esbarra na própria idempotência do razão.
        """
        if attempt.time_seconds < MIN_SECONDS_PER_QUESTION:
            # Não deu tempo de ler o enunciado: a resposta não entra na contagem.
            return

        day = datetime.now(UTC).date()
        today_attempts = list(
            (
                await self.session.execute(
                    select(QuestionAttempt).where(
                        QuestionAttempt.user_id == user.id,
                        func.date(QuestionAttempt.created_at) == day,
                    )
                )
            )
            .scalars()
            .all()
        )
        _, accuracy, _ = valid_questions(
            [
                {
                    "question_id": float(item.question_id),
                    "time_seconds": float(item.time_seconds),
                    "is_correct": bool(item.is_correct),
                }
                for item in today_attempts
            ]
        )

        metrics: dict[str, float | str] = {
            "questions": 1.0,
            "difficulty": question.difficulty,
        }
        if accuracy is not None:
            metrics["accuracy"] = accuracy

        await GameEngine(self.session).award(
            user,
            GameEvent(
                GameEventKind.QUESTIONS_ANSWERED,
                metrics,
                reference=f"{question.public_id}:{day.isoformat()}",
            ),
            today=day,
        )

    async def _update_stats(
        self, question: Question, *, is_correct: bool, time_seconds: int
    ) -> None:
        """Contadores agregados: é deles que sai qualquer percentual exibido."""
        stats = question.stats or await self.stats.get_for_question(question.id)
        if stats is None:
            stats = QuestionStats(
                question_id=question.id,
                attempts=0,
                correct_attempts=0,
                total_time_seconds=0,
            )
            self.session.add(stats)
            await self.session.flush()

        stats.attempts += 1
        if is_correct:
            stats.correct_attempts += 1
        stats.total_time_seconds += time_seconds
        stats.last_attempt_at = datetime.now(UTC)

    async def history(
        self, user: User, *, limit: int, offset: int
    ) -> tuple[Sequence[QuestionAttempt], int]:
        return await self.attempts.list_for_user(user.id, limit=limit, offset=offset)
