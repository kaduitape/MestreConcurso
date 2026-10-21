"""geracao em massa por topico

Revision ID: a85c48b8b12c
Revises: 1137526cb118
Create Date: 2026-10-21 11:23:50.570194
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "a85c48b8b12c"
down_revision: str | None = "1137526cb118"
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
        "generation_plans",
        sa.Column("competition_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("kinds", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("options", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("estimate_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("estimate_is_known", sa.Boolean(), nullable=False),
        sa.Column("estimate_basis", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("spent_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_generation_plans_competition_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_generation_plans_confirmed_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_generation_plans_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_plans")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_generation_plans_competition_id"),
        "generation_plans",
        ["competition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generation_plans_public_id"), "generation_plans", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_generation_plans_status"), "generation_plans", ["status"], unique=False
    )
    op.create_index(
        "ix_generation_plans_status_created_at",
        "generation_plans",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "generation_items",
        sa.Column("plan_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_name", sa.String(length=200), nullable=False),
        sa.Column("subject_name", sa.String(length=140), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("target_public_id", sa.String(length=26), nullable=True),
        sa.Column("cost_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            ["plan_id"],
            ["generation_plans.id"],
            name=op.f("fk_generation_items_plan_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_generation_items_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_generation_items_topic_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generation_items")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_generation_items_plan_id"), "generation_items", ["plan_id"], unique=False
    )
    op.create_index(
        "ix_generation_items_plan_status", "generation_items", ["plan_id", "status"], unique=False
    )


def downgrade() -> None:
    # Derrubar a tabela já leva os índices dela, e remover índice antes do DROP
    # TABLE é o que falha no MySQL quando ele sustenta uma chave estrangeira.
    op.drop_table("generation_items")
    op.drop_table("generation_plans")
