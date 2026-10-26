"""cargos do edital como lista

Revision ID: e03dc96a2b31
Revises: e71d9a3c5f28
Create Date: 2026-10-25 21:05:47.135608
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "e03dc96a2b31"
down_revision: str | None = "e71d9a3c5f28"
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


def upgrade() -> None:
    op.create_table(
        "notice_positions",
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("position_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_label", sa.String(length=200), nullable=False),
        sa.Column("education_level", sa.String(length=20), nullable=True),
        sa.Column("salary_cents", sa.BigInteger(), nullable=True),
        sa.Column("vacancies", sa.Integer(), nullable=True),
        sa.Column("cr_vacancies", sa.Integer(), nullable=True),
        sa.Column("workload_hours", sa.Integer(), nullable=True),
        sa.Column("requirements", MEDIUM_TEXT, nullable=True),
        sa.Column("questions_count", sa.Integer(), nullable=True),
        sa.Column("exam_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("evidence_level", sa.String(length=20), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote", MEDIUM_TEXT, nullable=True),
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
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_positions_notice_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.id"],
            name=op.f("fk_notice_positions_position_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_positions")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_notice_positions_public_id"), "notice_positions", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_notice_positions_notice_id"), "notice_positions", ["notice_id"], unique=False
    )
    op.create_index(
        "ix_notice_positions_notice",
        "notice_positions",
        ["notice_id", "order_index"],
        unique=False,
    )


def downgrade() -> None:
    # Derrubar a tabela leva os índices dela junto, nos dois dialetos.
    op.drop_table("notice_positions")
