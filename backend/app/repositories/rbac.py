"""Consultas de papéis e permissões."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.rbac import Permission, Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    model = Role

    async def get_by_slug(self, slug: str) -> Role | None:
        stmt = select(Role).where(Role.slug == slug).options(selectinload(Role.permissions))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_slugs(self, slugs: Sequence[str]) -> Sequence[Role]:
        if not slugs:
            return []
        stmt = select(Role).where(Role.slug.in_(slugs)).options(selectinload(Role.permissions))
        return (await self.session.execute(stmt)).scalars().all()

    async def list_all(self) -> Sequence[Role]:
        stmt = select(Role).options(selectinload(Role.permissions)).order_by(Role.slug)
        return (await self.session.execute(stmt)).scalars().all()


class PermissionRepository(BaseRepository[Permission]):
    model = Permission

    async def list_all(self) -> Sequence[Permission]:
        stmt = select(Permission).order_by(Permission.slug)
        return (await self.session.execute(stmt)).scalars().all()

    async def get_by_slug(self, slug: str) -> Permission | None:
        return await self.get_by(slug=slug)
