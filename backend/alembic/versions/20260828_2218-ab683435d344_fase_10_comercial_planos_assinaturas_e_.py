"""Fase 10 - Comercial: planos, assinaturas, cupons e pagamentos

Revision ID: ab683435d344
Revises: ac9e77dcec2d
Create Date: 2026-08-28 22:18:05.934145
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "ab683435d344"
down_revision: str | None = "ac9e77dcec2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQLite (usado nos testes) só auto-incrementa colunas INTEGER.
BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

# Opções aplicadas somente no MySQL; ignoradas pelos demais dialetos.
MYSQL_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column("max_redemptions", sa.Integer(), nullable=True),
        sa.Column("redeemed", sa.Integer(), nullable=False),
        sa.Column("once_per_user", sa.Boolean(), nullable=False),
        sa.Column("min_amount_cents", sa.Integer(), nullable=False),
        sa.Column("plan_slugs", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coupons")),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_coupons_code"), "coupons", ["code"], unique=False)
    op.create_index(op.f("ix_coupons_public_id"), "coupons", ["public_id"], unique=True)

    op.create_table(
        "plans",
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
        sa.UniqueConstraint("slug", name="uq_plans_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_plans_public_id"), "plans", ["public_id"], unique=True)
    op.create_index(op.f("ix_plans_slug"), "plans", ["slug"], unique=False)

    op.create_table(
        "webhook_events",
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("topic", sa.String(length=60), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.String(length=400), nullable=True),
        sa.Column("payload", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_webhook_events_received", "webhook_events", ["received_at"], unique=False)

    op.create_table(
        "coupon_redemptions",
        sa.Column("coupon_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["coupon_id"],
            ["coupons.id"],
            name=op.f("fk_coupon_redemptions_coupon_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_coupon_redemptions_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coupon_redemptions")),
        sa.UniqueConstraint("coupon_id", "user_id", name="uq_coupon_redemptions_coupon_user"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_coupon_redemptions_coupon_id"), "coupon_redemptions", ["coupon_id"], unique=False
    )
    op.create_index(
        op.f("ix_coupon_redemptions_user_id"), "coupon_redemptions", ["user_id"], unique=False
    )

    op.create_table(
        "payment_providers",
        sa.Column("slug", sa.String(length=30), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_sandbox", sa.Boolean(), nullable=False),
        sa.Column(
            "access_token_encrypted",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("access_token_hint", sa.String(length=32), nullable=True),
        sa.Column(
            "webhook_secret_encrypted",
            sa.Text().with_variant(mysql.LONGTEXT(), "mysql"),
            nullable=True,
        ),
        sa.Column("webhook_secret_hint", sa.String(length=32), nullable=True),
        sa.Column("credentials_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credentials_set_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("notes", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("settings", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["credentials_set_by_user_id"],
            ["users.id"],
            name=op.f("fk_payment_providers_credentials_set_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_providers")),
        sa.UniqueConstraint("slug", name="uq_payment_providers_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_payment_providers_slug"), "payment_providers", ["slug"], unique=False)

    op.create_table(
        "plan_entitlements",
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_plan_entitlements_plan_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_entitlements")),
        sa.UniqueConstraint("plan_id", "feature", name="uq_plan_entitlements_plan_feature"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_plan_entitlements_plan_id"), "plan_entitlements", ["plan_id"], unique=False
    )

    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("current_period_start", sa.Date(), nullable=True),
        sa.Column("current_period_end", sa.Date(), nullable=True),
        sa.Column("trial_ends_on", sa.Date(), nullable=True),
        sa.Column("grace_ends_on", sa.Date(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(length=255), nullable=True),
        sa.Column("scheduled_plan_id", sa.BigInteger(), nullable=True),
        sa.Column("coupon_id", sa.BigInteger(), nullable=True),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["coupon_id"],
            ["coupons.id"],
            name=op.f("fk_subscriptions_coupon_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_subscriptions_plan_id"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scheduled_plan_id"],
            ["plans.id"],
            name=op.f("fk_subscriptions_scheduled_plan_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_subscriptions_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_subscriptions_period_end", "subscriptions", ["current_period_end"], unique=False
    )
    op.create_index(op.f("ix_subscriptions_plan_id"), "subscriptions", ["plan_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_public_id"), "subscriptions", ["public_id"], unique=True)
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)
    op.create_index(
        "ix_subscriptions_user_status", "subscriptions", ["user_id", "status"], unique=False
    )

    op.create_table(
        "usage_counters",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("used", sa.Integer(), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_usage_counters_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_counters")),
        sa.UniqueConstraint(
            "user_id", "feature", "window_start", name="uq_usage_counters_user_feature_window"
        ),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_usage_counters_user_feature", "usage_counters", ["user_id", "feature"], unique=False
    )
    op.create_index(op.f("ix_usage_counters_user_id"), "usage_counters", ["user_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("subscription_id", sa.BigInteger(), nullable=True),
        sa.Column("plan_id", sa.BigInteger(), nullable=True),
        sa.Column("reference", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_reference", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False),
        sa.Column("checkout_url", sa.String(length=500), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column("public_id", sa.String(length=26), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["plans.id"], name=op.f("fk_payments_plan_id"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_payments_subscription_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_payments_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payments")),
        sa.UniqueConstraint("reference", name="uq_payments_reference"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_payments_provider_reference", "payments", ["provider_reference"], unique=False
    )
    op.create_index(op.f("ix_payments_public_id"), "payments", ["public_id"], unique=True)
    op.create_index(op.f("ix_payments_reference"), "payments", ["reference"], unique=False)
    op.create_index(op.f("ix_payments_user_id"), "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_user_status", "payments", ["user_id", "status"], unique=False)

    op.create_table(
        "subscription_events",
        sa.Column("subscription_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=True),
        sa.Column("detail", sa.String(length=400), nullable=False),
        sa.Column("meta", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscriptions.id"],
            name=op.f("fk_subscription_events_subscription_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_events")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_subscription_events_subscription",
        "subscription_events",
        ["subscription_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subscription_events_subscription_id"),
        "subscription_events",
        ["subscription_id"],
        unique=False,
    )

    op.create_table(
        "invoice_lines",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("payment_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=False),
        sa.Column("credit_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("tax_cents", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name=op.f("fk_invoice_lines_payment_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_invoice_lines_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_lines")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_invoice_lines_user_created", "invoice_lines", ["user_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_invoice_lines_user_id"), "invoice_lines", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_lines_user_id"), table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_user_created", table_name="invoice_lines")

    op.drop_table("invoice_lines")
    op.drop_index(op.f("ix_subscription_events_subscription_id"), table_name="subscription_events")
    op.drop_index("ix_subscription_events_subscription", table_name="subscription_events")

    op.drop_table("subscription_events")
    op.drop_index("ix_payments_user_status", table_name="payments")
    op.drop_index(op.f("ix_payments_user_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_reference"), table_name="payments")
    op.drop_index(op.f("ix_payments_public_id"), table_name="payments")
    op.drop_index("ix_payments_provider_reference", table_name="payments")

    op.drop_table("payments")
    op.drop_index(op.f("ix_usage_counters_user_id"), table_name="usage_counters")
    op.drop_index("ix_usage_counters_user_feature", table_name="usage_counters")

    op.drop_table("usage_counters")
    op.drop_index("ix_subscriptions_user_status", table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_public_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_plan_id"), table_name="subscriptions")
    op.drop_index("ix_subscriptions_period_end", table_name="subscriptions")

    op.drop_table("subscriptions")
    op.drop_index(op.f("ix_plan_entitlements_plan_id"), table_name="plan_entitlements")

    op.drop_table("plan_entitlements")
    op.drop_index(op.f("ix_payment_providers_slug"), table_name="payment_providers")

    op.drop_table("payment_providers")
    op.drop_index(op.f("ix_coupon_redemptions_user_id"), table_name="coupon_redemptions")
    op.drop_index(op.f("ix_coupon_redemptions_coupon_id"), table_name="coupon_redemptions")

    op.drop_table("coupon_redemptions")
    op.drop_index("ix_webhook_events_received", table_name="webhook_events")

    op.drop_table("webhook_events")
    op.drop_index(op.f("ix_plans_slug"), table_name="plans")
    op.drop_index(op.f("ix_plans_public_id"), table_name="plans")

    op.drop_table("plans")
    op.drop_index(op.f("ix_coupons_public_id"), table_name="coupons")
    op.drop_index(op.f("ix_coupons_code"), table_name="coupons")

    op.drop_table("coupons")
