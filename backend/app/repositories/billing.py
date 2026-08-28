"""Consultas da camada comercial."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.billing import (
    Coupon,
    CouponRedemption,
    InvoiceLine,
    Payment,
    PaymentProviderConfig,
    Plan,
    Subscription,
    UsageCounter,
    WebhookEvent,
)
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    async def get_by_slug(self, slug: str) -> Plan | None:
        stmt = (
            select(Plan)
            .options(selectinload(Plan.entitlements))
            .where(Plan.slug == slug)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def public_plans(self) -> Sequence[Plan]:
        stmt = (
            select(Plan)
            .options(selectinload(Plan.entitlements))
            .where(Plan.is_active.is_(True), Plan.is_public.is_(True))
            .order_by(Plan.sort_order, Plan.price_cents)
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def all_plans(self) -> Sequence[Plan]:
        stmt = (
            select(Plan)
            .options(selectinload(Plan.entitlements))
            .order_by(Plan.sort_order, Plan.price_cents)
        )
        return (await self.session.execute(stmt)).scalars().all()


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def current_for(self, user_id: int) -> Subscription | None:
        """A assinatura mais recente do candidato, seja qual for o estado."""
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.id.desc())
            .limit(1)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def get_by_public_id(self, public_id: str) -> Subscription | None:
        return await self.get_by(public_id=public_id)

    async def active_snapshots(self, statuses: Sequence[str]) -> Sequence[Subscription]:
        stmt = (
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(Subscription.status.in_(statuses))
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def canceled_between(self, start: datetime, end: datetime) -> int:
        stmt = select(func.count()).where(
            Subscription.canceled_at.is_not(None),
            Subscription.canceled_at >= start,
            Subscription.canceled_at <= end,
        )
        return int((await self.session.execute(stmt)).scalar_one())


class CouponRepository(BaseRepository[Coupon]):
    model = Coupon

    async def get_by_code(self, code: str) -> Coupon | None:
        return await self.get_by(code=code.strip().upper())

    async def redeemed_by(self, coupon_id: int, user_id: int) -> bool:
        stmt = select(CouponRedemption.id).where(
            CouponRedemption.coupon_id == coupon_id, CouponRedemption.user_id == user_id
        )
        return (await self.session.execute(stmt)).first() is not None

    async def all_coupons(self) -> Sequence[Coupon]:
        stmt = select(Coupon).order_by(Coupon.id.desc())
        return (await self.session.execute(stmt)).scalars().all()


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def get_by_reference(self, reference: str) -> Payment | None:
        return await self.get_by(reference=reference)

    async def get_by_provider_reference(self, provider_reference: str) -> Payment | None:
        return await self.get_by(provider_reference=provider_reference)

    async def history(self, user_id: int, *, limit: int = 30) -> Sequence[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.user_id == user_id)
            .order_by(Payment.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()


class UsageRepository(BaseRepository[UsageCounter]):
    model = UsageCounter

    async def get_window(
        self, user_id: int, feature: str, window_start: date
    ) -> UsageCounter | None:
        return await self.get_by(user_id=user_id, feature=feature, window_start=window_start)


class WebhookRepository(BaseRepository[WebhookEvent]):
    model = WebhookEvent

    async def get_event(self, provider: str, event_id: str) -> WebhookEvent | None:
        return await self.get_by(provider=provider, event_id=event_id)


class PaymentConfigRepository(BaseRepository[PaymentProviderConfig]):
    model = PaymentProviderConfig

    async def get_by_slug(self, slug: str) -> PaymentProviderConfig | None:
        return await self.get_by(slug=slug)


class InvoiceRepository(BaseRepository[InvoiceLine]):
    model = InvoiceLine

    async def history(self, user_id: int, *, limit: int = 30) -> Sequence[InvoiceLine]:
        stmt = (
            select(InvoiceLine)
            .where(InvoiceLine.user_id == user_id)
            .order_by(InvoiceLine.id.desc())
            .limit(limit)
        )
        return (await self.session.execute(stmt)).scalars().all()
