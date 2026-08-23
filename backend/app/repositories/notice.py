"""Consultas de editais e arquivos."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.notice import Notice, NoticeFile
from app.repositories.base import BaseRepository


class NoticeRepository(BaseRepository[Notice]):
    model = Notice

    async def get_by_public_id(self, public_id: str) -> Notice | None:
        stmt = (
            select(Notice)
            .where(Notice.public_id == public_id)
            .options(selectinload(Notice.files), selectinload(Notice.competition))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_competition(self, competition_id: int) -> Sequence[Notice]:
        stmt = (
            select(Notice)
            .where(Notice.competition_id == competition_id)
            .options(selectinload(Notice.files))
            .order_by(Notice.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def search(
        self, *, limit: int, offset: int, status: str | None = None
    ) -> tuple[Sequence[Notice], int]:
        stmt = (
            select(Notice)
            .options(selectinload(Notice.files), selectinload(Notice.competition))
            .order_by(Notice.created_at.desc())
        )
        if status:
            stmt = stmt.where(Notice.status == status)
        return await self.paginate(stmt, limit=limit, offset=offset)


class NoticeFileRepository(BaseRepository[NoticeFile]):
    model = NoticeFile

    async def get_by_public_id(self, public_id: str) -> NoticeFile | None:
        stmt = (
            select(NoticeFile)
            .where(NoticeFile.public_id == public_id)
            .options(selectinload(NoticeFile.notice))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_checksum(self, notice_id: int, checksum: str) -> NoticeFile | None:
        return await self.get_by(notice_id=notice_id, checksum_sha256=checksum)
