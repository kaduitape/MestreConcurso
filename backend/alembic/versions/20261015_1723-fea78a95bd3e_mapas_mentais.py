"""Mapas mentais

Revision ID: fea78a95bd3e
Revises: 05598f0ab8c9
Create Date: 2026-10-15 17:23:44.442959
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "fea78a95bd3e"
down_revision: str | None = "05598f0ab8c9"
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
        "mind_maps",
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("subject", sa.String(length=140), nullable=False),
        sa.Column("topic", sa.String(length=240), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("max_panels", sa.Integer(), nullable=False),
        sa.Column(
            "source_content", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("content", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column(
            "generation_error", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_mind_maps_created_by_user_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_mind_maps_subject_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mind_maps")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_mind_maps_created_by_user_id", "mind_maps", ["created_by_user_id"], unique=False
    )
    op.create_index(op.f("ix_mind_maps_public_id"), "mind_maps", ["public_id"], unique=True)
    op.create_index(op.f("ix_mind_maps_status"), "mind_maps", ["status"], unique=False)
    op.create_index(
        "ix_mind_maps_status_created_at", "mind_maps", ["status", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_mind_maps_status_created_at", table_name="mind_maps")
    op.drop_index(op.f("ix_mind_maps_status"), table_name="mind_maps")
    op.drop_index(op.f("ix_mind_maps_public_id"), table_name="mind_maps")
    op.drop_index("ix_mind_maps_created_by_user_id", table_name="mind_maps")

    op.drop_table("mind_maps")
