"""cadastro de concurso pelo edital

Revision ID: e71d9a3c5f28
Revises: d58c2b4f91ac
Create Date: 2026-10-24 09:30:11.402876
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "e71d9a3c5f28"
down_revision: str | None = "d58c2b4f91ac"
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

MEDIUM_TEXT = sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql")
JSON_TYPE = sa.JSON().with_variant(mysql.JSON(), "mysql")


def upgrade() -> None:
    op.create_table(
        "competition_intakes",
        sa.Column("source_kind", sa.String(length=10), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("notice_id", sa.BigInteger(), nullable=True),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("candidates", JSON_TYPE, nullable=False),
        sa.Column("chosen_url", sa.String(length=500), nullable=True),
        sa.Column("choice_reason", MEDIUM_TEXT, nullable=True),
        sa.Column("proposal", JSON_TYPE, nullable=False),
        sa.Column("matches", JSON_TYPE, nullable=False),
        sa.Column("detail", MEDIUM_TEXT, nullable=True),
        sa.Column("auto_applied", sa.Boolean(), nullable=False),
        sa.Column("gaps", JSON_TYPE, nullable=False),
        sa.Column("applied_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["applied_by_user_id"],
            ["users.id"],
            name=op.f("fk_competition_intakes_applied_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_competition_intakes_competition_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_competition_intakes_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_competition_intakes_notice_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competition_intakes")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_competition_intakes_public_id"),
        "competition_intakes",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_competition_intakes_status"), "competition_intakes", ["status"], unique=False
    )
    op.create_index(
        "ix_competition_intakes_status_created",
        "competition_intakes",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Derrubar a tabela leva os índices dela junto, nos dois dialetos.
    op.drop_table("competition_intakes")
