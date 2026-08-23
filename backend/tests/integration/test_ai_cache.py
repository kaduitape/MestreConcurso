"""O cache persistente precisa evitar de fato uma segunda chamada paga."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.ai_cache import AICacheService, fingerprint
from tests.conftest import CapturingDispatcher
from tests.factories import create_admin


def _key(payload: dict[str, Any]) -> str:
    return fingerprint(
        feature="board.profile",
        model_slug="gpt-4o-mini",
        prompt_version="v1",
        payload=payload,
    )


async def test_store_then_hit_avoids_new_call(db_session: AsyncSession) -> None:
    service = AICacheService(db_session)
    key = _key({"board": "cespe"})

    assert await service.get(key) is None

    await service.store(
        cache_key=key,
        feature="board.profile",
        provider_slug="openai",
        model_slug="gpt-4o-mini",
        payload={"resumo": "banca literal"},
        prompt_version="v1",
        input_tokens=900,
        output_tokens=300,
        cost_cents=Decimal("0.42"),
    )

    hit = await service.get(key)
    assert hit is not None
    assert hit.payload["resumo"] == "banca literal"
    assert hit.hits == 1

    again = await service.get(key)
    assert again is not None
    assert again.hits == 2


async def test_expired_entry_is_not_served(db_session: AsyncSession) -> None:
    from datetime import UTC, datetime, timedelta

    service = AICacheService(db_session)
    key = _key({"board": "fgv"})
    entry = await service.store(
        cache_key=key,
        feature="board.profile",
        provider_slug="openai",
        model_slug="gpt-4o-mini",
        payload={"resumo": "antigo"},
        ttl_hours=1,
    )
    entry.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    assert await service.get(key) is None


async def test_stats_report_tokens_saved(db_session: AsyncSession) -> None:
    service = AICacheService(db_session)
    key = _key({"board": "cesgranrio"})
    await service.store(
        cache_key=key,
        feature="board.profile",
        provider_slug="openai",
        model_slug="gpt-4o-mini",
        payload={"resumo": "x"},
        input_tokens=1000,
        output_tokens=200,
        cost_cents=Decimal("1.5"),
    )
    await service.get(key)
    await service.get(key)

    stats = await service.stats()
    assert stats.entries == 1
    assert stats.total_hits == 2
    assert stats.tokens_stored == 1200
    # Dois acertos evitaram duas chamadas de 1200 tokens cada.
    assert stats.tokens_saved == 2400
    assert stats.cost_saved_cents == Decimal("3.0")


async def test_purge_removes_entries(db_session: AsyncSession) -> None:
    service = AICacheService(db_session)
    await service.store(
        cache_key=_key({"board": "a"}),
        feature="board.profile",
        provider_slug="openai",
        model_slug="gpt-4o-mini",
        payload={},
    )
    await service.store(
        cache_key=_key({"board": "b"}),
        feature="chat.tutor",
        provider_slug="openai",
        model_slug="gpt-4o-mini",
        payload={},
    )

    assert await service.purge(feature="chat.tutor") == 1
    assert (await service.stats()).entries == 1


async def test_cache_endpoint_reports_and_purges(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="cache@exemplo.com.br")
    service = AICacheService(db_session)
    key = _key({"board": "quadrix"})
    await service.store(
        cache_key=key,
        feature="board.profile",
        provider_slug="openai",
        model_slug="gpt-4o-mini",
        payload={"resumo": "y"},
        input_tokens=500,
        output_tokens=100,
    )
    await service.get(key)

    stats = await client.get("/api/v1/admin/ai/cache", headers=admin.auth_header)
    assert stats.status_code == 200
    assert stats.json()["entries"] == 1
    assert stats.json()["tokens_saved"] == 600

    purged = await client.delete("/api/v1/admin/ai/cache", headers=admin.auth_header)
    assert purged.status_code == 200
    assert purged.json()["detail"]["removed"] == 1
