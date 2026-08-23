"""Rate limiting por janela deslizante em Redis.

Falha aberta (permite a requisição) se o Redis estiver indisponível: indisponibilidade
de infraestrutura auxiliar não pode derrubar o login de todos os usuários.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from redis.exceptions import RedisError

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

_UNITS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

_LUA_SLIDING_WINDOW = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
  redis.call('ZADD', key, now, ARGV[4])
  redis.call('EXPIRE', key, window)
  return {1, limit - count - 1, 0}
end
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
local retry = window - (now - tonumber(oldest[2]))
if retry < 1 then retry = 1 end
return {0, 0, retry}
"""


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    limit: int
    window_seconds: int

    @classmethod
    def parse(cls, expression: str) -> RateLimitRule:
        """Converte "10/minute" em uma regra."""
        raw_limit, _, unit = expression.partition("/")
        unit = unit.strip().lower().rstrip("s")
        if unit not in _UNITS:
            raise ValueError(f"Unidade de rate limit inválida: {expression!r}")
        return cls(limit=int(raw_limit), window_seconds=_UNITS[unit])


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


async def check_rate_limit(key: str, rule: RateLimitRule) -> RateLimitResult:
    """Consome uma unidade da janela e informa se a requisição é permitida."""
    if not settings.rate_limit_enabled:
        return RateLimitResult(True, rule.limit, rule.limit, 0)

    now = time.time()
    member = f"{now}:{time.monotonic_ns()}"
    try:
        allowed, remaining, retry = await get_redis().eval(  # type: ignore[misc]
            _LUA_SLIDING_WINDOW,
            1,
            f"rl:{key}",
            now,
            rule.window_seconds,
            rule.limit,
            member,
        )
    except (RedisError, OSError) as exc:
        logger.warning("rate_limit.unavailable", error=str(exc), key=key)
        return RateLimitResult(True, rule.limit, rule.limit, 0)

    return RateLimitResult(
        allowed=bool(allowed),
        limit=rule.limit,
        remaining=int(remaining),
        retry_after=int(retry),
    )
