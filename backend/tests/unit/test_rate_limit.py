"""Testes das regras de rate limit."""

from __future__ import annotations

import pytest

from app.core.pagination import Page, PageParams
from app.core.rate_limit import RateLimitRule


@pytest.mark.parametrize(
    ("expression", "limit", "window"),
    [("10/minute", 10, 60), ("5/hour", 5, 3600), ("120/second", 120, 1), ("3/day", 3, 86400)],
)
def test_rule_parsing(expression: str, limit: int, window: int) -> None:
    rule = RateLimitRule.parse(expression)
    assert rule.limit == limit
    assert rule.window_seconds == window


def test_invalid_rule_raises() -> None:
    with pytest.raises(ValueError, match="Unidade de rate limit inválida"):
        RateLimitRule.parse("10/fortnight")


def test_pagination_math() -> None:
    params = PageParams(page=3, page_size=20)
    assert params.offset == 40
    page = Page.create(["a", "b"], total=45, params=params)
    assert page.pages == 3
    assert page.total == 45
    assert Page.create([], total=0, params=params).pages == 0


async def test_fails_open_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Indisponibilidade do Redis não pode bloquear o login de todos os usuários."""
    from redis.exceptions import ConnectionError as RedisConnectionError

    from app.core import rate_limit as module

    class BrokenRedis:
        async def eval(self, *args: object, **kwargs: object) -> object:
            raise RedisConnectionError("redis fora do ar")

    monkeypatch.setattr(module.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(module, "get_redis", lambda: BrokenRedis())
    result = await module.check_rate_limit("auth:login:1.2.3.4", RateLimitRule.parse("2/minute"))
    assert result.allowed is True


async def test_disabled_rate_limit_always_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import rate_limit as module

    monkeypatch.setattr(module.settings, "rate_limit_enabled", False)
    result = await module.check_rate_limit("qualquer", RateLimitRule.parse("1/minute"))
    assert result.allowed is True
    assert result.remaining == 1
