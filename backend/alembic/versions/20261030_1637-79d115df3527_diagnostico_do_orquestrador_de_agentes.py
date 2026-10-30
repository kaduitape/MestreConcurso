"""diagnostico do orquestrador de agentes

Revision ID: 79d115df3527
Revises: 174d620d1ff0
Create Date: 2026-10-30 16:37:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "79d115df3527"
down_revision: str | None = "174d620d1ff0"
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
        "agent_step_attempts",
        sa.Column("step_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("detail", MEDIUM_TEXT, nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_class", sa.String(length=160), nullable=True),
        sa.Column("traceback", MEDIUM_TEXT, nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("cost_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            ["step_id"],
            ["agent_steps.id"],
            name=op.f("fk_agent_step_attempts_step_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_step_attempts")),
        sa.UniqueConstraint("step_id", "number", name="uq_agent_step_attempts_step_id_number"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_agent_step_attempts_step_id"), "agent_step_attempts", ["step_id"], unique=False
    )
    op.create_index(
        "ix_agent_step_attempts_step", "agent_step_attempts", ["step_id", "number"], unique=False
    )

    # Sinal de vida do passo: sem ele, processo derrubado no meio deixa o passo
    # em "executando" para sempre e não há como saber que ele morreu.
    with op.batch_alter_table("agent_steps") as batch_op:
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))

    # Correlação com a auditoria e o log, e o registro de quem cancelou.
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("request_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("canceled_by_user_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_agent_runs_canceled_by_user_id"),
            "users",
            ["canceled_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_agent_runs_canceled_by_user_id"), type_="foreignkey"
        )
        batch_op.drop_column("canceled_by_user_id")
        batch_op.drop_column("canceled_at")
        batch_op.drop_column("request_id")

    with op.batch_alter_table("agent_steps") as batch_op:
        batch_op.drop_column("heartbeat_at")

    # Derrubar a tabela leva os índices dela junto, nos dois dialetos.
    op.drop_table("agent_step_attempts")
