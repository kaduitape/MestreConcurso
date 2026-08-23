"""Cache persistente de respostas de IA.

Motivo de existir: nenhuma pergunta já respondida deve ser paga duas vezes. A
chave é a impressão digital determinística de (funcionalidade + modelo + versão do
prompt + entrada), então a mesma análise de banca, edital ou questão é servida do
banco em vez de ir ao provedor.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ai import AICacheEntry
from app.repositories.ai import AICacheRepository
from app.repositories.base import rowcount

logger = get_logger(__name__)


def fingerprint(*, feature: str, model_slug: str, prompt_version: str | None, payload: Any) -> str:
    """Impressão digital estável da requisição (chaves ordenadas, sem espaços)."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    raw = f"{feature}|{model_slug}|{prompt_version or '-'}|{canonical}"
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class CacheStats:
    entries: int
    total_hits: int
    tokens_stored: int
    tokens_saved: int
    cost_saved_cents: Decimal
    expired_entries: int


class AICacheService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AICacheRepository(session)

    async def get(self, cache_key: str) -> AICacheEntry | None:
        """Devolve a entrada válida e contabiliza o acerto (economia real)."""
        entry = await self.repository.get_by_fingerprint(cache_key)
        if entry is None:
            return None

        expires_at = entry.expires_at
        if expires_at is not None:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if expires_at <= datetime.now(UTC):
                logger.info("ai_cache.expired", feature=entry.feature)
                return None

        entry.hits += 1
        entry.last_hit_at = datetime.now(UTC)
        await self.session.commit()
        logger.info("ai_cache.hit", feature=entry.feature, hits=entry.hits)
        return entry

    async def store(
        self,
        *,
        cache_key: str,
        feature: str,
        provider_slug: str,
        model_slug: str,
        payload: dict[str, Any],
        prompt_version: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_cents: Decimal | float | int = 0,
        ttl_hours: int | None = None,
    ) -> AICacheEntry:
        """Grava (ou atualiza) a resposta para reaproveitamento futuro."""
        entry = await self.repository.get_by_fingerprint(cache_key)
        expires_at = datetime.now(UTC) + timedelta(hours=ttl_hours) if ttl_hours else None

        if entry is None:
            entry = AICacheEntry(fingerprint=cache_key, feature=feature)
            self.session.add(entry)

        entry.provider_slug = provider_slug
        entry.model_slug = model_slug
        entry.prompt_version = prompt_version
        entry.payload = payload
        entry.input_tokens = input_tokens
        entry.output_tokens = output_tokens
        entry.cost_cents = Decimal(str(cost_cents))
        entry.expires_at = expires_at

        await self.session.commit()
        logger.info("ai_cache.stored", feature=feature, model=model_slug)
        return entry

    async def stats(self) -> CacheStats:
        """Números derivados dos contadores reais — nada é estimado."""
        row = (
            await self.session.execute(
                select(
                    func.count(AICacheEntry.id),
                    func.coalesce(func.sum(AICacheEntry.hits), 0),
                    func.coalesce(
                        func.sum(AICacheEntry.input_tokens + AICacheEntry.output_tokens), 0
                    ),
                    func.coalesce(
                        func.sum(
                            AICacheEntry.hits
                            * (AICacheEntry.input_tokens + AICacheEntry.output_tokens)
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(AICacheEntry.hits * AICacheEntry.cost_cents), 0),
                )
            )
        ).one()

        expired = int(
            (
                await self.session.execute(
                    select(func.count(AICacheEntry.id)).where(
                        AICacheEntry.expires_at.is_not(None),
                        AICacheEntry.expires_at <= datetime.now(UTC),
                    )
                )
            ).scalar_one()
        )

        return CacheStats(
            entries=int(row[0]),
            total_hits=int(row[1]),
            tokens_stored=int(row[2]),
            tokens_saved=int(row[3]),
            cost_saved_cents=Decimal(str(row[4])),
            expired_entries=expired,
        )

    async def purge(self, *, feature: str | None = None, expired_only: bool = False) -> int:
        stmt = delete(AICacheEntry)
        if feature:
            stmt = stmt.where(AICacheEntry.feature == feature)
        if expired_only:
            stmt = stmt.where(
                AICacheEntry.expires_at.is_not(None),
                AICacheEntry.expires_at <= datetime.now(UTC),
            )
        removed = rowcount(await self.session.execute(stmt))
        await self.session.commit()
        logger.info("ai_cache.purged", removed=removed, feature=feature)
        return removed
