"""Consultas do Mestre IA."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.tutor import Conversation, Message, VideoResource, VocabularyTerm
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def get_by_public_id(self, public_id: str, user_id: int) -> Conversation | None:
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.public_id == public_id, Conversation.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: int, *, limit: int = 30) -> Sequence[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.is_archived.is_(False))
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def recent_messages(self, conversation_id: int, *, limit: int) -> list[Message]:
        """Últimas mensagens em ordem cronológica, para dar contexto ao modelo."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return list(reversed(rows))


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def get_by_public_id(self, public_id: str, user_id: int) -> Message | None:
        stmt = select(Message).where(Message.public_id == public_id, Message.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class VocabularyRepository(BaseRepository[VocabularyTerm]):
    model = VocabularyTerm

    async def get_by_public_id(self, public_id: str, user_id: int) -> VocabularyTerm | None:
        stmt = (
            select(VocabularyTerm)
            .where(VocabularyTerm.public_id == public_id, VocabularyTerm.user_id == user_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_key(self, user_id: int, term_key: str) -> VocabularyTerm | None:
        return await self.get_by(user_id=user_id, term_key=term_key)

    async def list_for_user(
        self, user_id: int, *, limit: int, offset: int, search: str | None = None
    ) -> tuple[Sequence[VocabularyTerm], int]:
        stmt = (
            select(VocabularyTerm)
            .where(VocabularyTerm.user_id == user_id)
            .order_by(VocabularyTerm.created_at.desc())
        )
        if search:
            stmt = stmt.where(VocabularyTerm.term.ilike(f"%{search}%"))
        return await self.paginate(stmt, limit=limit, offset=offset)


class VideoResourceRepository(BaseRepository[VideoResource]):
    model = VideoResource

    async def get_by_public_id(self, public_id: str) -> VideoResource | None:
        stmt = (
            select(VideoResource)
            .options(selectinload(VideoResource.subject))
            .where(VideoResource.public_id == public_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def verified_for_subject(
        self, subject_id: int, *, limit: int = 3
    ) -> Sequence[VideoResource]:
        """Só vídeo conferido por uma pessoa chega a ser sugerido."""
        stmt = (
            select(VideoResource)
            .where(
                VideoResource.subject_id == subject_id,
                VideoResource.is_active.is_(True),
                VideoResource.verified_at.is_not(None),
            )
            .order_by(VideoResource.verified_at.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def search(
        self, *, limit: int, offset: int, subject_id: int | None = None
    ) -> tuple[Sequence[VideoResource], int]:
        stmt = select(VideoResource).order_by(VideoResource.created_at.desc())
        if subject_id is not None:
            stmt = stmt.where(VideoResource.subject_id == subject_id)
        return await self.paginate(stmt, limit=limit, offset=offset)
