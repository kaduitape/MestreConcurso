"""Direitos de uso e limites — a parte "limitar" do ciclo comercial.

Este serviço resolve o que o candidato pode fazer **a partir do banco**. Nenhum
limite é lido do código: o catálogo de fábrica só semeia a tabela na primeira
subida, e a partir daí mudar um teto é um `UPDATE`.

Sem assinatura ativa, o candidato cai no plano gratuito — que existe justamente
para que "não assinou" tenha direitos definidos, em vez de virar uma sequência de
condicionais espalhadas pelo sistema.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.logging import get_logger
from app.domain.billing.plans import (
    DEFAULT_PLANS,
    FALLBACK_PLAN_SLUG,
    Entitlement,
    EntitlementSet,
)
from app.domain.billing.quota import QuotaCheck, check, window_for
from app.domain.billing.subscription import SubscriptionState as DomainState
from app.domain.billing.subscription import (
    SubscriptionStatus,
    grace_deadline,
    is_entitled,
    next_status,
    period_end_for,
)
from app.models.billing import (
    Plan,
    PlanEntitlement,
    Subscription,
    SubscriptionEvent,
    UsageCounter,
)
from app.models.user import User
from app.repositories.billing import PlanRepository, SubscriptionRepository, UsageRepository

logger = get_logger(__name__)


class QuotaExceededError(AppError):
    """Recusa por limite. Traz o que foi usado e o que fazer a respeito."""

    status_code = 402
    code = "quota_exceeded"
    message = "Limite do plano atingido."


class FeatureNotIncludedError(AppError):
    status_code = 402
    code = "feature_not_included"
    message = "Este recurso não está incluído no seu plano."


@dataclass(frozen=True, slots=True)
class Access:
    """O contexto comercial do candidato, já resolvido."""

    plan: Plan
    subscription: Subscription | None
    entitlements: EntitlementSet
    status: str
    #: Data de aniversário da assinatura — âncora das janelas mensais.
    anchor: date | None


class EntitlementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.plans = PlanRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.usage = UsageRepository(session)

    # ------------------------------------------------------------------ #
    # Catálogo
    # ------------------------------------------------------------------ #
    async def sync_plans(self) -> int:
        """Semeia os planos de fábrica que ainda não existem no banco."""
        existing = {plan.slug for plan in await self.plans.all_plans()}
        created = 0
        for spec in DEFAULT_PLANS:
            if spec.slug in existing:
                continue
            plan = Plan(
                slug=spec.slug,
                name=spec.name,
                description=spec.description,
                price_cents=spec.price_cents,
                months=12 if spec.slug.endswith("anual") else 1,
                trial_days=spec.trial_days,
                is_public=spec.is_public,
                sort_order=spec.sort_order,
            )
            plan.entitlements = [
                PlanEntitlement(
                    feature=item.feature,
                    is_enabled=item.enabled,
                    limit_value=item.limit,
                    period=item.period,
                )
                for item in spec.entitlements
            ]
            self.session.add(plan)
            created += 1
        if created:
            await self.session.commit()
            logger.info("billing.plans_seeded", created=created)
        return created

    async def fallback_plan(self) -> Plan:
        await self.sync_plans()
        plan = await self.plans.get_by_slug(FALLBACK_PLAN_SLUG)
        if plan is None:  # pragma: no cover — sync_plans acabou de criar
            raise AppError("Plano gratuito não encontrado.")
        return plan

    # ------------------------------------------------------------------ #
    # Resolução
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_set(plan: Plan) -> EntitlementSet:
        return EntitlementSet(
            plan_slug=plan.slug,
            plan_name=plan.name,
            items={
                item.feature: Entitlement(
                    feature=item.feature,
                    enabled=item.is_enabled,
                    limit=item.limit_value,
                    period=item.period,
                )
                for item in plan.entitlements
            },
        )

    async def apply_scheduled_downgrade(self, subscription: Subscription, *, today: date) -> bool:
        """Aplica o downgrade agendado quando o período vira. Devolve se aplicou.

        Mora aqui, e não no serviço de assinatura, porque é a mesma categoria de
        coisa que já acontece nesta função: uma transição que **o tempo produz**.
        Deixá-la só no caminho de escrita foi o erro que fez a troca agendada
        nunca chegar a acontecer.
        """
        if subscription.scheduled_plan_id is None:
            return False
        if subscription.current_period_end is not None and today <= subscription.current_period_end:
            return False

        target = await self.session.get(Plan, subscription.scheduled_plan_id)
        if target is None:
            # O plano agendado sumiu do catálogo: o agendamento morre junto,
            # em vez de deixar a assinatura apontando para o nada.
            subscription.scheduled_plan_id = None
            await self.session.commit()
            return False

        previous_status = subscription.status
        subscription.plan_id = target.id
        subscription.scheduled_plan_id = None
        subscription.current_period_start = day_start = today
        subscription.current_period_end = period_end_for(day_start, months=target.months)
        if target.price_cents == 0:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.grace_ends_on = None
        else:
            # Plano pago recém-ativado ainda não foi cobrado. Sem abrir a
            # tolerância, o candidato perderia acesso na virada sem ter tido
            # chance de pagar — o mesmo erro de cortar antes da hora.
            subscription.status = SubscriptionStatus.PAST_DUE
            subscription.grace_ends_on = grace_deadline(today)
        self.session.add(
            SubscriptionEvent(
                subscription_id=subscription.id,
                kind="DOWNGRADE_APPLIED",
                from_status=previous_status,
                to_status=subscription.status,
                detail=f"Plano alterado para {target.name} na virada do período.",
                meta={"to_plan": target.slug},
            )
        )
        await self.session.commit()
        logger.info(
            "billing.downgrade_applied",
            subscription=subscription.public_id,
            plan=target.slug,
        )
        return True

    async def access_for(self, user: User, *, today: date | None = None) -> Access:
        """Descobre o plano vigente do candidato — e atualiza o que o tempo mudou."""
        day = today or datetime.now(UTC).date()
        subscription = await self.subscriptions.current_for(user.id)

        if subscription is None:
            plan = await self.fallback_plan()
            return Access(
                plan=plan,
                subscription=None,
                entitlements=self._to_set(plan),
                status="NONE",
                anchor=None,
            )

        # A troca agendada vem antes de tudo: ela redefine plano e período, e o
        # estado precisa ser avaliado sobre o período novo.
        await self.apply_scheduled_downgrade(subscription, today=day)

        state = DomainState(
            status=subscription.status,
            current_period_end=subscription.current_period_end,
            trial_ends_on=subscription.trial_ends_on,
            grace_ends_on=subscription.grace_ends_on,
        )
        # O tempo, sozinho, muda estado: teste que venceu, período que virou.
        evolved = next_status(state, today=day)
        if evolved != subscription.status:
            subscription.status = evolved
            await self.session.commit()
            state = DomainState(
                status=evolved,
                current_period_end=subscription.current_period_end,
                trial_ends_on=subscription.trial_ends_on,
                grace_ends_on=subscription.grace_ends_on,
            )

        if not is_entitled(state, today=day):
            plan = await self.fallback_plan()
            return Access(
                plan=plan,
                subscription=subscription,
                entitlements=self._to_set(plan),
                status=subscription.status,
                anchor=None,
            )

        stored = await self.session.get(Plan, subscription.plan_id)
        plan = stored or await self.fallback_plan()
        return Access(
            plan=plan,
            subscription=subscription,
            entitlements=self._to_set(plan),
            status=subscription.status,
            anchor=subscription.started_on,
        )

    # ------------------------------------------------------------------ #
    # Consumo
    # ------------------------------------------------------------------ #
    async def _used(
        self,
        user: User,
        feature: str,
        entitlement: Entitlement,
        *,
        today: date,
        anchor: date | None,
    ) -> tuple[int, UsageCounter | None, date]:
        window = window_for(entitlement.period, today=today, anchor=anchor)
        counter = await self.usage.get_window(user.id, feature, window.starts_on)
        return (counter.used if counter else 0), counter, window.starts_on

    async def check(self, user: User, feature: str, *, today: date | None = None) -> QuotaCheck:
        """Diz se cabe mais um uso — sem consumir nada."""
        day = today or datetime.now(UTC).date()
        access = await self.access_for(user, today=day)
        entitlement = access.entitlements.get(feature)
        used, _, _ = await self._used(user, feature, entitlement, today=day, anchor=access.anchor)
        return check(
            entitlement,
            used=used,
            today=day,
            anchor=access.anchor,
            plan_name=access.plan.name,
        )

    async def consume(
        self, user: User, feature: str, *, amount: int = 1, today: date | None = None
    ) -> QuotaCheck:
        """Verifica e registra o uso. Recusa vira erro com o motivo em texto.

        A ordem importa: verificamos **antes** de gastar. Registrar primeiro e
        conferir depois deixaria o contador subir em chamadas recusadas.
        """
        day = today or datetime.now(UTC).date()
        access = await self.access_for(user, today=day)
        entitlement = access.entitlements.get(feature)
        used, counter, window_start = await self._used(
            user, feature, entitlement, today=day, anchor=access.anchor
        )
        result = check(
            entitlement,
            used=used,
            today=day,
            anchor=access.anchor,
            plan_name=access.plan.name,
        )

        if not result.allowed:
            error = FeatureNotIncludedError if not entitlement.enabled else QuotaExceededError
            raise error(
                result.reason,
                details={
                    "feature": feature,
                    "limit": result.limit,
                    "used": result.used,
                    "period": result.period,
                    "resets_on": result.resets_on.isoformat() if result.resets_on else None,
                    "plan": access.plan.slug,
                },
            )

        if entitlement.limit is None:
            # Recurso ilimitado não precisa de contador: a linha só existiria
            # para crescer sem nunca ser lida.
            return result

        window = window_for(entitlement.period, today=day, anchor=access.anchor)
        if counter is None:
            counter = UsageCounter(
                user_id=user.id,
                feature=feature,
                window_start=window_start,
                window_end=window.ends_on,
                used=0,
            )
            self.session.add(counter)
            try:
                await self.session.flush()
            except IntegrityError:
                # Corrida entre duas chamadas: a linha já existe, releia.
                await self.session.rollback()
                stored = await self.usage.get_window(user.id, feature, window_start)
                if stored is None:
                    raise
                counter = stored

        counter.used += max(1, amount)
        await self.session.commit()

        return QuotaCheck(
            feature=result.feature,
            label=result.label,
            allowed=True,
            limit=result.limit,
            used=counter.used,
            remaining=max(0, (result.limit or 0) - counter.used),
            period=result.period,
            resets_on=result.resets_on,
        )

    async def summary(self, user: User, *, today: date | None = None) -> list[QuotaCheck]:
        """Todos os direitos do plano, com o que já foi usado em cada um."""
        day = today or datetime.now(UTC).date()
        access = await self.access_for(user, today=day)
        result: list[QuotaCheck] = []
        for feature, entitlement in sorted(access.entitlements.items.items()):
            used, _, _ = await self._used(
                user, feature, entitlement, today=day, anchor=access.anchor
            )
            result.append(
                check(
                    entitlement,
                    used=used,
                    today=day,
                    anchor=access.anchor,
                    plan_name=access.plan.name,
                )
            )
        return result
