"""Caderno de Erros: por que cada questão foi errada, e o que isso revela.

A causa é declarada por quem errou. A IA pode *sugerir* a causa, e a sugestão
fica visível como sugestão — sem entrar em nenhuma estatística até que a pessoa
confirme. Todo agregado deste módulo é contagem sobre causas confirmadas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage, CompletionRequest, ProviderError
from app.ai.prompts import get_prompt, latest_version
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.game import GameEvent, GameEventKind
from app.domain.intelligence import ErrorNotebook, ErrorRecord, build_notebook
from app.models.ai import AIFeature
from app.models.intelligence import AnalysisSource, ErrorAnalysis, ErrorCause, TrapPattern
from app.models.question import Question, QuestionAttempt
from app.models.user import User
from app.repositories.intelligence import ErrorAnalysisRepository, TrapPatternRepository
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService
from app.services.game_engine import GameEngine

logger = get_logger(__name__)

CLASSIFY_PROMPT = "error_classify"
VALID_CAUSES = {cause.value for cause in ErrorCause}


@dataclass(frozen=True, slots=True)
class CauseSuggestion:
    cause: str | None
    trap_slug: str | None
    confidence: float | None
    rationale: str | None
    study_tip: str | None
    model: str
    prompt_version: str
    # Sempre falso na criação: a sugestão nasce esperando confirmação.
    confirmed: bool = False


class ErrorNotebookService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.analyses = ErrorAnalysisRepository(session)
        self.traps = TrapPatternRepository(session)
        self.ai_settings = AISettingsService(session)
        self.cache = AICacheService(session)

    # ------------------------------------------------------------------ #
    # Registro da causa
    # ------------------------------------------------------------------ #
    async def _attempt(self, user: User, attempt_public_id: str) -> QuestionAttempt:
        attempt = (
            await self.session.execute(
                select(QuestionAttempt).where(
                    QuestionAttempt.public_id == attempt_public_id,
                    QuestionAttempt.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if attempt is None:
            raise NotFoundError("Resposta não encontrada.")
        if attempt.is_correct:
            raise ConflictError(
                "Esta questão foi respondida corretamente; não há erro a classificar.",
                code="attempt_not_wrong",
            )
        return attempt

    async def _trap_id(self, slug: str | None) -> int | None:
        if not slug:
            return None
        trap = await self.traps.get_by_slug(slug)
        if trap is None:
            raise NotFoundError("Padrão de pegadinha não encontrado.")
        return trap.id

    async def classify(
        self,
        user: User,
        attempt_public_id: str,
        *,
        cause: str,
        trap_slug: str | None = None,
        note: str | None = None,
    ) -> ErrorAnalysis:
        """Registra (ou corrige) a causa declarada pelo candidato."""
        if cause not in VALID_CAUSES:
            raise ValidationError("Causa inválida.", code="invalid_cause")
        if cause != ErrorCause.TRAP and trap_slug:
            raise ValidationError(
                "O padrão de pegadinha só se aplica quando a causa é uma pegadinha.",
                code="trap_requires_trap_cause",
            )

        attempt = await self._attempt(user, attempt_public_id)
        analysis = await self.analyses.get_for_attempt(attempt.id)
        now = datetime.now(UTC)

        if analysis is None:
            analysis = ErrorAnalysis(
                question_attempt_id=attempt.id,
                user_id=user.id,
                question_id=attempt.question_id,
                subject_id=attempt.subject_id,
            )
            self.session.add(analysis)

        analysis.cause = cause
        analysis.trap_pattern_id = await self._trap_id(trap_slug)
        analysis.note = note
        analysis.source = AnalysisSource.USER
        # Declarada pela pessoa: já nasce confirmada e conta na estatística.
        analysis.confirmed_at = now
        await self.session.commit()

        stored = await self.analyses.get_for_attempt(attempt.id)
        assert stored is not None

        await GameEngine(self.session).award(
            user,
            GameEvent(
                GameEventKind.ERROR_CLASSIFIED,
                {"errors": 1.0},
                reference=stored.public_id,
            ),
        )

        logger.info("error_notebook.classified", user=user.public_id, cause=cause)
        return stored

    async def confirm(self, user: User, public_id: str) -> ErrorAnalysis:
        """Confirma uma sugestão da IA — só aqui ela passa a contar."""
        analysis = await self.analyses.get_by_public_id(public_id, user.id)
        if analysis is None:
            raise NotFoundError("Classificação não encontrada.")
        if analysis.confirmed_at is not None:
            return analysis
        analysis.confirmed_at = datetime.now(UTC)
        await self.session.commit()
        return analysis

    async def resolve(self, user: User, public_id: str) -> ErrorAnalysis:
        """Marca o erro como superado — sai da fila, permanece no histórico."""
        analysis = await self.analyses.get_by_public_id(public_id, user.id)
        if analysis is None:
            raise NotFoundError("Classificação não encontrada.")
        analysis.resolved_at = datetime.now(UTC)
        await self.session.commit()
        return analysis

    async def delete(self, user: User, public_id: str) -> None:
        analysis = await self.analyses.get_by_public_id(public_id, user.id)
        if analysis is None:
            raise NotFoundError("Classificação não encontrada.")
        await self.analyses.delete(analysis)
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Sugestão de causa (IA)
    # ------------------------------------------------------------------ #
    async def suggest_cause(self, user: User, attempt_public_id: str) -> CauseSuggestion:
        """Pede uma leitura do erro ao modelo. Nada é gravado como confirmado."""
        attempt = await self._attempt(user, attempt_public_id)
        question = (
            await self.session.execute(select(Question).where(Question.id == attempt.question_id))
        ).scalar_one_or_none()
        if question is None:
            raise NotFoundError("Questão não encontrada.")

        resolved = await self.ai_settings.resolve_feature(AIFeature.ERROR_CLASSIFY)
        version = latest_version(CLASSIFY_PROMPT)
        prompt = get_prompt(CLASSIFY_PROMPT, version)
        traps = list(await self.traps.active())
        trap_list = ", ".join(f"{trap.slug} ({trap.name})" for trap in traps) or "nenhum"

        correct = next((item for item in question.alternatives if item.is_correct), None)
        selected = next(
            (item for item in question.alternatives if item.letter == attempt.selected_letter),
            None,
        )

        payload = {
            "question": question.checksum,
            "selected": attempt.selected_letter,
            "traps": [trap.slug for trap in traps],
        }
        cache_key = fingerprint(
            feature=AIFeature.ERROR_CLASSIFY,
            model_slug=resolved.model_slug,
            prompt_version=version,
            payload=payload,
        )
        cached = await self.cache.get(cache_key)
        if cached is not None:
            suggestion = dict(cached.payload)
        else:
            document = "\n".join(
                [
                    f"ENUNCIADO: {question.statement}",
                    f"ALTERNATIVA MARCADA ({attempt.selected_letter or 'em branco'}): "
                    f"{selected.content if selected else 'nenhuma'}",
                    f"ALTERNATIVA CORRETA ({correct.letter if correct else '?'}): "
                    f"{correct.content if correct else 'desconhecida'}",
                ]
            )
            request = CompletionRequest(
                messages=[
                    ChatMessage(role="system", content=prompt.template),
                    ChatMessage(
                        role="user",
                        content=(
                            f"Padrões de pegadinha disponíveis: {trap_list}"
                            "\n\nAnalise o erro a seguir.\n\n"
                            "<untrusted_document>\n"
                            f"{document}\n"
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
                feature=AIFeature.ERROR_CLASSIFY,
                provider_slug=resolved.provider_slug,
                model_slug=resolved.model_slug,
                payload=suggestion,
                prompt_version=version,
                input_tokens=completion.usage.input_tokens,
                output_tokens=completion.usage.output_tokens,
                ttl_hours=resolved.binding.cache_ttl_hours,
            )

        cause = str(suggestion.get("cause") or "")
        if cause not in VALID_CAUSES:
            raise ValidationError(
                "O modelo devolveu uma causa fora da lista prevista.",
                code="invalid_ai_response",
            )
        trap_slug = suggestion.get("trap_slug")
        known = {trap.slug for trap in traps}
        # Pegadinha fora do catálogo é descartada: nome inventado não vira registro.
        if trap_slug not in known:
            trap_slug = None

        analysis = await self.analyses.get_for_attempt(attempt.id)
        if analysis is None:
            analysis = ErrorAnalysis(
                question_attempt_id=attempt.id,
                user_id=user.id,
                question_id=attempt.question_id,
                subject_id=attempt.subject_id,
            )
            self.session.add(analysis)
        elif analysis.confirmed_at is not None:
            raise ConflictError(
                "Este erro já tem causa confirmada por você.",
                code="cause_already_confirmed",
            )

        analysis.cause = cause
        analysis.trap_pattern_id = await self._trap_id(trap_slug)
        analysis.source = AnalysisSource.AI
        analysis.model_slug = resolved.model_slug
        analysis.prompt_version = version
        analysis.rationale = suggestion.get("rationale")
        analysis.confirmed_at = None
        await self.session.commit()

        return CauseSuggestion(
            cause=cause,
            trap_slug=trap_slug,
            confidence=(
                float(suggestion["confidence"])
                if suggestion.get("confidence") is not None
                else None
            ),
            rationale=suggestion.get("rationale"),
            study_tip=suggestion.get("study_tip"),
            model=resolved.model_slug,
            prompt_version=version,
        )

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def notebook(self, user: User) -> ErrorNotebook:
        """O caderno resumido — construído só com o que foi confirmado."""
        rows = await self.analyses.confirmed_for_user(user.id)
        records = [
            ErrorRecord(
                cause=row.cause,
                subject_id=row.subject_id,
                subject_name=(
                    row.attempt.question.subject.name
                    if row.attempt.question.subject
                    else "Sem disciplina"
                ),
                trap_slug=row.trap_pattern.slug if row.trap_pattern else None,
                trap_name=row.trap_pattern.name if row.trap_pattern else None,
                resolved=row.resolved_at is not None,
            )
            for row in rows
        ]
        return build_notebook(records)

    async def list_analyses(
        self,
        user: User,
        *,
        limit: int,
        offset: int,
        cause: str | None = None,
        only_pending: bool = False,
    ) -> tuple[list[ErrorAnalysis], int]:
        rows, total = await self.analyses.list_for_user(
            user.id, limit=limit, offset=offset, cause=cause, only_pending=only_pending
        )
        return list(rows), total

    async def pending_attempts(self, user: User, *, limit: int = 20) -> list[QuestionAttempt]:
        return list(await self.analyses.unclassified_attempts(user.id, limit=limit))

    async def trap_catalogue(self) -> list[TrapPattern]:
        return list(await self.traps.active())

    def suggestion_payload(self, analysis: ErrorAnalysis) -> dict[str, Any]:
        return {
            "cause": analysis.cause,
            "source": analysis.source,
            "model": analysis.model_slug,
            "prompt_version": analysis.prompt_version,
            "rationale": analysis.rationale,
            "confirmed": analysis.is_confirmed,
        }
