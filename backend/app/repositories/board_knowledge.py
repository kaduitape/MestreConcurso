"""Consultas do conhecimento acumulado sobre bancas."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.board_knowledge import BoardKnowledgeEntry
from app.repositories.base import BaseRepository


class BoardKnowledgeRepository(BaseRepository[BoardKnowledgeEntry]):
    model = BoardKnowledgeEntry

    async def get_entry(
        self, exam_board_id: int, kind: str, entry_key: str
    ) -> BoardKnowledgeEntry | None:
        return await self.get_by(exam_board_id=exam_board_id, kind=kind, entry_key=entry_key)

    async def list_for_board(
        self, exam_board_id: int, *, kind: str | None = None
    ) -> Sequence[BoardKnowledgeEntry]:
        stmt = (
            select(BoardKnowledgeEntry)
            .where(BoardKnowledgeEntry.exam_board_id == exam_board_id)
            .order_by(BoardKnowledgeEntry.kind, BoardKnowledgeEntry.entry_key)
        )
        if kind:
            stmt = stmt.where(BoardKnowledgeEntry.kind == kind)
        return (await self.session.execute(stmt)).scalars().all()

    async def count_by_source(self, exam_board_id: int) -> dict[str, int]:
        stmt = (
            select(BoardKnowledgeEntry.source, func.count())
            .where(BoardKnowledgeEntry.exam_board_id == exam_board_id)
            .group_by(BoardKnowledgeEntry.source)
        )
        rows = (await self.session.execute(stmt)).all()
        return {str(row[0]): int(row[1]) for row in rows}
