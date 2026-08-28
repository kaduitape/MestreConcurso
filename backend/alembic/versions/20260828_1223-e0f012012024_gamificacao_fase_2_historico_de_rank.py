"""Gamificacao Fase 2 - historico diario do rank

Revision ID: e0f012012024
Revises: 3a1b0f0dd1ba
Create Date: 2026-08-28 12:23:10.562732
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "e0f012012024"
down_revision: str | None = "3a1b0f0dd1ba"
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
        "rank_snapshots",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("rank_slug", sa.String(length=20), nullable=False),
        sa.Column("rank_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("components", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("missing_signals", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("xp_total", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
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
            ["user_id"], ["users.id"], name=op.f("fk_rank_snapshots_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rank_snapshots")),
        sa.UniqueConstraint("user_id", "day", name="uq_rank_snapshots_user_day"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_rank_snapshots_user_day", "rank_snapshots", ["user_id", "day"], unique=False
    )
    op.create_index(op.f("ix_rank_snapshots_user_id"), "rank_snapshots", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rank_snapshots_user_id"), table_name="rank_snapshots")
    op.drop_index("ix_rank_snapshots_user_day", table_name="rank_snapshots")

    op.drop_table("rank_snapshots")
