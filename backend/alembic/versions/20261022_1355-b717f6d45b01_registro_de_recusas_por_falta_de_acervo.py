"""registro de recusas por falta de acervo

Revision ID: b717f6d45b01
Revises: 9de7389084a8
Create Date: 2026-10-22 13:55:12.837162
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "b717f6d45b01"
down_revision: str | None = "9de7389084a8"
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
        "resource_refusals",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=60), nullable=False),
        sa.Column("detail", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("variant", sa.String(length=40), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("requested", sa.Integer(), nullable=True),
        sa.Column("available", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_resource_refusals_competition_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_resource_refusals_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_resource_refusals_topic_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_resource_refusals_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_refusals")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_resource_refusals_created_at"), "resource_refusals", ["created_at"], unique=False
    )
    op.create_index(
        "ix_resource_refusals_kind_created_at",
        "resource_refusals",
        ["kind", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_resource_refusals_subject_created_at",
        "resource_refusals",
        ["subject_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Derrubar a tabela leva os índices dela junto, nos dois dialetos.
    op.drop_table("resource_refusals")
