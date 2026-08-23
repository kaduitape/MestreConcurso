"""Repositório genérico tipado — CRUD comum sem duplicação."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import CursorResult, Result, Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


def rowcount(result: Result[Any]) -> int:
    """Número de linhas afetadas por UPDATE/DELETE (tipado para o mypy)."""
    return int(cast("CursorResult[Any]", result).rowcount or 0)


class BaseRepository[ModelT: Base]:
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: int) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def get_by(self, **filters: Any) -> ModelT | None:
        stmt = select(self.model).filter_by(**filters).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(self, *, limit: int = 50, offset: int = 0, **filters: Any) -> Sequence[ModelT]:
        stmt = select(self.model).filter_by(**filters).limit(limit).offset(offset)
        return (await self.session.execute(stmt)).scalars().all()

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return int((await self.session.execute(stmt)).scalar_one())

    async def paginate(
        self, stmt: Select[tuple[ModelT]], *, limit: int, offset: int
    ) -> tuple[Sequence[ModelT], int]:
        """Executa a consulta paginada e o total correspondente."""
        total_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int((await self.session.execute(total_stmt)).scalar_one())
        rows = (await self.session.execute(stmt.limit(limit).offset(offset))).scalars().all()
        return rows, total

    def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)

    async def delete_by(self, **filters: Any) -> int:
        stmt = delete(self.model).filter_by(**filters)
        return rowcount(await self.session.execute(stmt))

    async def flush(self) -> None:
        await self.session.flush()
