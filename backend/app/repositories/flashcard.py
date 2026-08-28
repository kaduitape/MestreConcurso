"""Consultas de flashcards e do estado de memória."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import selectinload

from app.models.flashcard import CardMemoryState, Flashcard, FlashcardReview
from app.repositories.base import BaseRepository


class FlashcardRepository(BaseRepository[Flashcard]):
    model = Flashcard

    def _visible(self, user_id: int) -> Select[tuple[Flashcard]]:
        """Cartões do próprio candidato somados aos globais."""
        return (
            select(Flashcard)
            .options(selectinload(Flashcard.subject))
            .where(
                Flashcard.is_active.is_(True),
                or_(Flashcard.user_id == user_id, Flashcard.user_id.is_(None)),
            )
        )

    async def get_by_public_id(self, public_id: str, user_id: int) -> Flashcard | None:
        stmt = (
            self._visible(user_id)
            .where(Flashcard.public_id == public_id)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_owned(self, public_id: str, user_id: int) -> Flashcard | None:
        """Só o cartão do próprio candidato — global não se edita por aqui."""
        stmt = select(Flashcard).where(
            Flashcard.public_id == public_id, Flashcard.user_id == user_id
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_checksum(self, user_id: int, checksum: str) -> Flashcard | None:
        stmt = select(Flashcard).where(
            Flashcard.checksum == checksum,
            or_(Flashcard.user_id == user_id, Flashcard.user_id.is_(None)),
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def search(
        self,
        user_id: int,
        *,
        limit: int,
        offset: int,
        subject_id: int | None = None,
        origin: str | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[Flashcard], int]:
        stmt = self._visible(user_id).order_by(Flashcard.created_at.desc())
        if subject_id is not None:
            stmt = stmt.where(Flashcard.subject_id == subject_id)
        if origin:
            stmt = stmt.where(Flashcard.origin == origin)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(or_(Flashcard.front.ilike(pattern), Flashcard.back.ilike(pattern)))
        return await self.paginate(stmt, limit=limit, offset=offset)

    async def count_visible(self, user_id: int) -> int:
        stmt = select(func.count()).select_from(self._visible(user_id).subquery())
        return int((await self.session.execute(stmt)).scalar_one())


class CardStateRepository(BaseRepository[CardMemoryState]):
    model = CardMemoryState

    async def get_for(self, user_id: int, flashcard_id: int) -> CardMemoryState | None:
        return await self.get_by(user_id=user_id, flashcard_id=flashcard_id)

    async def due_states(self, user_id: int, *, until: date) -> Sequence[CardMemoryState]:
        stmt = (
            select(CardMemoryState)
            .options(selectinload(CardMemoryState.flashcard).selectinload(Flashcard.subject))
            .where(CardMemoryState.user_id == user_id, CardMemoryState.due_on <= until)
            .order_by(CardMemoryState.due_on)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def all_states(self, user_id: int) -> Sequence[CardMemoryState]:
        stmt = (
            select(CardMemoryState)
            .options(selectinload(CardMemoryState.flashcard).selectinload(Flashcard.subject))
            .where(CardMemoryState.user_id == user_id)
            .order_by(CardMemoryState.due_on)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def by_card_ids(
        self, user_id: int, card_ids: Sequence[int]
    ) -> dict[int, CardMemoryState]:
        if not card_ids:
            return {}
        stmt = select(CardMemoryState).where(
            CardMemoryState.user_id == user_id, CardMemoryState.flashcard_id.in_(card_ids)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {row.flashcard_id: row for row in rows}

    async def last_review_day(self, user_id: int) -> date | None:
        stmt = select(func.max(CardMemoryState.last_reviewed_at)).where(
            CardMemoryState.user_id == user_id
        )
        value = (await self.session.execute(stmt)).scalar_one_or_none()
        return value.date() if value is not None else None


class FlashcardReviewRepository(BaseRepository[FlashcardReview]):
    model = FlashcardReview

    async def recent(self, user_id: int, *, limit: int = 50) -> Sequence[FlashcardReview]:
        stmt = (
            select(FlashcardReview)
            .where(FlashcardReview.user_id == user_id)
            .order_by(FlashcardReview.created_at.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def counts_by_rating(self, user_id: int) -> dict[str, int]:
        stmt = (
            select(FlashcardReview.rating, func.count())
            .where(FlashcardReview.user_id == user_id)
            .group_by(FlashcardReview.rating)
        )
        return {str(row[0]): int(row[1]) for row in (await self.session.execute(stmt)).all()}

    async def reviewed_today(self, user_id: int, *, day: date) -> int:
        stmt = select(func.count()).where(
            FlashcardReview.user_id == user_id,
            func.date(FlashcardReview.created_at) == day,
        )
        return int((await self.session.execute(stmt)).scalar_one())
