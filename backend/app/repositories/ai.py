"""Consultas da configuração de IA e do cache persistente."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.ai import (
    AICacheEntry,
    AIFeatureBinding,
    AIModel,
    AIModelRoute,
    AIProviderConfig,
    AIRoutingDecision,
)
from app.repositories.base import BaseRepository


class AIProviderRepository(BaseRepository[AIProviderConfig]):
    model = AIProviderConfig

    async def get_by_slug(self, slug: str) -> AIProviderConfig | None:
        stmt = (
            select(AIProviderConfig)
            .where(AIProviderConfig.slug == slug)
            .options(selectinload(AIProviderConfig.models))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> Sequence[AIProviderConfig]:
        stmt = (
            select(AIProviderConfig)
            .options(selectinload(AIProviderConfig.models))
            .order_by(AIProviderConfig.slug)
        )
        return (await self.session.execute(stmt)).scalars().all()


class AIModelRepository(BaseRepository[AIModel]):
    model = AIModel

    async def get_by_slug(self, provider_id: int, slug: str) -> AIModel | None:
        return await self.get_by(provider_id=provider_id, slug=slug)

    async def list_for_provider(self, provider_id: int) -> Sequence[AIModel]:
        stmt = (
            select(AIModel)
            .where(AIModel.provider_id == provider_id)
            .order_by(AIModel.kind, AIModel.slug)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_with_provider(self, model_id: int) -> AIModel | None:
        stmt = select(AIModel).where(AIModel.id == model_id).options(selectinload(AIModel.provider))
        return (await self.session.execute(stmt)).scalar_one_or_none()


class AIFeatureBindingRepository(BaseRepository[AIFeatureBinding]):
    model = AIFeatureBinding

    async def get_by_feature(self, feature: str) -> AIFeatureBinding | None:
        stmt = (
            select(AIFeatureBinding)
            .where(AIFeatureBinding.feature == feature)
            .options(
                selectinload(AIFeatureBinding.model).selectinload(AIModel.provider),
                selectinload(AIFeatureBinding.fallback_model).selectinload(AIModel.provider),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> Sequence[AIFeatureBinding]:
        stmt = (
            select(AIFeatureBinding)
            .options(
                selectinload(AIFeatureBinding.model).selectinload(AIModel.provider),
                selectinload(AIFeatureBinding.fallback_model).selectinload(AIModel.provider),
            )
            .order_by(AIFeatureBinding.feature)
        )
        return (await self.session.execute(stmt)).scalars().all()


class AICacheRepository(BaseRepository[AICacheEntry]):
    model = AICacheEntry

    async def get_by_fingerprint(self, fingerprint: str) -> AICacheEntry | None:
        stmt = select(AICacheEntry).where(AICacheEntry.fingerprint == fingerprint)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class AIModelRouteRepository(BaseRepository[AIModelRoute]):
    model = AIModelRoute

    async def list_for_feature(self, feature: str) -> Sequence[AIModelRoute]:
        stmt = (
            select(AIModelRoute)
            .where(AIModelRoute.feature == feature)
            .options(selectinload(AIModelRoute.model).selectinload(AIModel.provider))
            .order_by(AIModelRoute.priority, AIModelRoute.id)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def list_all(self) -> Sequence[AIModelRoute]:
        stmt = (
            select(AIModelRoute)
            .options(selectinload(AIModelRoute.model).selectinload(AIModel.provider))
            .order_by(AIModelRoute.feature, AIModelRoute.priority, AIModelRoute.id)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_with_model(self, route_id: int) -> AIModelRoute | None:
        stmt = (
            select(AIModelRoute)
            .where(AIModelRoute.id == route_id)
            .options(selectinload(AIModelRoute.model).selectinload(AIModel.provider))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_for_feature(self, feature: str) -> int:
        stmt = select(func.count(AIModelRoute.id)).where(AIModelRoute.feature == feature)
        return int((await self.session.execute(stmt)).scalar_one() or 0)


class AIRoutingDecisionRepository(BaseRepository[AIRoutingDecision]):
    model = AIRoutingDecision

    async def recent(
        self, *, feature: str | None = None, limit: int = 50
    ) -> Sequence[AIRoutingDecision]:
        stmt = select(AIRoutingDecision).order_by(AIRoutingDecision.id.desc()).limit(limit)
        if feature:
            stmt = stmt.where(AIRoutingDecision.feature == feature)
        return (await self.session.execute(stmt)).scalars().all()
