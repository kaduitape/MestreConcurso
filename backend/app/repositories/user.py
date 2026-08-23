"""Consultas de usuários."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import selectinload

from app.models.user import Profile, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.strip().lower())
            .options(selectinload(User.roles), selectinload(User.profile))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_public_id(self, public_id: str) -> User | None:
        stmt = (
            select(User)
            .where(User.public_id == public_id)
            .options(selectinload(User.roles), selectinload(User.profile))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_with_relations(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles), selectinload(User.profile))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email.strip().lower()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    def search_statement(
        self, *, search: str | None = None, status: str | None = None, role: str | None = None
    ) -> Select[tuple[User]]:
        stmt = (
            select(User)
            .options(selectinload(User.roles), selectinload(User.profile))
            .order_by(User.created_at.desc())
        )
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(or_(User.email.like(pattern), User.full_name.like(pattern)))
        if status:
            stmt = stmt.where(User.status == status)
        if role:
            stmt = stmt.where(User.roles.any(slug=role))
        return stmt

    async def search(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        status: str | None = None,
        role: str | None = None,
    ) -> tuple[Sequence[User], int]:
        stmt = self.search_statement(search=search, status=status, role=role)
        return await self.paginate(stmt, limit=limit, offset=offset)


class ProfileRepository(BaseRepository[Profile]):
    model = Profile

    async def get_by_user_id(self, user_id: int) -> Profile | None:
        return await self.get_by(user_id=user_id)
