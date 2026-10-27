"""cronograma do concurso

Revision ID: 174d620d1ff0
Revises: e03dc96a2b31
Create Date: 2026-10-26 15:57:59.391072
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "174d620d1ff0"
down_revision: str | None = "e03dc96a2b31"
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
        "competition_events",
        sa.Column("competition_id", sa.BigInteger(), nullable=False),
        sa.Column("notice_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=False),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=10), nullable=False),
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
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_competition_events_competition_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_competition_events_notice_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competition_events")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_competition_events_public_id"), "competition_events", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_competition_events_competition_id"),
        "competition_events",
        ["competition_id"],
        unique=False,
    )
    op.create_index(
        "ix_competition_events_competition_date",
        "competition_events",
        ["competition_id", "date_start"],
        unique=False,
    )

    # A citação da data do edital: era a única coisa extraída neste projeto que
    # não guardava a própria prova. Anulável porque as análises já feitas não a
    # têm — e refazê-las é o que a nova versão do prompt já provoca.
    with op.batch_alter_table("notice_events") as batch_op:
        batch_op.add_column(sa.Column("quote", MEDIUM_TEXT, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notice_events") as batch_op:
        batch_op.drop_column("quote")

    # Derrubar a tabela leva os índices dela junto, nos dois dialetos.
    op.drop_table("competition_events")
