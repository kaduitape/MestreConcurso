"""Estúdio de Treinamento: aulas estruturadas em cenas.

Revision ID: d4e5f6a7b8c9
Revises: ab683435d344
Create Date: 2026-08-29 10:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "ab683435d344"
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
        "training_lessons",
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=False),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=140), nullable=False),
        sa.Column("topic", sa.String(length=240), nullable=False),
        sa.Column("character_name", sa.String(length=120), nullable=False),
        sa.Column(
            "additional_prompt", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("style", sa.String(length=40), nullable=False),
        sa.Column("target_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("board_name", sa.String(length=120), nullable=True),
        sa.Column("research_before_generate", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("script", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_training_lessons_competition_id_competitions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_training_lessons_created_by_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_lessons")),
        sa.UniqueConstraint("public_id", name=op.f("uq_training_lessons_public_id")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_training_lessons_public_id"), "training_lessons", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_training_lessons_created_by_user_id"),
        "training_lessons",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_lessons_status"), "training_lessons", ["status"], unique=False
    )
    op.create_index(
        "ix_training_lessons_status_created_at",
        "training_lessons",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_training_lessons_created_by_user_id_created_at",
        "training_lessons",
        ["created_by_user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("training_lessons")
