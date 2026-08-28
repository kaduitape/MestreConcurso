"""Criação e curadoria de flashcards.

O cartão pode nascer de quatro lugares: da mão do candidato, de uma questão que
ele errou, de um erro classificado no Caderno de Erros, ou de um trecho de
material passado a um modelo.

Nos três últimos casos a **procedência viaja junto**. Cartão gerado por IA a
partir de um trecho de edital só é aceito se a citação existir literalmente no
material — a mesma conferência do Mestre IA, pelo mesmo motivo: um verso errado
memorizado por repetição espaçada é pior do que nenhum cartão.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage, CompletionRequest, ProviderError
from app.ai.prompts import get_prompt, latest_version
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.evidence import MIN_QUOTE_LENGTH, normalize_for_match
from app.models.ai import AIFeature
from app.models.catalog import Subject
from app.models.flashcard import CardOrigin, Flashcard
from app.models.intelligence import ErrorAnalysis
from app.models.question import Question
from app.models.user import User
from app.repositories.flashcard import FlashcardRepository
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService

logger = get_logger(__name__)

GENERATE_PROMPT = "flashcard_generate"
MAX_GENERATED = 10
MAX_MATERIAL_CHARS = 6000
MAX_CARDS_PER_USER = 5000
_WHITESPACE = re.compile(r"\s+")


def front_checksum(front: str) -> str:
    """Impressão digital da frente normalizada — barra cartão repetido."""
    normalized = _WHITESPACE.sub(" ", front).strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class GenerationResult:
    created: list[Flashcard] = field(default_factory=list)
    discarded: list[str] = field(default_factory=list)
    skipped_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None


class FlashcardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cards = FlashcardRepository(session)
        self.ai_settings = AISettingsService(session)
        self.cache = AICacheService(session)

    # ------------------------------------------------------------------ #
    # Criação manual
    # ------------------------------------------------------------------ #
    async def _subject_id(self, public_id: str | None) -> int | None:
        if not public_id:
            return None
        row = (
            await self.session.execute(select(Subject.id).where(Subject.public_id == public_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Disciplina não encontrada.")
        return int(row)

    async def _guard_limit(self, user: User) -> None:
        total = await self.cards.count(user_id=user.id)
        if total >= MAX_CARDS_PER_USER:
            raise ConflictError(
                f"Você atingiu o limite de {MAX_CARDS_PER_USER} cartões.",
                code="deck_full",
            )

    async def create(
        self,
        user: User,
        *,
        front: str,
        back: str,
        hint: str | None = None,
        tags: list[str] | None = None,
        subject_public_id: str | None = None,
        origin: str = CardOrigin.USER,
        source_ref: str | None = None,
        source_quote: str | None = None,
        source_page: int | None = None,
        source_document: str | None = None,
        model_slug: str | None = None,
        prompt_version: str | None = None,
    ) -> Flashcard:
        cleaned_front = front.strip()
        cleaned_back = back.strip()
        if len(cleaned_front) < 3 or len(cleaned_back) < 1:
            raise ValidationError("O cartão precisa de frente e verso.", code="invalid_flashcard")

        await self._guard_limit(user)
        checksum = front_checksum(cleaned_front)
        if await self.cards.get_by_checksum(user.id, checksum) is not None:
            raise ConflictError(
                "Você já tem um cartão com esta frente.", code="duplicate_flashcard"
            )

        card = Flashcard(
            user_id=user.id,
            subject_id=await self._subject_id(subject_public_id),
            front=cleaned_front,
            back=cleaned_back,
            hint=hint.strip() if hint else None,
            tags=tags or [],
            origin=origin,
            source_ref=source_ref,
            source_quote=source_quote,
            source_page=source_page,
            source_document=source_document,
            model_slug=model_slug,
            prompt_version=prompt_version,
            checksum=checksum,
        )
        self.session.add(card)
        await self.session.commit()
        stored = await self.cards.get_by_public_id(card.public_id, user.id)
        assert stored is not None
        return stored

    async def update(self, user: User, public_id: str, data: dict[str, Any]) -> Flashcard:
        card = await self.cards.get_owned(public_id, user.id)
        if card is None:
            raise NotFoundError("Cartão não encontrado ou não editável por você.")

        if "subject_public_id" in data:
            card.subject_id = await self._subject_id(data.pop("subject_public_id"))
        if data.get("front"):
            card.front = str(data["front"]).strip()
            card.checksum = front_checksum(card.front)
        for field_name in ("back", "hint", "tags", "is_active"):
            value = data.get(field_name)
            if value is not None:
                setattr(card, field_name, value)

        await self.session.commit()
        stored = await self.cards.get_by_public_id(public_id, user.id)
        assert stored is not None
        return stored

    async def delete(self, user: User, public_id: str) -> None:
        card = await self.cards.get_owned(public_id, user.id)
        if card is None:
            raise NotFoundError("Cartão não encontrado ou não removível por você.")
        await self.cards.delete(card)
        await self.session.commit()

    async def get(self, user: User, public_id: str) -> Flashcard:
        card = await self.cards.get_by_public_id(public_id, user.id)
        if card is None:
            raise NotFoundError("Cartão não encontrado.")
        return card

    async def search(
        self, user: User, *, limit: int, offset: int, **filters: Any
    ) -> tuple[list[Flashcard], int]:
        subject_public_id = filters.pop("subject_public_id", None)
        subject_id = await self._subject_id(subject_public_id) if subject_public_id else None
        rows, total = await self.cards.search(
            user.id, limit=limit, offset=offset, subject_id=subject_id, **filters
        )
        return list(rows), total

    # ------------------------------------------------------------------ #
    # Criação a partir de um erro
    # ------------------------------------------------------------------ #
    async def from_question(self, user: User, question_public_id: str) -> Flashcard:
        """Transforma uma questão em cartão, usando o comentário como verso."""
        question = (
            await self.session.execute(
                select(Question).where(Question.public_id == question_public_id)
            )
        ).scalar_one_or_none()
        if question is None:
            raise NotFoundError("Questão não encontrada.")

        correct = question.correct_alternative
        if correct is None:
            raise ConflictError(
                "Esta questão não tem gabarito definido, então não vira cartão.",
                code="question_without_answer",
            )

        back_parts = [f"{correct.letter}) {correct.content}"]
        if correct.feedback:
            back_parts.append(correct.feedback)
        elif question.explanation:
            back_parts.append(question.explanation)

        return await self.create(
            user,
            front=question.statement,
            back="\n\n".join(back_parts),
            subject_public_id=None,
            origin=CardOrigin.QUESTION,
            source_ref=question.public_id,
        )

    async def from_error(self, user: User, analysis_public_id: str) -> Flashcard:
        """Transforma um erro classificado em cartão."""
        analysis = (
            await self.session.execute(
                select(ErrorAnalysis).where(
                    ErrorAnalysis.public_id == analysis_public_id,
                    ErrorAnalysis.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if analysis is None:
            raise NotFoundError("Classificação de erro não encontrada.")

        question = (
            await self.session.execute(select(Question).where(Question.id == analysis.question_id))
        ).scalar_one_or_none()
        if question is None:
            raise NotFoundError("Questão do erro não encontrada.")

        card = await self.from_question(user, question.public_id)
        card.origin = CardOrigin.ERROR
        card.source_ref = analysis.public_id
        card.subject_id = analysis.subject_id
        await self.session.commit()
        stored = await self.cards.get_by_public_id(card.public_id, user.id)
        assert stored is not None
        return stored

    # ------------------------------------------------------------------ #
    # Geração por IA, com citação conferida
    # ------------------------------------------------------------------ #
    async def generate(
        self,
        user: User,
        *,
        material: str,
        quantity: int = 5,
        subject_public_id: str | None = None,
        source_document: str | None = None,
        source_page: int | None = None,
    ) -> GenerationResult:
        """Gera cartões a partir de um material, conferindo cada citação.

        Cartão cuja citação não aparece literalmente no material é **descartado**,
        não salvo com aviso: um verso sem base entraria na repetição espaçada e
        seria memorizado por insistência.
        """
        text = material.strip()
        if len(text) < 80:
            raise ValidationError(
                "O material é curto demais para gerar cartões.", code="material_too_short"
            )
        text = text[:MAX_MATERIAL_CHARS]
        wanted = max(1, min(quantity, MAX_GENERATED))

        resolved = await self.ai_settings.resolve_feature(AIFeature.FLASHCARD_GENERATION)
        version = latest_version(GENERATE_PROMPT)
        prompt = get_prompt(GENERATE_PROMPT, version)

        cache_key = fingerprint(
            feature=AIFeature.FLASHCARD_GENERATION,
            model_slug=resolved.model_slug,
            prompt_version=version,
            payload={"material": front_checksum(text), "quantity": wanted},
        )
        cached = await self.cache.get(cache_key)
        if cached is not None:
            payload = dict(cached.payload)
        else:
            request = CompletionRequest(
                messages=[
                    ChatMessage(role="system", content=prompt.template),
                    ChatMessage(
                        role="user",
                        content=(f"Gere até {wanted} cartões.\n\n<material>\n{text}\n</material>"),
                    ),
                ],
                model=resolved.model_slug,
                temperature=float(resolved.binding.temperature or 0),
                json_response=True,
            )
            try:
                completion = await resolved.provider.complete(request)
                payload = json.loads(completion.content)
            except ProviderError:
                raise
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValidationError(
                    "A resposta do modelo não seguiu o formato esperado.",
                    code="invalid_ai_response",
                ) from exc

            await self.cache.store(
                cache_key=cache_key,
                feature=AIFeature.FLASHCARD_GENERATION,
                provider_slug=resolved.provider_slug,
                model_slug=resolved.model_slug,
                payload=payload,
                prompt_version=version,
                input_tokens=completion.usage.input_tokens,
                output_tokens=completion.usage.output_tokens,
                ttl_hours=resolved.binding.cache_ttl_hours,
            )

        haystack = normalize_for_match(text)
        created: list[Flashcard] = []
        discarded: list[str] = []

        for item in (payload.get("cards") or [])[:wanted]:
            if not isinstance(item, dict):
                continue
            front = str(item.get("front") or "").strip()
            back = str(item.get("back") or "").strip()
            quote = str(item.get("quote") or "").strip()
            if not front or not back:
                continue

            if len(quote) < MIN_QUOTE_LENGTH or normalize_for_match(quote) not in haystack:
                discarded.append(front[:120])
                continue

            try:
                card = await self.create(
                    user,
                    front=front,
                    back=back,
                    hint=item.get("hint"),
                    subject_public_id=subject_public_id,
                    origin=CardOrigin.AI,
                    source_quote=quote,
                    source_page=source_page,
                    source_document=source_document,
                    model_slug=resolved.model_slug,
                    prompt_version=version,
                )
            except ConflictError:
                # Cartão repetido não é erro de geração: já existe no baralho.
                continue
            created.append(card)

        logger.info(
            "flashcards.generated",
            user=user.public_id,
            created=len(created),
            discarded=len(discarded),
        )
        return GenerationResult(
            created=created,
            discarded=discarded,
            skipped_reason=payload.get("skipped_reason"),
            model=resolved.model_slug,
            prompt_version=version,
        )
