"""Assinaturas: contratar, trocar de plano e cancelar.

A regra que evita o erro mais caro deste arquivo: **cancelar não corta na hora**.
Quem pagou até o dia 30 tem acesso até o dia 30. Cortar antes é cobrar por
serviço não entregue — e é o tipo de decisão que a pressa de código costuma
tomar sozinha.

Todo movimento vira uma linha em ``subscription_events``. Quando alguém
perguntar "por que meu acesso mudou?", a resposta existe.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.billing.coupons import Coupon as CouponSpec
from app.domain.billing.coupons import CouponResult
from app.domain.billing.coupons import apply as apply_coupon
from app.domain.billing.subscription import (
    ChangeDecision,
    ChangeKind,
    SubscriptionStatus,
    decide_change,
    grace_deadline,
    period_end_for,
)
from app.models.billing import (
    Coupon,
    CouponRedemption,
    InvoiceLine,
    Payment,
    PaymentStatus,
    Plan,
    Subscription,
    SubscriptionEvent,
)
from app.models.user import User
from app.repositories.billing import (
    CouponRepository,
    InvoiceRepository,
    PaymentRepository,
    PlanRepository,
    SubscriptionRepository,
)
from app.services.entitlements import EntitlementService

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SubscribeResult:
    subscription: Subscription
    payment: Payment | None
    #: Nulo em plano gratuito ou em teste: não há o que cobrar agora.
    checkout_url: str | None
    coupon: CouponResult | None
    detail: str


def _reference() -> str:
    """Referência nossa da cobrança — é ela que amarra webhook e pagamento."""
    return f"sub_{secrets.token_urlsafe(12)}"


class BillingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.plans = PlanRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.coupons = CouponRepository(session)
        self.payments = PaymentRepository(session)
        self.invoices = InvoiceRepository(session)
        self.entitlements = EntitlementService(session)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def public_plans(self) -> list[Plan]:
        await self.entitlements.sync_plans()
        return list(await self.plans.public_plans())

    async def current(self, user: User) -> Subscription | None:
        """A assinatura **já atualizada** pelo que o tempo mudou.

        Passa por ``access_for`` de propósito: é ele que aplica a troca agendada
        e move o estado (teste vencido, período virado). Ler a linha crua daria
        um retrato desatualizado para quem só consulta.
        """
        access = await self.entitlements.access_for(user)
        return access.subscription

    def _record(
        self,
        subscription: Subscription,
        *,
        kind: str,
        detail: str,
        from_status: str | None = None,
        to_status: str | None = None,
        meta: dict[str, object] | None = None,
    ) -> None:
        self.session.add(
            SubscriptionEvent(
                subscription_id=subscription.id,
                kind=kind,
                from_status=from_status,
                to_status=to_status,
                detail=detail,
                meta=meta or {},
            )
        )

    # ------------------------------------------------------------------ #
    # Cupom
    # ------------------------------------------------------------------ #
    async def preview_coupon(
        self, user: User, *, code: str, plan_slug: str, today: date | None = None
    ) -> CouponResult:
        day = today or datetime.now(UTC).date()
        await self.entitlements.sync_plans()
        plan = await self.plans.get_by_slug(plan_slug)
        if plan is None:
            raise NotFoundError("Plano não encontrado.")

        stored = await self.coupons.get_by_code(code)
        if stored is None:
            return CouponResult(
                valid=False,
                discount_cents=0,
                final_cents=plan.price_cents,
                reason="Cupom não encontrado.",
            )

        return apply_coupon(
            self._coupon_spec(stored),
            amount_cents=plan.price_cents,
            today=day,
            plan_slug=plan.slug,
            already_used_by_user=await self.coupons.redeemed_by(stored.id, user.id),
        )

    @staticmethod
    def _coupon_spec(stored: Coupon) -> CouponSpec:
        return CouponSpec(
            code=stored.code,
            kind=stored.kind,
            value=stored.value,
            is_active=stored.is_active,
            starts_on=stored.starts_on,
            ends_on=stored.ends_on,
            max_redemptions=stored.max_redemptions,
            redeemed=stored.redeemed,
            plan_slugs=tuple(stored.plan_slugs or ()),
            once_per_user=stored.once_per_user,
            min_amount_cents=stored.min_amount_cents,
        )

    # ------------------------------------------------------------------ #
    # Contratação
    # ------------------------------------------------------------------ #
    async def subscribe(
        self,
        user: User,
        *,
        plan_slug: str,
        coupon_code: str | None = None,
        today: date | None = None,
    ) -> SubscribeResult:
        """Contrata um plano. Cobrança e liberação são passos separados.

        A assinatura nasce pendente quando há valor a pagar: quem libera o acesso
        é a confirmação do pagamento, não o clique em "assinar".
        """
        day = today or datetime.now(UTC).date()
        await self.entitlements.sync_plans()

        plan = await self.plans.get_by_slug(plan_slug)
        if plan is None or not plan.is_active:
            raise NotFoundError("Plano não encontrado.")

        existing = await self.subscriptions.current_for(user.id)
        if existing is not None and existing.status in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.CANCELING,
        }:
            raise ConflictError(
                "Você já tem uma assinatura em vigor. Use a troca de plano.",
                code="subscription_already_active",
            )

        coupon_result: CouponResult | None = None
        stored_coupon: Coupon | None = None
        amount = plan.price_cents
        if coupon_code:
            stored_coupon = await self.coupons.get_by_code(coupon_code)
            if stored_coupon is None:
                raise ValidationError("Cupom não encontrado.", code="coupon_not_found")
            coupon_result = apply_coupon(
                self._coupon_spec(stored_coupon),
                amount_cents=amount,
                today=day,
                plan_slug=plan.slug,
                already_used_by_user=await self.coupons.redeemed_by(stored_coupon.id, user.id),
            )
            if not coupon_result.valid:
                raise ValidationError(coupon_result.reason, code="coupon_invalid")
            amount = coupon_result.final_cents

        trial_ends = day + timedelta(days=plan.trial_days) if plan.trial_days > 0 else None
        if plan.price_cents == 0:
            status = SubscriptionStatus.ACTIVE
        elif trial_ends is not None:
            status = SubscriptionStatus.TRIALING
        else:
            status = SubscriptionStatus.PAST_DUE

        subscription = Subscription(
            user_id=user.id,
            plan_id=plan.id,
            status=status,
            started_on=day,
            current_period_start=day,
            current_period_end=period_end_for(day, months=plan.months),
            trial_ends_on=trial_ends,
            grace_ends_on=grace_deadline(day) if status == SubscriptionStatus.PAST_DUE else None,
            coupon_id=stored_coupon.id if stored_coupon else None,
        )
        self.session.add(subscription)
        await self.session.flush()

        self._record(
            subscription,
            kind="SUBSCRIBED",
            detail=f"Assinatura do plano {plan.name} criada.",
            to_status=status,
            meta={"plan": plan.slug, "amount_cents": amount},
        )

        payment: Payment | None = None
        if amount > 0:
            payment = Payment(
                user_id=user.id,
                subscription_id=subscription.id,
                plan_id=plan.id,
                reference=_reference(),
                status=PaymentStatus.PENDING,
                amount_cents=amount,
                discount_cents=coupon_result.discount_cents if coupon_result else 0,
            )
            self.session.add(payment)

        await self.session.commit()

        detail = (
            f"Plano {plan.name} contratado."
            if amount == 0
            else (
                f"Plano {plan.name} contratado. "
                + (
                    f"Você tem {plan.trial_days} dias de teste; a cobrança de "
                    f"R$ {amount / 100:.2f} acontece ao fim deles."
                    if trial_ends
                    else f"Falta concluir o pagamento de R$ {amount / 100:.2f}."
                )
            )
        )
        logger.info("billing.subscribed", user=user.public_id, plan=plan.slug, status=status)
        return SubscribeResult(
            subscription=subscription,
            payment=payment,
            checkout_url=None,
            coupon=coupon_result,
            detail=detail,
        )

    # ------------------------------------------------------------------ #
    # Troca de plano
    # ------------------------------------------------------------------ #
    async def change_plan(
        self, user: User, *, plan_slug: str, today: date | None = None
    ) -> tuple[Subscription, ChangeDecision, Payment | None]:
        """Sobe agora com crédito proporcional; desce na virada do período."""
        day = today or datetime.now(UTC).date()
        subscription = await self.subscriptions.current_for(user.id)
        if subscription is None:
            raise NotFoundError("Você ainda não tem assinatura.")

        target = await self.plans.get_by_slug(plan_slug)
        if target is None or not target.is_active:
            raise NotFoundError("Plano não encontrado.")

        current = await self.session.get(Plan, subscription.plan_id)
        if current is None:  # pragma: no cover — FK garante
            raise NotFoundError("Plano atual não encontrado.")

        decision = decide_change(
            current_price_cents=current.price_cents,
            new_price_cents=target.price_cents,
            period_start=subscription.current_period_start,
            period_end=subscription.current_period_end,
            today=day,
        )

        if decision.kind == ChangeKind.SAME:
            raise ConflictError(decision.reason, code="same_plan")

        payment: Payment | None = None
        if decision.immediate:
            previous = subscription.status
            subscription.plan_id = target.id
            subscription.scheduled_plan_id = None
            subscription.current_period_start = day
            subscription.current_period_end = period_end_for(day, months=target.months)
            subscription.status = (
                SubscriptionStatus.PAST_DUE
                if decision.charge_cents > 0
                else SubscriptionStatus.ACTIVE
            )
            if subscription.status == SubscriptionStatus.PAST_DUE:
                subscription.grace_ends_on = grace_deadline(day)

            if decision.charge_cents > 0:
                payment = Payment(
                    user_id=user.id,
                    subscription_id=subscription.id,
                    plan_id=target.id,
                    reference=_reference(),
                    status=PaymentStatus.PENDING,
                    amount_cents=decision.charge_cents,
                    discount_cents=decision.credit_cents,
                )
                self.session.add(payment)

            self._record(
                subscription,
                kind="UPGRADED",
                detail=decision.reason,
                from_status=previous,
                to_status=subscription.status,
                meta={
                    "from_plan": current.slug,
                    "to_plan": target.slug,
                    "credit_cents": decision.credit_cents,
                    "charge_cents": decision.charge_cents,
                },
            )
        else:
            subscription.scheduled_plan_id = target.id
            self._record(
                subscription,
                kind="DOWNGRADE_SCHEDULED",
                detail=decision.reason,
                from_status=subscription.status,
                to_status=subscription.status,
                meta={"from_plan": current.slug, "to_plan": target.slug},
            )

        await self.session.commit()
        logger.info(
            "billing.plan_changed",
            user=user.public_id,
            kind=decision.kind,
            plan=target.slug,
        )
        return subscription, decision, payment

    # ------------------------------------------------------------------ #
    # Cancelamento
    # ------------------------------------------------------------------ #
    async def cancel(
        self, user: User, *, reason: str | None = None, today: date | None = None
    ) -> Subscription:
        """Cancela mantendo o acesso até o fim do período já pago."""
        day = today or datetime.now(UTC).date()
        subscription = await self.subscriptions.current_for(user.id)
        if subscription is None:
            raise NotFoundError("Você ainda não tem assinatura.")
        if subscription.status in {
            SubscriptionStatus.CANCELED,
            SubscriptionStatus.EXPIRED,
        }:
            raise ConflictError("Esta assinatura já está encerrada.", code="already_canceled")

        previous = subscription.status
        subscription.canceled_at = datetime.now(UTC)
        subscription.cancel_reason = reason
        subscription.scheduled_plan_id = None

        keeps_access = (
            subscription.current_period_end is not None
            and day <= subscription.current_period_end
            and previous
            in {
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.CANCELING,
            }
        )
        subscription.status = (
            SubscriptionStatus.CANCELING if keeps_access else SubscriptionStatus.CANCELED
        )

        self._record(
            subscription,
            kind="CANCELED",
            detail=(
                f"Cancelada. O acesso continua até {subscription.current_period_end:%d/%m/%Y}."
                if keeps_access and subscription.current_period_end
                else "Cancelada. Não havia período pago em aberto."
            ),
            from_status=previous,
            to_status=subscription.status,
            meta={"reason": reason or ""},
        )
        await self.session.commit()
        logger.info("billing.canceled", user=user.public_id, status=subscription.status)
        return subscription

    # ------------------------------------------------------------------ #
    # Confirmação de pagamento
    # ------------------------------------------------------------------ #
    async def confirm_payment(self, payment: Payment, *, today: date | None = None) -> None:
        """Libera o acesso e emite a linha de faturamento.

        Chamada pelo webhook (e só por ele, quando há provedor): é a confirmação
        do adquirente que muda o estado, nunca o clique do candidato.
        """
        day = today or datetime.now(UTC).date()
        if payment.status == PaymentStatus.APPROVED and payment.paid_at is not None:
            return

        payment.status = PaymentStatus.APPROVED
        payment.paid_at = datetime.now(UTC)

        subscription = (
            await self.session.get(Subscription, payment.subscription_id)
            if payment.subscription_id
            else None
        )
        if subscription is not None:
            plan = await self.session.get(Plan, subscription.plan_id)
            months = plan.months if plan else 1
            previous = subscription.status
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.grace_ends_on = None
            subscription.trial_ends_on = None
            subscription.current_period_start = day
            subscription.current_period_end = period_end_for(day, months=months)

            self._record(
                subscription,
                kind="PAYMENT_APPROVED",
                detail=f"Pagamento de R$ {payment.amount_cents / 100:.2f} confirmado.",
                from_status=previous,
                to_status=subscription.status,
                meta={"reference": payment.reference},
            )

            self.session.add(
                InvoiceLine(
                    user_id=payment.user_id,
                    payment_id=payment.id,
                    description=f"Assinatura {plan.name if plan else ''}".strip(),
                    amount_cents=payment.amount_cents + payment.discount_cents,
                    discount_cents=payment.discount_cents,
                    total_cents=payment.amount_cents,
                    period_start=subscription.current_period_start,
                    period_end=subscription.current_period_end,
                )
            )

            if subscription.coupon_id:
                coupon = await self.session.get(Coupon, subscription.coupon_id)
                if coupon is not None and not await self.coupons.redeemed_by(
                    coupon.id, payment.user_id
                ):
                    coupon.redeemed += 1
                    self.session.add(
                        CouponRedemption(
                            coupon_id=coupon.id,
                            user_id=payment.user_id,
                            amount_cents=payment.amount_cents + payment.discount_cents,
                            discount_cents=payment.discount_cents,
                        )
                    )

        await self.session.commit()

    async def fail_payment(self, payment: Payment, *, today: date | None = None) -> None:
        """Registra a recusa e abre a tolerância — não corta o acesso na hora."""
        day = today or datetime.now(UTC).date()
        payment.status = PaymentStatus.REJECTED

        subscription = (
            await self.session.get(Subscription, payment.subscription_id)
            if payment.subscription_id
            else None
        )
        if subscription is not None and subscription.status in {
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
        }:
            previous = subscription.status
            subscription.status = SubscriptionStatus.PAST_DUE
            subscription.grace_ends_on = grace_deadline(day)
            self._record(
                subscription,
                kind="PAYMENT_FAILED",
                detail=(
                    "Pagamento recusado. O acesso continua até "
                    f"{subscription.grace_ends_on:%d/%m/%Y} para dar tempo de resolver."
                ),
                from_status=previous,
                to_status=subscription.status,
                meta={"reference": payment.reference},
            )
        await self.session.commit()

    async def apply_scheduled_downgrade(
        self, subscription: Subscription, *, today: date | None = None
    ) -> bool:
        """Delega para o serviço de direitos, onde as transições do tempo moram."""
        return await self.entitlements.apply_scheduled_downgrade(
            subscription, today=today or datetime.now(UTC).date()
        )
