"""teto de gasto com IA

Revision ID: 35cf5e2fb21f
Revises: 81ed603d085c
Create Date: 2026-10-20 13:18:24.739771
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "35cf5e2fb21f"
down_revision: str | None = "81ed603d085c"
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
        "ai_budgets",
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("monthly_limit_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("per_run_limit_cents", sa.Numeric(precision=12, scale=6), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_budgets")),
        sa.UniqueConstraint("scope", name="uq_ai_budgets_scope"),
        **MYSQL_OPTS,
    )


def downgrade() -> None:
    op.drop_table("ai_budgets")
