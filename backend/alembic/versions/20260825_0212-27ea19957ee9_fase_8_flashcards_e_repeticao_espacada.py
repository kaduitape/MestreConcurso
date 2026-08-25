"""fase 8 flashcards e repeticao espacada

Revision ID: 27ea19957ee9
Revises: 7b7eb5924621
Create Date: 2026-08-25 02:12:30.418363
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "27ea19957ee9"
down_revision: str | None = "7b7eb5924621"
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
        "flashcards",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("front", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("back", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("hint", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("tags", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("extra", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=60), nullable=True),
        sa.Column(
            "source_quote", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
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
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_flashcards_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name=op.f("fk_flashcards_topic_id"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_flashcards_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flashcards")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_flashcards_checksum"), "flashcards", ["checksum"], unique=False)
    op.create_index("ix_flashcards_origin", "flashcards", ["origin", "is_active"], unique=False)
    op.create_index(op.f("ix_flashcards_public_id"), "flashcards", ["public_id"], unique=True)
    op.create_index(op.f("ix_flashcards_user_id"), "flashcards", ["user_id"], unique=False)
    op.create_index(
        "ix_flashcards_user_subject", "flashcards", ["user_id", "subject_id"], unique=False
    )

    op.create_table(
        "flashcard_reviews",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("flashcard_id", sa.BigInteger(), nullable=False),
        sa.Column("rating", sa.String(length=10), nullable=False),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("previous_interval_days", sa.Integer(), nullable=False),
        sa.Column("next_interval_days", sa.Integer(), nullable=False),
        sa.Column("ease_factor", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("breakdown", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["flashcard_id"],
            ["flashcards.id"],
            name=op.f("fk_flashcard_reviews_flashcard_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_flashcard_reviews_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flashcard_reviews")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_flashcard_reviews_card", "flashcard_reviews", ["flashcard_id"], unique=False
    )
    op.create_index(
        "ix_flashcard_reviews_user_created",
        "flashcard_reviews",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flashcard_reviews_user_id"), "flashcard_reviews", ["user_id"], unique=False
    )

    op.create_table(
        "flashcard_states",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("flashcard_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("ease_factor", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("repetitions", sa.Integer(), nullable=False),
        sa.Column("lapses", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rating", sa.String(length=10), nullable=True),
        sa.Column("last_breakdown", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("postponed_count", sa.Integer(), nullable=False),
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
            ["flashcard_id"],
            ["flashcards.id"],
            name=op.f("fk_flashcard_states_flashcard_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_flashcard_states_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flashcard_states")),
        sa.UniqueConstraint("user_id", "flashcard_id", name="uq_flashcard_states_user_card"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_flashcard_states_due_on"), "flashcard_states", ["due_on"], unique=False
    )
    op.create_index(
        op.f("ix_flashcard_states_flashcard_id"), "flashcard_states", ["flashcard_id"], unique=False
    )
    op.create_index(
        "ix_flashcard_states_user_due", "flashcard_states", ["user_id", "due_on"], unique=False
    )
    op.create_index(
        op.f("ix_flashcard_states_user_id"), "flashcard_states", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_flashcard_states_user_id"), table_name="flashcard_states")
    op.drop_index("ix_flashcard_states_user_due", table_name="flashcard_states")
    op.drop_index(op.f("ix_flashcard_states_flashcard_id"), table_name="flashcard_states")
    op.drop_index(op.f("ix_flashcard_states_due_on"), table_name="flashcard_states")

    op.drop_table("flashcard_states")
    op.drop_index(op.f("ix_flashcard_reviews_user_id"), table_name="flashcard_reviews")
    op.drop_index("ix_flashcard_reviews_user_created", table_name="flashcard_reviews")
    op.drop_index("ix_flashcard_reviews_card", table_name="flashcard_reviews")

    op.drop_table("flashcard_reviews")
    op.drop_index("ix_flashcards_user_subject", table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_user_id"), table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_public_id"), table_name="flashcards")
    op.drop_index("ix_flashcards_origin", table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_checksum"), table_name="flashcards")

    op.drop_table("flashcards")
