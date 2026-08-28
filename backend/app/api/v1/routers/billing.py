"""Comercial: planos, assinatura, cobrança, webhook e painel de SaaS.

O ciclo que o aceite da fase pede — **assinar → cobrar → limitar → cancelar** —
está inteiro aqui, com os limites vindo do banco e a confirmação vindo do
adquirente, nunca do clique do candidato.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request

from app.api.deps import CurrentUser, DbSession, RequestCtx, rate_limit, require_permissions
from app.core.errors import NotFoundError
from app.domain import permissions as perms
from app.domain.billing.plans import FEATURE_LABEL, Entitlement
from app.domain.billing.subscription import STATUS_LABEL
from app.models.audit import AuditAction
from app.models.billing import Coupon, Plan, PlanEntitlement, Subscription
from app.models.user import User
from app.schemas.billing import (
    CancelInput,
    ChangePlanInput,
    ChangePlanResultRead,
    CheckoutInput,
    CheckoutRead,
    CouponCreate,
    CouponPreviewInput,
    CouponRead,
    CouponResultRead,
    EntitlementRead,
    InvoiceRead,
    MetricRead,
    PaymentConfigRead,
    PaymentConfigUpdate,
    PaymentRead,
    PlanRead,
    PlanUpdate,
    QuotaRead,
    SaasDashboardRead,
    SubscribeInput,
    SubscribeResultRead,
    SubscriptionRead,
    WebhookAck,
)
from app.services.audit import AuditService
from app.services.billing import BillingService
from app.services.entitlements import EntitlementService
from app.services.payments import PaymentService
from app.services.saas_metrics import SaasMetricsService

router = APIRouter(tags=["comercial"])
billing_router = APIRouter(prefix="/billing", tags=["comercial"])
admin_router = APIRouter(prefix="/admin/billing", tags=["admin · comercial"])

BillingAdmin = Annotated[User, Depends(require_permissions(perms.BILLING_WRITE))]
BillingViewer = Annotated[User, Depends(require_permissions(perms.BILLING_READ))]


def _entitlement_read(item: PlanEntitlement) -> EntitlementRead:
    spec = Entitlement(
        feature=item.feature,
        enabled=item.is_enabled,
        limit=item.limit_value,
        period=item.period,
    )
    return EntitlementRead(
        feature=item.feature,
        label=FEATURE_LABEL.get(item.feature, item.feature),
        enabled=item.is_enabled,
        limit=item.limit_value,
        period=item.period,
        description=spec.describe(),
    )


def _plan_read(plan: Plan) -> PlanRead:
    return PlanRead(
        slug=plan.slug,
        name=plan.name,
        description=plan.description,
        price_cents=plan.price_cents,
        months=plan.months,
        trial_days=plan.trial_days,
        is_public=plan.is_public,
        entitlements=[
            _entitlement_read(item)
            for item in sorted(plan.entitlements, key=lambda entry: entry.feature)
        ],
    )


async def _subscription_read(
    db: DbSession, subscription: Subscription | None, *, fallback: Plan
) -> SubscriptionRead:
    if subscription is None:
        return SubscriptionRead(
            plan_slug=fallback.slug,
            plan_name=fallback.name,
            status="NONE",
            status_label="Sem assinatura",
            is_paid=False,
        )

    plan = await db.get(Plan, subscription.plan_id) or fallback
    scheduled = (
        await db.get(Plan, subscription.scheduled_plan_id)
        if subscription.scheduled_plan_id
        else None
    )
    return SubscriptionRead(
        public_id=subscription.public_id,
        plan_slug=plan.slug,
        plan_name=plan.name,
        status=subscription.status,
        status_label=STATUS_LABEL.get(subscription.status, subscription.status),
        started_on=subscription.started_on,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        trial_ends_on=subscription.trial_ends_on,
        grace_ends_on=subscription.grace_ends_on,
        canceled_at=subscription.canceled_at,
        scheduled_plan_slug=scheduled.slug if scheduled else None,
        is_paid=plan.price_cents > 0,
    )


def _quota_read(item: Any) -> QuotaRead:
    return QuotaRead(
        feature=item.feature,
        label=item.label,
        allowed=item.allowed,
        limit=item.limit,
        used=item.used,
        remaining=item.remaining,
        period=item.period,
        resets_on=item.resets_on,
        reason=item.reason,
    )


def _coupon_result_read(result: Any) -> CouponResultRead:
    return CouponResultRead(
        valid=result.valid,
        discount_cents=result.discount_cents,
        final_cents=result.final_cents,
        reason=result.reason,
        description=result.description,
    )


# --------------------------------------------------------------------------- #
# Candidato
# --------------------------------------------------------------------------- #
@billing_router.get("/plans", response_model=list[PlanRead], summary="Planos disponíveis")
async def plans(db: DbSession) -> list[PlanRead]:
    """Rota aberta: os planos e o que cada um concede, sem letra miúda."""
    return [_plan_read(item) for item in await BillingService(db).public_plans()]


@billing_router.get("/subscription", response_model=SubscriptionRead, summary="Minha assinatura")
async def subscription(user: CurrentUser, db: DbSession) -> SubscriptionRead:
    service = BillingService(db)
    fallback = await service.entitlements.fallback_plan()
    return await _subscription_read(db, await service.current(user), fallback=fallback)


@billing_router.get("/usage", response_model=list[QuotaRead], summary="Meus limites de uso")
async def usage(user: CurrentUser, db: DbSession) -> list[QuotaRead]:
    """O que o plano concede e quanto já foi usado em cada recurso."""
    return [_quota_read(item) for item in await EntitlementService(db).summary(user)]


@billing_router.post(
    "/coupons/preview", response_model=CouponResultRead, summary="Conferir um cupom"
)
async def preview_coupon(
    payload: CouponPreviewInput, user: CurrentUser, db: DbSession
) -> CouponResultRead:
    """Cupom recusado devolve o motivo — não um silêncio."""
    result = await BillingService(db).preview_coupon(
        user, code=payload.code, plan_slug=payload.plan_slug
    )
    return _coupon_result_read(result)


@billing_router.post(
    "/subscribe",
    response_model=SubscribeResultRead,
    status_code=201,
    summary="Assinar um plano",
    dependencies=[Depends(rate_limit("20/hour", scope="billing:subscribe"))],
)
async def subscribe(
    payload: SubscribeInput, user: CurrentUser, db: DbSession, ctx: RequestCtx
) -> SubscribeResultRead:
    """Contrata o plano. Quem libera o acesso pago é a confirmação do pagamento."""
    service = BillingService(db)
    result = await service.subscribe(
        user, plan_slug=payload.plan_slug, coupon_code=payload.coupon_code
    )
    await AuditService(db).record(
        AuditAction.SUBSCRIPTION_CREATED,
        actor=user,
        actor_ip=ctx.ip_address,
        resource_type="subscription",
        resource_id=result.subscription.public_id,
        meta={"plan": payload.plan_slug},
    )
    await db.commit()

    fallback = await service.entitlements.fallback_plan()
    return SubscribeResultRead(
        subscription=await _subscription_read(db, result.subscription, fallback=fallback),
        payment=PaymentRead.model_validate(result.payment) if result.payment else None,
        coupon=_coupon_result_read(result.coupon) if result.coupon else None,
        detail=result.detail,
    )


@billing_router.post("/change-plan", response_model=ChangePlanResultRead, summary="Trocar de plano")
async def change_plan(
    payload: ChangePlanInput, user: CurrentUser, db: DbSession
) -> ChangePlanResultRead:
    """Subir vale agora, com crédito proporcional; descer vale na virada."""
    service = BillingService(db)
    subscription, decision, payment = await service.change_plan(user, plan_slug=payload.plan_slug)
    fallback = await service.entitlements.fallback_plan()
    return ChangePlanResultRead(
        subscription=await _subscription_read(db, subscription, fallback=fallback),
        kind=decision.kind,
        immediate=decision.immediate,
        credit_cents=decision.credit_cents,
        charge_cents=decision.charge_cents,
        reason=decision.reason,
        payment=PaymentRead.model_validate(payment) if payment else None,
    )


@billing_router.post("/cancel", response_model=SubscriptionRead, summary="Cancelar a assinatura")
async def cancel(
    payload: CancelInput, user: CurrentUser, db: DbSession, ctx: RequestCtx
) -> SubscriptionRead:
    """O acesso continua até o fim do período já pago."""
    service = BillingService(db)
    subscription = await service.cancel(user, reason=payload.reason)
    await AuditService(db).record(
        AuditAction.SUBSCRIPTION_CANCELED,
        actor=user,
        actor_ip=ctx.ip_address,
        resource_type="subscription",
        resource_id=subscription.public_id,
        meta={"reason": payload.reason or ""},
    )
    await db.commit()
    fallback = await service.entitlements.fallback_plan()
    return await _subscription_read(db, subscription, fallback=fallback)


@billing_router.get("/payments", response_model=list[PaymentRead], summary="Minhas cobranças")
async def payments(user: CurrentUser, db: DbSession) -> list[PaymentRead]:
    rows = await BillingService(db).payments.history(user.id)
    return [PaymentRead.model_validate(item) for item in rows]


@billing_router.get("/invoices", response_model=list[InvoiceRead], summary="Meu faturamento")
async def invoices(user: CurrentUser, db: DbSession) -> list[InvoiceRead]:
    rows = await BillingService(db).invoices.history(user.id)
    return [InvoiceRead.model_validate(item) for item in rows]


@billing_router.post(
    "/checkout",
    response_model=CheckoutRead,
    summary="Iniciar o pagamento de uma cobrança",
    dependencies=[Depends(rate_limit("30/hour", scope="billing:checkout"))],
)
async def checkout(payload: CheckoutInput, user: CurrentUser, db: DbSession) -> CheckoutRead:
    """Cria a cobrança no adquirente. Sem provedor configurado, recusa com o motivo."""
    url = await PaymentService(db).start_checkout(
        user,
        payload.reference,
        success_url=payload.success_url,
        failure_url=payload.failure_url,
    )
    return CheckoutRead(checkout_url=url)


# --------------------------------------------------------------------------- #
# Webhook (rota aberta, verificada por assinatura)
# --------------------------------------------------------------------------- #
@router.post(
    "/webhooks/mercadopago",
    response_model=WebhookAck,
    summary="Notificação do Mercado Pago",
    include_in_schema=False,
)
async def mercadopago_webhook(
    request: Request,
    db: DbSession,
    x_signature: Annotated[str | None, Header(alias="x-signature")] = None,
    x_request_id: Annotated[str | None, Header(alias="x-request-id")] = None,
) -> WebhookAck:
    """Assinatura conferida, evento deduplicado, status consultado na origem.

    Devolvemos 200 mesmo em notificação recusada: repetir uma notificação
    inválida indefinidamente não ajuda ninguém, e o motivo fica no log.
    """
    payload = await request.json()
    result = await PaymentService(db).handle_webhook(
        payload if isinstance(payload, dict) else {},
        signature=x_signature,
        request_id=x_request_id,
    )
    return WebhookAck(accepted=result.accepted, duplicate=result.duplicate, detail=result.detail)


# --------------------------------------------------------------------------- #
# Administração
# --------------------------------------------------------------------------- #
@admin_router.get("/plans", response_model=list[PlanRead], summary="Todos os planos")
async def admin_plans(_: BillingViewer, db: DbSession) -> list[PlanRead]:
    service = BillingService(db)
    await service.entitlements.sync_plans()
    return [_plan_read(item) for item in await service.plans.all_plans()]


@admin_router.put("/plans/{slug}", response_model=PlanRead, summary="Editar um plano")
async def update_plan(
    slug: str, payload: PlanUpdate, actor: BillingAdmin, db: DbSession, ctx: RequestCtx
) -> PlanRead:
    """Preço, limites e recursos mudam **sem deploy** — é a regra da fase."""
    service = BillingService(db)
    await service.entitlements.sync_plans()
    plan = await service.plans.get_by_slug(slug)
    if plan is None:
        raise NotFoundError("Plano não encontrado.")

    before = {
        "price_cents": plan.price_cents,
        "entitlements": {
            item.feature: {"enabled": item.is_enabled, "limit": item.limit_value}
            for item in plan.entitlements
        },
    }

    data = payload.model_dump(exclude_unset=True, exclude={"entitlements"})
    for field_name, value in data.items():
        if value is not None:
            setattr(plan, field_name, value)

    if payload.entitlements is not None:
        # As linhas antigas saem antes de as novas entrarem: a chave única
        # (plano, recurso) não perdoa inserir por cima.
        plan.entitlements.clear()
        await db.flush()
        plan.entitlements = [
            PlanEntitlement(
                feature=item.feature,
                is_enabled=item.is_enabled,
                limit_value=item.limit_value,
                period=item.period,
            )
            for item in payload.entitlements
        ]

    await AuditService(db).record(
        AuditAction.PLAN_UPDATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="plan",
        resource_id=slug,
        meta={"before": before},
    )
    await db.commit()

    stored = await service.plans.get_by_slug(slug)
    assert stored is not None
    return _plan_read(stored)


@admin_router.get("/coupons", response_model=list[CouponRead], summary="Cupons")
async def list_coupons(_: BillingViewer, db: DbSession) -> list[CouponRead]:
    rows = await BillingService(db).coupons.all_coupons()
    return [CouponRead.model_validate(item) for item in rows]


@admin_router.post("/coupons", response_model=CouponRead, status_code=201, summary="Criar um cupom")
async def create_coupon(payload: CouponCreate, _: BillingAdmin, db: DbSession) -> CouponRead:
    coupon = Coupon(
        code=payload.code.strip().upper(),
        kind=payload.kind,
        value=payload.value,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        max_redemptions=payload.max_redemptions,
        once_per_user=payload.once_per_user,
        min_amount_cents=payload.min_amount_cents,
        plan_slugs=payload.plan_slugs,
    )
    db.add(coupon)
    await db.commit()
    return CouponRead.model_validate(coupon)


@admin_router.get("/provider", response_model=PaymentConfigRead, summary="Provedor de pagamento")
async def payment_config(_: BillingViewer, db: DbSession) -> PaymentConfigRead:
    """Só a dica visual das credenciais: o segredo nunca volta pela API."""
    stored = await PaymentService(db).config()
    if stored is None:
        return PaymentConfigRead(
            slug="mercadopago",
            display_name="Mercado Pago",
            is_active=False,
            is_sandbox=True,
            is_configured=False,
        )
    return PaymentConfigRead(
        slug=stored.slug,
        display_name=stored.display_name,
        is_active=stored.is_active,
        is_sandbox=stored.is_sandbox,
        access_token_hint=stored.access_token_hint,
        webhook_secret_hint=stored.webhook_secret_hint,
        credentials_set_at=stored.credentials_set_at,
        is_configured=bool(stored.access_token_encrypted),
    )


@admin_router.put("/provider", response_model=PaymentConfigRead, summary="Configurar o provedor")
async def update_payment_config(
    payload: PaymentConfigUpdate, actor: BillingAdmin, db: DbSession, ctx: RequestCtx
) -> PaymentConfigRead:
    stored = await PaymentService(db).save_credentials(
        actor,
        access_token=payload.access_token,
        webhook_secret=payload.webhook_secret,
        is_active=payload.is_active,
        is_sandbox=payload.is_sandbox,
    )
    await AuditService(db).record(
        AuditAction.PAYMENT_PROVIDER_UPDATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="payment_provider",
        resource_id=stored.slug,
        meta={"is_active": stored.is_active, "is_sandbox": stored.is_sandbox},
    )
    await db.commit()
    return PaymentConfigRead(
        slug=stored.slug,
        display_name=stored.display_name,
        is_active=stored.is_active,
        is_sandbox=stored.is_sandbox,
        access_token_hint=stored.access_token_hint,
        webhook_secret_hint=stored.webhook_secret_hint,
        credentials_set_at=stored.credentials_set_at,
        is_configured=bool(stored.access_token_encrypted),
    )


@admin_router.get("/dashboard", response_model=SaasDashboardRead, summary="Indicadores do SaaS")
async def dashboard(_: BillingViewer, db: DbSession) -> SaasDashboardRead:
    """MRR, ARPU, churn, custo de IA e margem — cada um com o denominador."""
    metrics = await SaasMetricsService(db).build()
    return SaasDashboardRead(
        metrics=[
            MetricRead(
                key=item.key,
                label=item.label,
                value=item.value,
                unit=item.unit,
                basis=item.basis,
                empty_reason=item.empty_reason,
            )
            for item in metrics.metrics
        ],
        period_start=metrics.period_start,
        period_end=metrics.period_end,
    )


router.include_router(billing_router)
router.include_router(admin_router)
