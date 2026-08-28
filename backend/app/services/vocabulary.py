"""Vocabulário inteligente: os termos que o candidato guarda das conversas.

Cada termo registra **de onde veio a definição**: de um trecho citado e conferido
(`CITED`) ou da redação do modelo (`GENERATED`). A interface mostra a diferença —
uma definição gerada não é apresentada como se fosse texto do edital.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.tutor import normalize
from app.models.catalog import Subject
from app.models.tutor import Message, VocabularyTerm
from app.models.user import User
from app.repositories.tutor import VocabularyRepository

logger = get_logger(__name__)

MIN_TERM_LENGTH = 2
MAX_TERMS = 500


class VocabularyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.terms = VocabularyRepository(session)

    async def add(
        self,
        user: User,
        *,
        term: str,
        definition: str,
        subject_public_id: str | None = None,
        message_public_id: str | None = None,
    ) -> VocabularyTerm:
        cleaned = term.strip()
        if len(cleaned) < MIN_TERM_LENGTH:
            raise ValidationError("Informe o termo.", code="invalid_term")
        if not definition.strip():
            raise ValidationError("Informe a definição.", code="invalid_definition")

        total = await self.terms.count(user_id=user.id)
        if total >= MAX_TERMS:
            raise ConflictError(
                f"Seu vocabulário atingiu o limite de {MAX_TERMS} termos.",
                code="vocabulary_full",
            )

        key = normalize(cleaned)
        if await self.terms.get_by_key(user.id, key) is not None:
            raise ConflictError("Este termo já está no seu vocabulário.", code="duplicate_term")

        subject_id = None
        if subject_public_id:
            subject_id = (
                await self.session.execute(
                    select(Subject.id).where(Subject.public_id == subject_public_id)
                )
            ).scalar_one_or_none()
            if subject_id is None:
                raise NotFoundError("Disciplina não encontrada.")

        origin = "GENERATED"
        quote = page = document = None
        message_id = None
        if message_public_id:
            message = (
                await self.session.execute(
                    select(Message).where(
                        Message.public_id == message_public_id, Message.user_id == user.id
                    )
                )
            ).scalar_one_or_none()
            if message is None:
                raise NotFoundError("Mensagem não encontrada.")
            message_id = message.id
            # Herda a origem da primeira afirmação conferida da mensagem: se a
            # resposta tinha citação, o termo nasce com ela.
            cited = next(
                (item for item in (message.claims or []) if item.get("status") == "CITED"), None
            )
            if cited:
                origin = "CITED"
                quote = cited.get("quote")
                page = cited.get("page_number")
                document = cited.get("document_title")

        entry = VocabularyTerm(
            user_id=user.id,
            term=cleaned[:160],
            term_key=key[:160],
            definition=definition.strip(),
            subject_id=int(subject_id) if subject_id else None,
            message_id=message_id,
            source_quote=quote,
            source_page=page,
            source_document=document,
            origin=origin,
        )
        self.session.add(entry)
        await self.session.commit()
        stored = await self.terms.get_by_public_id(entry.public_id, user.id)
        assert stored is not None
        logger.info("vocabulary.added", user=user.public_id, origin=origin)
        return stored

    async def list(
        self, user: User, *, limit: int, offset: int, search: str | None = None
    ) -> tuple[list[VocabularyTerm], int]:
        rows, total = await self.terms.list_for_user(
            user.id, limit=limit, offset=offset, search=search
        )
        return list(rows), total

    async def review(self, user: User, public_id: str) -> VocabularyTerm:
        entry = await self.terms.get_by_public_id(public_id, user.id)
        if entry is None:
            raise NotFoundError("Termo não encontrado.")
        entry.times_reviewed += 1
        entry.last_reviewed_at = datetime.now(UTC)
        await self.session.commit()
        return entry

    async def delete(self, user: User, public_id: str) -> None:
        entry = await self.terms.get_by_public_id(public_id, user.id)
        if entry is None:
            raise NotFoundError("Termo não encontrado.")
        await self.terms.delete(entry)
        await self.session.commit()
