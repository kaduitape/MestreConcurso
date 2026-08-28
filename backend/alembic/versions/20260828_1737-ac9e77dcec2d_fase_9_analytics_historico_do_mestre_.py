"""Fase 9 - Analytics: historico do Mestre Score

Revision ID: ac9e77dcec2d
Revises: fce1976e6881
Create Date: 2026-08-28 17:37:17.131724
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "ac9e77dcec2d"
down_revision: str | None = "fce1976e6881"
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
        "master_score_snapshots",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("low", sa.Integer(), nullable=False),
        sa.Column("high", sa.Integer(), nullable=False),
        sa.Column("band", sa.String(length=30), nullable=False),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.Column("available_weight", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("components", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("missing_signals", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_master_score_snapshots_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_master_score_snapshots")),
        sa.UniqueConstraint("user_id", "day", name="uq_master_score_snapshots_user_day"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_master_score_snapshots_user_day",
        "master_score_snapshots",
        ["user_id", "day"],
        unique=False,
    )
    op.create_index(
        op.f("ix_master_score_snapshots_user_id"),
        "master_score_snapshots",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_master_score_snapshots_user_id"), table_name="master_score_snapshots")
    op.drop_index("ix_master_score_snapshots_user_day", table_name="master_score_snapshots")

    op.drop_table("master_score_snapshots")
