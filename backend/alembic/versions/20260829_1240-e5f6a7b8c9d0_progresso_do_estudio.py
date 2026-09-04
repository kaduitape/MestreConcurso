"""Progresso e conclusão do Estúdio de Treinamento.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-29 12:40:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
MYSQL_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "training_progress",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("lesson_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("current_scene", sa.Integer(), nullable=False),
        sa.Column("completed_scenes", sa.Integer(), nullable=False),
        sa.Column("focus_seconds", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
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
            ["lesson_id"],
            ["training_lessons.id"],
            name=op.f("fk_training_progress_lesson_id_training_lessons"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_training_progress_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_progress")),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_training_progress_user_lesson"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_training_progress_user_id"), "training_progress", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_training_progress_lesson_id"), "training_progress", ["lesson_id"], unique=False
    )
    op.create_index(
        "ix_training_progress_lesson_status",
        "training_progress",
        ["lesson_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_training_progress_user_updated",
        "training_progress",
        ["user_id", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("training_progress")
