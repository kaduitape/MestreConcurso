"""Schemas da camada comercial.

Um detalhe que aparece em vários objetos: ``limit`` nulo significa **ilimitado**,
e ``enabled`` falso significa **sem acesso**. São campos separados porque as duas
coisas são diferentes, e confundi-las libera recurso pago por engano.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class EntitlementRead(BaseModel):
    feature: str
    label: str
    enabled: bool
    #: Nulo = sem teto.
    limit: int | None = None
    period: str
    description: str


class PlanRead(BaseModel):
    slug: str
    name: str
    description: str
    price_cents: int
    months: int
    trial_days: int
    is_public: bool
    entitlements: list[EntitlementRead] = Field(default_factory=list)


class QuotaRead(BaseModel):
    feature: str
    label: str
    allowed: bool
    limit: int | None = None
    used: int
    remaining: int | None = None
    period: str
    resets_on: date | None = None
    #: Vazio quando permitido; explica a recusa quando não.
    reason: str = ""


class SubscriptionRead(BaseModel):
    public_id: str | None = None
    plan_slug: str
    plan_name: str
    status: str
    status_label: str
    started_on: date | None = None
    current_period_start: date | None = None
    current_period_end: date | None = None
    trial_ends_on: date | None = None
    grace_ends_on: date | None = None
    canceled_at: datetime | None = None
    #: Downgrade agendado para a virada do período.
    scheduled_plan_slug: str | None = None
    #: Falso quando o candidato caiu no plano gratuito.
    is_paid: bool = False


class SubscribeInput(BaseModel):
    plan_slug: str = Field(min_length=2, max_length=40)
    coupon_code: str | None = Field(default=None, max_length=40)


class ChangePlanInput(BaseModel):
    plan_slug: str = Field(min_length=2, max_length=40)


class CancelInput(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class CouponPreviewInput(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    plan_slug: str = Field(min_length=2, max_length=40)


class CouponResultRead(BaseModel):
    valid: bool
    discount_cents: int
    final_cents: int
    #: Motivo da recusa, quando houver.
    reason: str = ""
    description: str = ""


class PaymentRead(BaseModel):
    model_config = _READ

    public_id: str
    reference: str
    status: str
    amount_cents: int
    discount_cents: int
    checkout_url: str | None = None
    paid_at: datetime | None = None
    created_at: datetime


class SubscribeResultRead(BaseModel):
    subscription: SubscriptionRead
    payment: PaymentRead | None = None
    coupon: CouponResultRead | None = None
    detail: str


class ChangePlanResultRead(BaseModel):
    subscription: SubscriptionRead
    kind: str
    immediate: bool
    credit_cents: int
    charge_cents: int
    reason: str
    payment: PaymentRead | None = None


class InvoiceRead(BaseModel):
    model_config = _READ

    description: str
    amount_cents: int
    discount_cents: int
    credit_cents: int
    total_cents: int
    period_start: date | None = None
    period_end: date | None = None
    created_at: datetime


class CheckoutInput(BaseModel):
    reference: str = Field(min_length=4, max_length=60)
    success_url: str = Field(max_length=500)
    failure_url: str = Field(max_length=500)


class CheckoutRead(BaseModel):
    checkout_url: str


class WebhookAck(BaseModel):
    accepted: bool
    duplicate: bool
    detail: str


# --------------------------------------------------------------------------- #
# Administração
# --------------------------------------------------------------------------- #
class PlanEntitlementInput(BaseModel):
    feature: str = Field(max_length=60)
    is_enabled: bool = True
    limit_value: int | None = Field(default=None, ge=0)
    period: str = Field(default="MONTH", pattern="^(DAY|MONTH|TOTAL)$")


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=400)
    price_cents: int | None = Field(default=None, ge=0)
    trial_days: int | None = Field(default=None, ge=0, le=90)
    is_active: bool | None = None
    is_public: bool | None = None
    #: Substitui a lista inteira de direitos do plano.
    entitlements: list[PlanEntitlementInput] | None = None


class CouponCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    kind: str = Field(default="PERCENT", pattern="^(PERCENT|FIXED)$")
    value: int = Field(gt=0)
    starts_on: date | None = None
    ends_on: date | None = None
    max_redemptions: int | None = Field(default=None, gt=0)
    once_per_user: bool = True
    min_amount_cents: int = Field(default=0, ge=0)
    plan_slugs: list[str] = Field(default_factory=list)


class CouponRead(BaseModel):
    model_config = _READ

    public_id: str
    code: str
    kind: str
    value: int
    is_active: bool
    starts_on: date | None = None
    ends_on: date | None = None
    max_redemptions: int | None = None
    redeemed: int
    once_per_user: bool
    min_amount_cents: int
    plan_slugs: list[str] = Field(default_factory=list)


class PaymentConfigRead(BaseModel):
    slug: str
    display_name: str
    is_active: bool
    is_sandbox: bool
    #: Apenas a dica visual: o segredo nunca volta pela API.
    access_token_hint: str | None = None
    webhook_secret_hint: str | None = None
    credentials_set_at: datetime | None = None
    is_configured: bool


class PaymentConfigUpdate(BaseModel):
    access_token: str | None = Field(default=None, max_length=500)
    webhook_secret: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    is_sandbox: bool | None = None


class MetricRead(BaseModel):
    key: str
    label: str
    #: Nulo quando não há base para calcular — nunca zero por omissão.
    value: float | None = None
    unit: str
    #: O denominador ou a amostra, escritos.
    basis: str
    empty_reason: str | None = None


class SaasDashboardRead(BaseModel):
    metrics: list[MetricRead] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
