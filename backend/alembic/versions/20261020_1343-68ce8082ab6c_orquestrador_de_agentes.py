"""orquestrador de agentes

Revision ID: 68ce8082ab6c
Revises: 35cf5e2fb21f
Create Date: 2026-10-20 13:43:10.252251
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "68ce8082ab6c"
down_revision: str | None = "35cf5e2fb21f"
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
        "agent_runs",
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("started_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("cost_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_agent_runs_competition_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["started_by_user_id"],
            ["users.id"],
            name=op.f("fk_agent_runs_started_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_agent_runs_competition_id"), "agent_runs", ["competition_id"], unique=False
    )
    op.create_index(op.f("ix_agent_runs_public_id"), "agent_runs", ["public_id"], unique=True)
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)
    op.create_index(
        "ix_agent_runs_status_created_at", "agent_runs", ["status", "created_at"], unique=False
    )

    op.create_table(
        "agent_steps",
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_key", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("detail", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("result", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("cost_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
            ["run_id"], ["agent_runs.id"], name=op.f("fk_agent_steps_run_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_steps")),
        sa.UniqueConstraint("run_id", "agent_key", name="uq_agent_steps_run_id_agent_key"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_agent_steps_run_id"), "agent_steps", ["run_id"], unique=False)
    op.create_index(
        "ix_agent_steps_run_id_status", "agent_steps", ["run_id", "status"], unique=False
    )


def downgrade() -> None:
    # Derrubar a tabela já leva os índices dela. Remover o índice antes falha no
    # MySQL quando é ele que sustenta a chave estrangeira — "Cannot drop index
    # 'ix_agent_runs_competition_id': needed in a foreign key constraint". O
    # SQLite dos testes não reclama, então isso só aparece em banco de verdade.
    op.drop_table("agent_steps")
    op.drop_table("agent_runs")
