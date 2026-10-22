"""Engine assíncrona e fábrica de sessões."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_restricted_engine: AsyncEngine | None = None
_restricted_session_factory: async_sessionmaker[AsyncSession] | None = None


def _engine_kwargs() -> dict[str, Any]:
    url = settings.sqlalchemy_url
    kwargs: dict[str, Any] = {"echo": settings.db_echo, "future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        # SQLite (testes) não aceita as opções de pool do MySQL.
        return {"echo": settings.db_echo, "future": True}
    kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
    )
    return kwargs


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.sqlalchemy_url, **_engine_kwargs())
        if _engine.dialect.name == "sqlite":
            _enable_sqlite_foreign_keys(_engine)
    return _engine


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """SQLite ignora ON DELETE CASCADE sem este PRAGMA; o MySQL já o respeita."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


def get_restricted_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Fábrica de sessões do usuário restrito, ou ``None`` se não houver um.

    Existe para o analista de melhorias (Agente 8): ele precisa ler tudo e só
    pode escrever duas tabelas, e a única forma de **garantir** isso é um
    usuário de banco com essa permissão. O código que confia apenas em si
    mesmo não garante nada — basta um import errado no futuro.
    """
    global _restricted_engine, _restricted_session_factory
    url = settings.readonly_sqlalchemy_url
    if url is None:
        return None
    if _restricted_session_factory is None:
        _restricted_engine = create_async_engine(
            url,
            echo=settings.db_echo,
            future=True,
            pool_pre_ping=True,
            # Pool pequeno de propósito: é uma varredura ocasional, não um
            # caminho de requisição.
            pool_size=2,
            max_overflow=2,
            pool_recycle=settings.db_pool_recycle,
        )
        _restricted_session_factory = async_sessionmaker(
            bind=_restricted_engine, expire_on_commit=False, autoflush=False
        )
    return _restricted_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Dependência FastAPI: uma sessão por requisição, com rollback em erro."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_factory, _restricted_engine, _restricted_session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    if _restricted_engine is not None:
        await _restricted_engine.dispose()
    _restricted_engine = None
    _restricted_session_factory = None
