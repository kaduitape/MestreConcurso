"""Comercial: planos, direitos de uso, assinaturas, cupons e pagamentos.

A decisão estrutural desta camada: **limite é linha de tabela**. O catálogo de
fábrica em ``app.domain.billing.plans`` só semeia o banco na primeira subida;
depois disso, mudar o que um plano concede é um `UPDATE`, não um deploy — como
pedido explicitamente no projeto.

A segunda decisão é a idempotência do webhook: cada notificação recebida vira uma
linha única por (provedor, id do evento). Reenvio — que todo adquirente faz — não
credita duas vezes.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, LongText, MediumText


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"


class Plan(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um plano comercial. Preço e período vivem aqui, não no código."""

    __tablename__ = "plans"
    __table_args__ = (UniqueConstraint("slug", name="uq_plans_slug"),)

    slug: Mapped[str] = mapped_column(String(40), index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(String(400), default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    #: Meses cobertos por um pagamento (1 = mensal, 12 = anual).
    months: Mapped[int] = mapped_column(Integer, default=1)
    trial_days: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    entitlements: Mapped[list[PlanEntitlement]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class PlanEntitlement(IdMixin, TimestampMixin, Base):
    """O que um plano concede em um recurso.

    ``is_enabled`` falso e ``limit_value`` nulo são coisas **diferentes**: o
    primeiro é "sem acesso", o segundo é "sem teto". Guardar as duas no mesmo
    campo é como sistemas de cobrança liberam recurso pago por engano.
    """

    __tablename__ = "plan_entitlements"
    __table_args__ = (
        UniqueConstraint("plan_id", "feature", name="uq_plan_entitlements_plan_feature"),
    )

    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    feature: Mapped[str] = mapped_column(String(60))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Nulo = ilimitado.
    limit_value: Mapped[int | None] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(10), default="MONTH")

    plan: Mapped[Plan] = relationship(back_populates="entitlements")


class Subscription(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """A assinatura de um candidato."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_status", "user_id", "status"),
        Index("ix_subscriptions_period_end", "current_period_end"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    started_on: Mapped[date] = mapped_column(Date)
    current_period_start: Mapped[date | None] = mapped_column(Date)
    current_period_end: Mapped[date | None] = mapped_column(Date)
    trial_ends_on: Mapped[date | None] = mapped_column(Date)
    #: Preenchido quando uma cobrança falha: até aqui o acesso continua.
    grace_ends_on: Mapped[date | None] = mapped_column(Date)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    #: Downgrade agendado para a virada do período.
    scheduled_plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="SET NULL")
    )
    coupon_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("coupons.id", ondelete="SET NULL")
    )

    plan: Mapped[Plan] = relationship(foreign_keys=[plan_id], lazy="selectin")


class SubscriptionEvent(IdMixin, TimestampMixin, Base):
    """Histórico da assinatura. É a resposta a "por que meu acesso mudou?"."""

    __tablename__ = "subscription_events"
    __table_args__ = (Index("ix_subscription_events_subscription", "subscription_id"),)

    subscription_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    detail: Mapped[str] = mapped_column(String(400), default="")
    meta: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class Coupon(IdMixin, PublicIdMixin, TimestampMixin, Base):
    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("code", name="uq_coupons_code"),)

    code: Mapped[str] = mapped_column(String(40), index=True)
    kind: Mapped[str] = mapped_column(String(10), default="PERCENT")
    value: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    max_redemptions: Mapped[int | None] = mapped_column(Integer)
    redeemed: Mapped[int] = mapped_column(Integer, default=0)
    once_per_user: Mapped[bool] = mapped_column(Boolean, default=True)
    min_amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    plan_slugs: Mapped[list[str]] = mapped_column(JsonType, default=list)


class CouponRedemption(IdMixin, TimestampMixin, Base):
    __tablename__ = "coupon_redemptions"
    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", name="uq_coupon_redemptions_coupon_user"),
    )

    coupon_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("coupons.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)


class Payment(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma cobrança. A referência é nossa; o id do provedor é dele."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("reference", name="uq_payments_reference"),
        Index("ix_payments_user_status", "user_id", "status"),
        Index("ix_payments_provider_reference", "provider_reference"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    subscription_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("plans.id", ondelete="SET NULL")
    )
    reference: Mapped[str] = mapped_column(String(60), index=True)
    provider: Mapped[str] = mapped_column(String(30), default="mercadopago")
    provider_reference: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    checkout_url: Mapped[str | None] = mapped_column(String(500))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Resposta do provedor, guardada para auditoria e conciliação.
    raw: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class WebhookEvent(IdMixin, TimestampMixin, Base):
    """Notificação recebida — a chave única é o que garante idempotência.

    Todo adquirente reenvia notificação. Sem esta tabela, o reenvio de um
    "pagamento aprovado" estenderia a assinatura duas vezes.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
        Index("ix_webhook_events_received", "received_at"),
    )

    provider: Mapped[str] = mapped_column(String(30), default="mercadopago")
    event_id: Mapped[str] = mapped_column(String(120))
    topic: Mapped[str | None] = mapped_column(String(60))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="RECEIVED")
    detail: Mapped[str | None] = mapped_column(String(400))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class UsageCounter(IdMixin, TimestampMixin, Base):
    """Consumo de um recurso dentro de uma janela.

    A janela é gravada na linha para que o contador não dependa de "que dia é
    hoje" na hora da leitura: virou a janela, é outra linha.
    """

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "feature", "window_start", name="uq_usage_counters_user_feature_window"
        ),
        Index("ix_usage_counters_user_feature", "user_id", "feature"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    feature: Mapped[str] = mapped_column(String(60))
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date | None] = mapped_column(Date)
    used: Mapped[int] = mapped_column(Integer, default=0)


class PaymentProviderConfig(IdMixin, TimestampMixin, Base):
    """Credencial do adquirente — cifrada, como a chave de IA da Fase 2.

    O segredo nunca volta pela API: guardamos o texto cifrado e uma dica visual.
    """

    __tablename__ = "payment_providers"
    __table_args__ = (UniqueConstraint("slug", name="uq_payment_providers_slug"),)

    slug: Mapped[str] = mapped_column(String(30), index=True, default="mercadopago")
    display_name: Mapped[str] = mapped_column(String(80), default="Mercado Pago")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Modo de teste do provedor, quando ele oferece um.
    is_sandbox: Mapped[bool] = mapped_column(Boolean, default=True)

    access_token_encrypted: Mapped[str | None] = mapped_column(LongText)
    access_token_hint: Mapped[str | None] = mapped_column(String(32))
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(LongText)
    webhook_secret_hint: Mapped[str | None] = mapped_column(String(32))
    credentials_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credentials_set_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(MediumText)
    settings: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)


class InvoiceLine(IdMixin, TimestampMixin, Base):
    """Faturamento: o que foi cobrado, quando e por quê."""

    __tablename__ = "invoice_lines"
    __table_args__ = (Index("ix_invoice_lines_user_created", "user_id", "created_at"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    payment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("payments.id", ondelete="SET NULL")
    )
    description: Mapped[str] = mapped_column(String(200))
    amount_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    #: Crédito proporcional aplicado em uma troca de plano.
    credit_cents: Mapped[int] = mapped_column(Integer, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    tax_cents: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
