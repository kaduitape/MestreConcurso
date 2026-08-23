"""Cliente Redis compartilhado (cache, rate limit, locks, pub/sub)."""

from __future__ import annotations

from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None


def get_redis() -> Redis:
    """Retorna um cliente Redis sobre um pool único do processo."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
            health_check_interval=30,
        )
    return Redis(connection_pool=_pool)


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None


async def ping_redis() -> bool:
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception:
        return False


async def cache_get(key: str) -> str | None:
    return await get_redis().get(key)


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    await get_redis().set(key, value, ex=ttl or settings.cache_default_ttl)


async def cache_delete(*keys: str) -> None:
    if keys:
        await get_redis().delete(*keys)
