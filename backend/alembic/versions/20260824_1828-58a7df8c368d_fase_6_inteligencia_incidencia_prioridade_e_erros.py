"""Fase 6 - inteligencia: incidencia, DNA da banca, prioridade e erros

Revision ID: 58a7df8c368d
Revises: 03b2b4b60595
Create Date: 2026-08-24 18:28:19.071939
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "58a7df8c368d"
down_revision: str | None = "03b2b4b60595"
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
        "trap_patterns",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False),
        sa.Column(
            "description", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column(
            "detection_hint", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("example", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trap_patterns")),
        sa.UniqueConstraint("slug", name="uq_trap_patterns_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_trap_patterns_public_id"), "trap_patterns", ["public_id"], unique=True)
    op.create_index(op.f("ix_trap_patterns_slug"), "trap_patterns", ["slug"], unique=False)

    op.create_table(
        "board_profile_metrics",
        sa.Column("scope_key", sa.String(length=160), nullable=False),
        sa.Column("exam_board_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("metric_slug", sa.String(length=60), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Numeric(precision=6, scale=3), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("detail", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("sample_exams", sa.Integer(), nullable=False),
        sa.Column("sample_questions", sa.Integer(), nullable=False),
        sa.Column("period_start_year", sa.Integer(), nullable=True),
        sa.Column("period_end_year", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
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
            ["exam_board_id"],
            ["exam_boards.id"],
            name=op.f("fk_board_profile_metrics_exam_board_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_board_profile_metrics_subject_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_board_profile_metrics")),
        sa.UniqueConstraint("scope_key", name="uq_board_profile_metrics_scope_key"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_board_profile_metrics_board",
        "board_profile_metrics",
        ["exam_board_id", "metric_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_board_profile_metrics_exam_board_id"),
        "board_profile_metrics",
        ["exam_board_id"],
        unique=False,
    )

    op.create_table(
        "topic_incidence",
        sa.Column("scope_key", sa.String(length=160), nullable=False),
        sa.Column("exam_board_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_name", sa.String(length=200), nullable=False),
        sa.Column("topic_name", sa.String(length=200), nullable=True),
        sa.Column("period_start_year", sa.Integer(), nullable=False),
        sa.Column("period_end_year", sa.Integer(), nullable=False),
        sa.Column("exams_count", sa.Integer(), nullable=False),
        sa.Column("questions_count", sa.Integer(), nullable=False),
        sa.Column("board_questions_count", sa.Integer(), nullable=False),
        sa.Column("incidence_pct", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("trend", sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
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
            ["exam_board_id"],
            ["exam_boards.id"],
            name=op.f("fk_topic_incidence_exam_board_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_topic_incidence_subject_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_topic_incidence_topic_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topic_incidence")),
        sa.UniqueConstraint("scope_key", name="uq_topic_incidence_scope_key"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_topic_incidence_board_subject",
        "topic_incidence",
        ["exam_board_id", "subject_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_topic_incidence_exam_board_id"), "topic_incidence", ["exam_board_id"], unique=False
    )
    op.create_index(
        op.f("ix_topic_incidence_subject_id"), "topic_incidence", ["subject_id"], unique=False
    )

    op.create_table(
        "user_priorities",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("study_plan_id", sa.BigInteger(), nullable=True),
        sa.Column("scope_key", sa.String(length=120), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("color_token", sa.String(length=40), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("contributions", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("coverage", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("missing_signals", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
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
            ["study_plan_id"],
            ["study_plans.id"],
            name=op.f("fk_user_priorities_study_plan_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_user_priorities_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_user_priorities_topic_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_priorities_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_priorities")),
        sa.UniqueConstraint("user_id", "scope_key", name="uq_user_priorities_user_scope"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_user_priorities_user_id"), "user_priorities", ["user_id"], unique=False
    )
    op.create_index(
        "ix_user_priorities_user_score", "user_priorities", ["user_id", "score"], unique=False
    )

    op.create_table(
        "error_analyses",
        sa.Column("question_attempt_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("cause", sa.String(length=30), nullable=False),
        sa.Column("trap_pattern_id", sa.BigInteger(), nullable=True),
        sa.Column("note", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("rationale", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            ["question_attempt_id"],
            ["question_attempts.id"],
            name=op.f("fk_error_analyses_question_attempt_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_error_analyses_question_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_error_analyses_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trap_pattern_id"],
            ["trap_patterns.id"],
            name=op.f("fk_error_analyses_trap_pattern_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_error_analyses_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_error_analyses")),
        sa.UniqueConstraint("question_attempt_id", name="uq_error_analyses_attempt"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_error_analyses_public_id"), "error_analyses", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_error_analyses_question_attempt_id"),
        "error_analyses",
        ["question_attempt_id"],
        unique=False,
    )
    op.create_index(
        "ix_error_analyses_user_cause", "error_analyses", ["user_id", "cause"], unique=False
    )
    op.create_index(
        "ix_error_analyses_user_created", "error_analyses", ["user_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_error_analyses_user_id"), "error_analyses", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_error_analyses_user_id"), table_name="error_analyses")
    op.drop_index("ix_error_analyses_user_created", table_name="error_analyses")
    op.drop_index("ix_error_analyses_user_cause", table_name="error_analyses")
    op.drop_index(op.f("ix_error_analyses_question_attempt_id"), table_name="error_analyses")
    op.drop_index(op.f("ix_error_analyses_public_id"), table_name="error_analyses")

    op.drop_table("error_analyses")
    op.drop_index("ix_user_priorities_user_score", table_name="user_priorities")
    op.drop_index(op.f("ix_user_priorities_user_id"), table_name="user_priorities")

    op.drop_table("user_priorities")
    op.drop_index(op.f("ix_topic_incidence_subject_id"), table_name="topic_incidence")
    op.drop_index(op.f("ix_topic_incidence_exam_board_id"), table_name="topic_incidence")
    op.drop_index("ix_topic_incidence_board_subject", table_name="topic_incidence")

    op.drop_table("topic_incidence")
    op.drop_index(
        op.f("ix_board_profile_metrics_exam_board_id"), table_name="board_profile_metrics"
    )
    op.drop_index("ix_board_profile_metrics_board", table_name="board_profile_metrics")

    op.drop_table("board_profile_metrics")
    op.drop_index(op.f("ix_trap_patterns_slug"), table_name="trap_patterns")
    op.drop_index(op.f("ix_trap_patterns_public_id"), table_name="trap_patterns")

    op.drop_table("trap_patterns")
