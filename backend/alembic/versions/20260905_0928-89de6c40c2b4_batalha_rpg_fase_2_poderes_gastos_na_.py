"""Batalha RPG fase 2: poderes gastos na batalha

Revision ID: 89de6c40c2b4
Revises: baac51ac4979
Create Date: 2026-09-05 09:28:00.923426
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "89de6c40c2b4"
down_revision: str | None = "baac51ac4979"
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
        "battle_power_uses",
        sa.Column("game_run_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("power", sa.String(length=16), nullable=False),
        sa.Column("cost", sa.Integer(), nullable=False),
        sa.Column("removed_letter", sa.String(length=2), nullable=True),
        sa.Column("hint", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
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
            ["game_run_id"],
            ["game_runs.id"],
            name=op.f("fk_battle_power_uses_game_run_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_battle_power_uses_question_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_battle_power_uses")),
        sa.UniqueConstraint("game_run_id", "question_id", "power", name="uq_battle_power_once"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_battle_power_uses_run", "battle_power_uses", ["game_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_battle_power_uses_run", table_name="battle_power_uses")

    op.drop_table("battle_power_uses")
