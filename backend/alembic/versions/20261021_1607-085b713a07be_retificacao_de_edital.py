"""retificacao de edital

Revision ID: 085b713a07be
Revises: a85c48b8b12c
Create Date: 2026-10-21 16:07:21.257406
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "085b713a07be"
down_revision: str | None = "a85c48b8b12c"
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
        "notice_diffs",
        sa.Column("competition_id", sa.BigInteger(), nullable=False),
        sa.Column("from_notice_id", sa.BigInteger(), nullable=True),
        sa.Column("to_notice_id", sa.BigInteger(), nullable=True),
        sa.Column("from_notice_title", sa.String(length=255), nullable=False),
        sa.Column("to_notice_title", sa.String(length=255), nullable=False),
        sa.Column("changes", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("impacts", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("summary", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_notice_diffs_competition_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_notice_diffs_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["from_notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_diffs_from_notice_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_notice_diffs_reviewed_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["to_notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_diffs_to_notice_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_diffs")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_notice_diffs_competition_created",
        "notice_diffs",
        ["competition_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notice_diffs_competition_id"), "notice_diffs", ["competition_id"], unique=False
    )
    op.create_index(op.f("ix_notice_diffs_public_id"), "notice_diffs", ["public_id"], unique=True)


def downgrade() -> None:
    # Derrubar a tabela já leva os índices dela, e remover índice antes do DROP
    # TABLE é o que falha no MySQL quando ele sustenta uma chave estrangeira.
    op.drop_table("notice_diffs")
