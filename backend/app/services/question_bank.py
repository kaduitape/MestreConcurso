"""Curadoria do banco de questões: cadastro, importação e classificação assistida.

A IA aqui apenas *sugere* disciplina, assunto e dificuldade. A sugestão fica
guardada ao lado da questão e só vira classificação quando uma pessoa aplica —
questão oficial não é reclassificada por modelo sem revisão.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage, CompletionRequest, ProviderError
from app.ai.prompts import get_prompt, latest_version
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.ai import AIFeature
from app.models.audit import AuditAction
from app.models.catalog import ExamBoard, Subject
from app.models.question import (
    Alternative,
    Exam,
    Question,
    QuestionOrigin,
    QuestionStats,
    QuestionStatus,
)
from app.models.user import User
from app.repositories.question import ExamRepository, QuestionRepository
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

CLASSIFY_PROMPT = "question_classify"
MAX_IMPORT_QUESTIONS = 500
_WHITESPACE = re.compile(r"\s+")


def statement_checksum(statement: str) -> str:
    """Impressão digital do enunciado normalizado — barra duplicata na importação."""
    normalized = _WHITESPACE.sub(" ", statement).strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ImportSummary:
    created: int
    skipped_duplicates: int
    errors: list[str]


class QuestionBankService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.questions = QuestionRepository(session)
        self.exams = ExamRepository(session)
        self.ai_settings = AISettingsService(session)
        self.cache = AICacheService(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Cadastro
    # ------------------------------------------------------------------ #
    async def create_question(
        self,
        data: dict[str, Any],
        alternatives: list[dict[str, Any]],
        *,
        subject_public_id: str | None = None,
        exam_public_id: str | None = None,
        board_slug: str | None = None,
        actor: User,
        context: RequestContext,
    ) -> Question:
        self._validate_alternatives(alternatives, kind=data.get("kind"))

        checksum = statement_checksum(data["statement"])
        if await self.questions.get_by_checksum(checksum) is not None:
            raise ConflictError("Esta questão já existe no banco.", code="duplicate_question")

        question = Question(
            checksum=checksum,
            subject_id=await self._subject_id(subject_public_id),
            exam_id=await self._exam_id(exam_public_id),
            exam_board_id=await self._board_id(board_slug),
            **data,
        )
        question.alternatives = [
            Alternative(
                letter=item["letter"].upper()[:2],
                content=item["content"],
                is_correct=bool(item.get("is_correct")),
                feedback=item.get("feedback"),
            )
            for item in alternatives
        ]
        question.stats = QuestionStats(attempts=0, correct_attempts=0, total_time_seconds=0)
        self.session.add(question)
        await self.session.flush()

        await self.audit.record(
            AuditAction.QUESTION_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question",
            resource_id=question.public_id,
        )
        await self.session.commit()
        result = await self.questions.get_by_public_id(question.public_id)
        assert result is not None
        return result

    async def update_question(
        self,
        public_id: str,
        data: dict[str, Any],
        *,
        subject_public_id: str | None = None,
        actor: User,
        context: RequestContext,
    ) -> Question:
        question = await self.get_question(public_id)
        if "statement" in data:
            question.checksum = statement_checksum(data["statement"])
        if subject_public_id is not None:
            question.subject_id = await self._subject_id(subject_public_id)
        for field, value in data.items():
            setattr(question, field, value)

        await self.audit.record(
            AuditAction.QUESTION_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question",
            resource_id=public_id,
            meta={"fields": sorted(data)},
        )
        await self.session.commit()
        result = await self.questions.get_by_public_id(public_id)
        assert result is not None
        return result

    async def get_question(self, public_id: str) -> Question:
        question = await self.questions.get_by_public_id(public_id)
        if question is None:
            raise NotFoundError("Questão não encontrada.")
        return question

    async def delete_question(
        self, public_id: str, *, actor: User, context: RequestContext
    ) -> None:
        question = await self.get_question(public_id)
        await self.questions.delete(question)
        await self.audit.record(
            AuditAction.QUESTION_DELETED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question",
            resource_id=public_id,
        )
        await self.session.commit()

    def _validate_alternatives(
        self, alternatives: list[dict[str, Any]], *, kind: str | None
    ) -> None:
        if kind == "DISCURSIVE":
            return
        if len(alternatives) < 2:
            raise ValidationError(
                "A questão precisa de pelo menos duas alternativas.",
                code="not_enough_alternatives",
            )
        correct = [item for item in alternatives if item.get("is_correct")]
        if len(correct) != 1:
            raise ValidationError(
                "Marque exatamente uma alternativa correta.",
                code="invalid_correct_alternative",
                details={"correct_count": len(correct)},
            )
        letters = [str(item["letter"]).upper() for item in alternatives]
        if len(set(letters)) != len(letters):
            raise ValidationError("Há letras repetidas nas alternativas.", code="duplicate_letter")

    async def _subject_id(self, public_id: str | None) -> int | None:
        if not public_id:
            return None
        subject = (
            await self.session.execute(select(Subject).where(Subject.public_id == public_id))
        ).scalar_one_or_none()
        if subject is None:
            raise NotFoundError("Disciplina não encontrada.")
        return subject.id

    async def _exam_id(self, public_id: str | None) -> int | None:
        if not public_id:
            return None
        exam = await self.exams.get_by_public_id(public_id)
        if exam is None:
            raise NotFoundError("Prova não encontrada.")
        return exam.id

    async def _board_id(self, slug: str | None) -> int | None:
        if not slug:
            return None
        board = (
            await self.session.execute(select(ExamBoard).where(ExamBoard.slug == slug))
        ).scalar_one_or_none()
        if board is None:
            raise NotFoundError("Banca não encontrada.")
        return board.id

    # ------------------------------------------------------------------ #
    # Importação em lote
    # ------------------------------------------------------------------ #
    async def import_questions(
        self,
        payload: list[dict[str, Any]],
        *,
        subject_public_id: str | None,
        exam_public_id: str | None,
        board_slug: str | None,
        actor: User,
        context: RequestContext,
    ) -> ImportSummary:
        if len(payload) > MAX_IMPORT_QUESTIONS:
            raise ValidationError(
                f"O lote excede o limite de {MAX_IMPORT_QUESTIONS} questões.",
                code="import_too_large",
            )

        subject_id = await self._subject_id(subject_public_id)
        exam_id = await self._exam_id(exam_public_id)
        board_id = await self._board_id(board_slug)

        created = 0
        duplicates = 0
        errors: list[str] = []

        for index, item in enumerate(payload, start=1):
            try:
                statement = str(item["statement"]).strip()
                alternatives = item.get("alternatives") or []
                self._validate_alternatives(alternatives, kind=item.get("kind"))

                checksum = statement_checksum(statement)
                if await self.questions.get_by_checksum(checksum) is not None:
                    duplicates += 1
                    continue

                question = Question(
                    statement=statement,
                    checksum=checksum,
                    subject_id=subject_id,
                    exam_id=exam_id,
                    exam_board_id=board_id,
                    year=item.get("year"),
                    difficulty=item.get("difficulty", "MEDIUM"),
                    origin=item.get("origin", QuestionOrigin.OFFICIAL),
                    status=item.get("status", QuestionStatus.PUBLISHED),
                    explanation=item.get("explanation"),
                    source_note=item.get("source_note"),
                    tags=item.get("tags") or [],
                )
                question.alternatives = [
                    Alternative(
                        letter=str(alternative["letter"]).upper()[:2],
                        content=alternative["content"],
                        is_correct=bool(alternative.get("is_correct")),
                        feedback=alternative.get("feedback"),
                    )
                    for alternative in alternatives
                ]
                question.stats = QuestionStats(attempts=0, correct_attempts=0, total_time_seconds=0)
                self.session.add(question)
                await self.session.flush()
                created += 1
            except (KeyError, ValidationError, TypeError) as exc:
                message = exc.message if isinstance(exc, ValidationError) else str(exc)
                errors.append(f"questão {index}: {message}")

        await self.audit.record(
            AuditAction.QUESTION_IMPORTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question_batch",
            resource_id=exam_public_id or subject_public_id or "-",
            meta={"created": created, "duplicates": duplicates, "errors": len(errors)},
        )
        await self.session.commit()
        logger.info("questions.imported", created=created, duplicates=duplicates)
        return ImportSummary(created=created, skipped_duplicates=duplicates, errors=errors[:20])

    # ------------------------------------------------------------------ #
    # Classificação assistida
    # ------------------------------------------------------------------ #
    async def suggest_classification(self, public_id: str) -> dict[str, Any]:
        """Pede uma sugestão ao modelo e guarda ao lado da questão, sem aplicá-la."""
        question = await self.get_question(public_id)
        resolved = await self.ai_settings.resolve_feature(AIFeature.QUESTION_CLASSIFY)
        version = latest_version(CLASSIFY_PROMPT)
        prompt = get_prompt(CLASSIFY_PROMPT, version)

        subjects = list(
            (
                await self.session.execute(
                    select(Subject.name).where(Subject.is_active.is_(True)).order_by(Subject.name)
                )
            )
            .scalars()
            .all()
        )

        cache_key = fingerprint(
            feature=AIFeature.QUESTION_CLASSIFY,
            model_slug=resolved.model_slug,
            prompt_version=version,
            payload={"checksum": question.checksum, "subjects": subjects},
        )
        cached = await self.cache.get(cache_key)
        if cached is not None:
            suggestion = dict(cached.payload)
        else:
            request = CompletionRequest(
                messages=[
                    ChatMessage(role="system", content=prompt.template),
                    ChatMessage(
                        role="user",
                        content=(
                            "Disciplinas disponíveis: "
                            + ", ".join(subjects)
                            + "\n\nClassifique a questão a seguir.\n\n"
                            "<untrusted_document>\n"
                            f"{question.statement}\n"
                            "</untrusted_document>"
                        ),
                    ),
                ],
                model=resolved.model_slug,
                temperature=float(resolved.binding.temperature or 0),
                json_response=True,
            )
            try:
                completion = await resolved.provider.complete(request)
                suggestion = json.loads(completion.content)
            except ProviderError:
                raise
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValidationError(
                    "A resposta do modelo não seguiu o formato esperado.",
                    code="invalid_ai_response",
                ) from exc

            await self.cache.store(
                cache_key=cache_key,
                feature=AIFeature.QUESTION_CLASSIFY,
                provider_slug=resolved.provider_slug,
                model_slug=resolved.model_slug,
                payload=suggestion,
                prompt_version=version,
                input_tokens=completion.usage.input_tokens,
                output_tokens=completion.usage.output_tokens,
                ttl_hours=resolved.binding.cache_ttl_hours,
            )

        question.ai_suggestion = {
            **suggestion,
            "model": resolved.model_slug,
            "prompt_version": version,
            "suggested_at": datetime.now(UTC).isoformat(),
            "applied": False,
        }
        question.status = QuestionStatus.NEEDS_REVIEW
        await self.session.commit()
        return question.ai_suggestion

    async def apply_suggestion(
        self,
        public_id: str,
        *,
        subject_public_id: str | None,
        difficulty: str | None,
        actor: User,
        context: RequestContext,
    ) -> Question:
        """Aplica a classificação revisada por uma pessoa."""
        question = await self.get_question(public_id)
        if subject_public_id:
            question.subject_id = await self._subject_id(subject_public_id)
        if difficulty:
            question.difficulty = difficulty

        question.ai_suggestion = {**(question.ai_suggestion or {}), "applied": True}
        question.status = QuestionStatus.PUBLISHED
        question.reviewed_by_user_id = actor.id
        question.reviewed_at = datetime.now(UTC)

        await self.audit.record(
            AuditAction.QUESTION_CLASSIFIED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question",
            resource_id=public_id,
            meta={"difficulty": question.difficulty},
        )
        await self.session.commit()
        result = await self.questions.get_by_public_id(public_id)
        assert result is not None
        return result

    # ------------------------------------------------------------------ #
    # Provas
    # ------------------------------------------------------------------ #
    async def create_exam(
        self,
        data: dict[str, Any],
        *,
        board_slug: str | None,
        actor: User,
        context: RequestContext,
    ) -> Exam:
        exam = Exam(exam_board_id=await self._board_id(board_slug), **data)
        self.session.add(exam)
        await self.session.flush()
        await self.audit.record(
            AuditAction.CATALOG_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="exam",
            resource_id=exam.public_id,
        )
        await self.session.commit()
        return exam
