"""Consultas do catálogo de concursos."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, delete, or_, select
from sqlalchemy.orm import selectinload

from app.models.catalog import (
    Competition,
    ExamBoard,
    Organization,
    Position,
    PositionSubject,
    Subject,
    Topic,
)
from app.repositories.base import BaseRepository, rowcount


class ExamBoardRepository(BaseRepository[ExamBoard]):
    model = ExamBoard

    async def get_by_slug(self, slug: str) -> ExamBoard | None:
        return await self.get_by(slug=slug)

    async def get_by_public_id(self, public_id: str) -> ExamBoard | None:
        return await self.get_by(public_id=public_id)

    async def search(
        self, *, limit: int, offset: int, search: str | None = None, only_active: bool = False
    ) -> tuple[Sequence[ExamBoard], int]:
        stmt = select(ExamBoard).order_by(ExamBoard.short_name)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(or_(ExamBoard.name.like(pattern), ExamBoard.short_name.like(pattern)))
        if only_active:
            stmt = stmt.where(ExamBoard.is_active.is_(True))
        return await self.paginate(stmt, limit=limit, offset=offset)


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        return await self.get_by(slug=slug)

    async def get_by_public_id(self, public_id: str) -> Organization | None:
        return await self.get_by(public_id=public_id)

    async def search(
        self, *, limit: int, offset: int, search: str | None = None, uf: str | None = None
    ) -> tuple[Sequence[Organization], int]:
        stmt = select(Organization).order_by(Organization.short_name)
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(Organization.name.like(pattern), Organization.short_name.like(pattern))
            )
        if uf:
            stmt = stmt.where(Organization.uf == uf.upper())
        return await self.paginate(stmt, limit=limit, offset=offset)


class CompetitionRepository(BaseRepository[Competition]):
    model = Competition

    def _with_relations(self) -> Select[tuple[Competition]]:
        # populate_existing: relações já carregadas na sessão precisam ser relidas.
        return (
            select(Competition)
            .execution_options(populate_existing=True)
            .options(
                selectinload(Competition.organization),
                selectinload(Competition.exam_board),
                selectinload(Competition.positions)
                .selectinload(Position.subjects)
                .selectinload(PositionSubject.subject),
            )
        )

    async def get_by_public_id(self, public_id: str) -> Competition | None:
        stmt = self._with_relations().where(Competition.public_id == public_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Competition | None:
        stmt = self._with_relations().where(Competition.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        status: str | None = None,
        exam_board_slug: str | None = None,
        year: int | None = None,
        published_only: bool = False,
    ) -> tuple[Sequence[Competition], int]:
        stmt = self._with_relations().order_by(
            Competition.exam_date.is_(None), Competition.exam_date, Competition.year.desc()
        )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(Competition.name.like(pattern))
        if status:
            stmt = stmt.where(Competition.status == status)
        if year:
            stmt = stmt.where(Competition.year == year)
        if exam_board_slug:
            stmt = stmt.join(Competition.exam_board).where(ExamBoard.slug == exam_board_slug)
        if published_only:
            stmt = stmt.where(Competition.is_published.is_(True))
        return await self.paginate(stmt, limit=limit, offset=offset)


class PositionRepository(BaseRepository[Position]):
    model = Position

    async def get_by_public_id(self, public_id: str) -> Position | None:
        stmt = (
            select(Position)
            .where(Position.public_id == public_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(Position.subjects).selectinload(PositionSubject.subject),
                selectinload(Position.competition),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SubjectRepository(BaseRepository[Subject]):
    model = Subject

    async def get_by_slug(self, slug: str) -> Subject | None:
        return await self.get_by(slug=slug)

    async def get_by_public_id(self, public_id: str) -> Subject | None:
        return await self.get_by(public_id=public_id)

    async def search(
        self, *, limit: int, offset: int, search: str | None = None, only_active: bool = False
    ) -> tuple[Sequence[Subject], int]:
        stmt = select(Subject).order_by(Subject.sort_order, Subject.name)
        if search:
            stmt = stmt.where(Subject.name.like(f"%{search.strip()}%"))
        if only_active:
            stmt = stmt.where(Subject.is_active.is_(True))
        return await self.paginate(stmt, limit=limit, offset=offset)


class TopicRepository(BaseRepository[Topic]):
    model = Topic

    async def get_by_public_id(self, public_id: str) -> Topic | None:
        return await self.get_by(public_id=public_id)

    async def list_for_subject(self, subject_id: int) -> Sequence[Topic]:
        stmt = (
            select(Topic)
            .where(Topic.subject_id == subject_id)
            .order_by(Topic.path, Topic.sort_order, Topic.name)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_slug(self, subject_id: int, slug: str) -> Topic | None:
        return await self.get_by(subject_id=subject_id, slug=slug)

    async def count_for_subject(self, subject_id: int) -> int:
        return await self.count(subject_id=subject_id)

    async def delete_subtree(self, topic: Topic) -> int:
        """Remove o assunto e todos os descendentes (caminho materializado)."""
        stmt = delete(Topic).where(
            Topic.subject_id == topic.subject_id,
            or_(Topic.id == topic.id, Topic.path.like(f"{topic.path}/%")),
        )
        return rowcount(await self.session.execute(stmt))
