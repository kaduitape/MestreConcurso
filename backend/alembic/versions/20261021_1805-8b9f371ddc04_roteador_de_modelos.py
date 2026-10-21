"""roteador de modelos

Revision ID: 8b9f371ddc04
Revises: 085b713a07be
Create Date: 2026-10-21 18:05:51.463934
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "8b9f371ddc04"
down_revision: str | None = "085b713a07be"
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
        "ai_model_routes",
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("model_id", sa.BigInteger(), nullable=True),
        sa.Column("min_input_chars", sa.Integer(), nullable=True),
        sa.Column("max_input_chars", sa.Integer(), nullable=True),
        sa.Column("requires_json", sa.Boolean(), nullable=True),
        sa.Column("min_budget_used_pct", sa.Numeric(precision=5, scale=2), nullable=True),
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
            ["model_id"],
            ["ai_models.id"],
            name=op.f("fk_ai_model_routes_model_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_model_routes")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_ai_model_routes_feature"), "ai_model_routes", ["feature"], unique=False
    )
    op.create_index(
        "ix_ai_model_routes_feature_priority",
        "ai_model_routes",
        ["feature", "priority"],
        unique=False,
    )

    op.create_table(
        "ai_routing_decisions",
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("model_id", sa.BigInteger(), nullable=True),
        sa.Column("model_slug", sa.String(length=120), nullable=False),
        sa.Column("provider_slug", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("route_id", sa.BigInteger(), nullable=True),
        sa.Column("route_label", sa.String(length=120), nullable=True),
        sa.Column("explanation", sa.String(length=500), nullable=False),
        sa.Column("signals", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("trace", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["ai_models.id"],
            name=op.f("fk_ai_routing_decisions_model_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["ai_model_routes.id"],
            name=op.f("fk_ai_routing_decisions_route_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_routing_decisions")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_ai_routing_decisions_created_at"),
        "ai_routing_decisions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_routing_decisions_feature_created_at",
        "ai_routing_decisions",
        ["feature", "created_at"],
        unique=False,
    )

    with op.batch_alter_table("ai_usage", schema=None) as batch_op:
        batch_op.add_column(sa.Column("routing_decision_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_ai_usage_routing_decision_id"),
            "ai_routing_decisions",
            ["routing_decision_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    # A coluna de ``ai_usage`` sai primeiro: no MySQL a chave estrangeira dela
    # impediria o ``DROP TABLE`` das decisões.
    with op.batch_alter_table("ai_usage", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_ai_usage_routing_decision_id"), type_="foreignkey")
        batch_op.drop_column("routing_decision_id")

    # Derrubar a tabela leva os índices dela junto, nos dois dialetos. Soltar
    # índice antes do ``DROP TABLE`` só cria a chance de o MySQL recusar um que
    # ele considere necessário a alguma chave estrangeira.
    op.drop_table("ai_routing_decisions")
    op.drop_table("ai_model_routes")
