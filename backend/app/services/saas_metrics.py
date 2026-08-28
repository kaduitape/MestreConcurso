"""Painel SaaS — MRR, churn, ARPU e custo de IA, com denominador à vista.

O serviço só reúne os números; quem decide o que pode ser afirmado é
``app.domain.billing.metrics``. É lá que mora a regra de que churn de período
aberto não é churn e que indicador sem base é ``None`` com motivo, nunca zero.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.billing.metrics import SaasMetrics, SubscriptionSnapshot, build
from app.domain.billing.subscription import SubscriptionStatus
from app.models.ai import AIUsage
from app.models.billing import Plan, Subscription
from app.repositories.billing import SubscriptionRepository

#: Estados que representam receita vigente. Teste não é receita: ninguém pagou.
PAYING_STATES = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.PAST_DUE,
    SubscriptionStatus.CANCELING,
)


class SaasMetricsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subscriptions = SubscriptionRepository(session)

    async def build(self, *, today: date | None = None) -> SaasMetrics:
        day = today or datetime.now(UTC).date()
        # O período de referência é o mês anterior fechado — é o único sobre o
        # qual churn pode ser afirmado.
        first_of_month = day.replace(day=1)
        period_end = first_of_month - timedelta(days=1)
        period_start = period_end.replace(day=1)

        rows = (
            await self.session.execute(
                select(Plan.slug, Plan.price_cents, Plan.months)
                .join(Subscription, Subscription.plan_id == Plan.id)
                .where(Subscription.status.in_(PAYING_STATES))
            )
        ).all()
        snapshots = [
            SubscriptionSnapshot(
                plan_slug=str(row[0]), price_cents=int(row[1]), months=int(row[2] or 1)
            )
            for row in rows
        ]

        started = datetime.combine(period_start, datetime.min.time(), tzinfo=UTC)
        ended = datetime.combine(period_end, datetime.max.time(), tzinfo=UTC)

        active_at_start = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        Subscription.started_on <= period_start,
                        Subscription.status.in_((*PAYING_STATES, SubscriptionStatus.CANCELED)),
                    )
                )
            ).scalar_one()
        )
        canceled = await self.subscriptions.canceled_between(started, ended)

        usage = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(AIUsage.cost_cents), 0),
                    func.count(),
                ).where(AIUsage.created_at >= started, AIUsage.created_at <= ended)
            )
        ).one()

        return build(
            subscriptions=snapshots,
            active_at_start=active_at_start,
            canceled_in_period=canceled,
            # O mês anterior sempre está fechado quando lido no mês corrente.
            period_closed=True,
            cost_cents=float(usage[0]),
            ai_calls=int(usage[1]),
            period_start=period_start,
            period_end=period_end,
        )
