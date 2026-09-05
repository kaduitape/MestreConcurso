"""Batalha RPG fase 3: classes e equipamentos

Revision ID: dc0c6263929d
Revises: 89de6c40c2b4
Create Date: 2026-09-05 12:07:09.164178
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "dc0c6263929d"
down_revision: str | None = "89de6c40c2b4"
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
        "battle_loadouts",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("class_slug", sa.String(length=30), nullable=False),
        sa.Column("weapon_slug", sa.String(length=40), nullable=False),
        sa.Column("armor_slug", sa.String(length=40), nullable=False),
        sa.Column("trinket_slug", sa.String(length=40), nullable=False),
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
            ["user_id"], ["users.id"], name=op.f("fk_battle_loadouts_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_battle_loadouts")),
        sa.UniqueConstraint("user_id", name="uq_battle_loadouts_user"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_battle_loadouts_user_id"), "battle_loadouts", ["user_id"], unique=False
    )

    op.create_table(
        "battle_run_loadouts",
        sa.Column("game_run_id", sa.BigInteger(), nullable=False),
        sa.Column("class_slug", sa.String(length=30), nullable=False),
        sa.Column("weapon_slug", sa.String(length=40), nullable=False),
        sa.Column("armor_slug", sa.String(length=40), nullable=False),
        sa.Column("trinket_slug", sa.String(length=40), nullable=False),
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
            name=op.f("fk_battle_run_loadouts_game_run_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_battle_run_loadouts")),
        sa.UniqueConstraint("game_run_id", name="uq_battle_run_loadouts_run"),
        **MYSQL_OPTS,
    )


def downgrade() -> None:
    op.drop_table("battle_run_loadouts")
    op.drop_index(op.f("ix_battle_loadouts_user_id"), table_name="battle_loadouts")

    op.drop_table("battle_loadouts")
