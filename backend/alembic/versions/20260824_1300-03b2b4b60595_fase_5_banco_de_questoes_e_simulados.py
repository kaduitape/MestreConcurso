"""Fase 5 - banco de questoes, tentativas e simulados

Revision ID: 03b2b4b60595
Revises: 0b9cb9f337b5
Create Date: 2026-08-24 13:00:56.154324
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "03b2b4b60595"
down_revision: str | None = "0b9cb9f337b5"
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
        "simulations",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("questions_count", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("config", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("is_template", sa.Boolean(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            name=op.f("fk_simulations_competition_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_simulations_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulations")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_simulations_public_id"), "simulations", ["public_id"], unique=True)
    op.create_index(op.f("ix_simulations_user_id"), "simulations", ["user_id"], unique=False)
    op.create_index("ix_simulations_user_kind", "simulations", ["user_id", "kind"], unique=False)

    op.create_table(
        "exams",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("exam_board_id", sa.BigInteger(), nullable=True),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("position_id", sa.BigInteger(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("phase", sa.String(length=60), nullable=True),
        sa.Column("applied_on", sa.Date(), nullable=True),
        sa.Column("questions_count", sa.Integer(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("is_official", sa.Boolean(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            name=op.f("fk_exams_competition_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["exam_board_id"],
            ["exam_boards.id"],
            name=op.f("fk_exams_exam_board_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.id"],
            name=op.f("fk_exams_position_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exams")),
        **MYSQL_OPTS,
    )
    op.create_index("ix_exams_board_year", "exams", ["exam_board_id", "year"], unique=False)
    op.create_index("ix_exams_competition", "exams", ["competition_id"], unique=False)
    op.create_index(op.f("ix_exams_exam_board_id"), "exams", ["exam_board_id"], unique=False)
    op.create_index(op.f("ix_exams_public_id"), "exams", ["public_id"], unique=True)
    op.create_index(op.f("ix_exams_year"), "exams", ["year"], unique=False)

    op.create_table(
        "simulation_attempts",
        sa.Column("simulation_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("wrong_count", sa.Integer(), nullable=False),
        sa.Column("blank_count", sa.Integer(), nullable=False),
        sa.Column("score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("analysis", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            ["simulation_id"],
            ["simulations.id"],
            name=op.f("fk_simulation_attempts_simulation_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_simulation_attempts_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_attempts")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_simulation_attempts_public_id"), "simulation_attempts", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_simulation_attempts_simulation_id"),
        "simulation_attempts",
        ["simulation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_attempts_user_id"), "simulation_attempts", ["user_id"], unique=False
    )
    op.create_index(
        "ix_simulation_attempts_user_status",
        "simulation_attempts",
        ["user_id", "status"],
        unique=False,
    )

    op.create_table(
        "questions",
        sa.Column("exam_id", sa.BigInteger(), nullable=True),
        sa.Column("exam_board_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("statement", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "explanation", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("source_note", sa.String(length=255), nullable=True),
        sa.Column("tags", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("ai_suggestion", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            ["exam_board_id"],
            ["exam_boards.id"],
            name=op.f("fk_questions_exam_board_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["exam_id"], ["exams.id"], name=op.f("fk_questions_exam_id"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_questions_reviewed_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_questions_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name=op.f("fk_questions_topic_id"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_questions")),
        sa.UniqueConstraint("checksum", name="uq_questions_checksum"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_questions_board_year", "questions", ["exam_board_id", "year"], unique=False)
    op.create_index(op.f("ix_questions_checksum"), "questions", ["checksum"], unique=False)
    op.create_index(op.f("ix_questions_exam_id"), "questions", ["exam_id"], unique=False)
    op.create_index(op.f("ix_questions_public_id"), "questions", ["public_id"], unique=True)
    op.create_index("ix_questions_status_origin", "questions", ["status", "origin"], unique=False)
    op.create_index(op.f("ix_questions_subject_id"), "questions", ["subject_id"], unique=False)
    op.create_index(
        "ix_questions_subject_topic", "questions", ["subject_id", "topic_id"], unique=False
    )

    op.create_table(
        "alternatives",
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("letter", sa.String(length=2), nullable=False),
        sa.Column("content", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_alternatives_question_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alternatives")),
        sa.UniqueConstraint("question_id", "letter", name="uq_alternatives_question_letter"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_alternatives_public_id"), "alternatives", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_alternatives_question_id"), "alternatives", ["question_id"], unique=False
    )

    op.create_table(
        "question_stats",
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("correct_attempts", sa.Integer(), nullable=False),
        sa.Column("total_time_seconds", sa.BigInteger(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_question_stats_question_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_stats")),
        sa.UniqueConstraint("question_id", name="uq_question_stats_question"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_question_stats_question_id"), "question_stats", ["question_id"], unique=False
    )

    op.create_table(
        "simulation_questions",
        sa.Column("simulation_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_simulation_questions_question_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            name=op.f("fk_simulation_questions_simulation_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_simulation_questions")),
        sa.UniqueConstraint(
            "simulation_id", "question_id", name="uq_simulation_questions_sim_question"
        ),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_simulation_questions_simulation_id"),
        "simulation_questions",
        ["simulation_id"],
        unique=False,
    )

    op.create_table(
        "question_attempts",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("question_id", sa.BigInteger(), nullable=False),
        sa.Column("simulation_attempt_id", sa.BigInteger(), nullable=True),
        sa.Column("study_task_id", sa.BigInteger(), nullable=True),
        sa.Column("selected_alternative_id", sa.BigInteger(), nullable=True),
        sa.Column("selected_letter", sa.String(length=2), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("is_blank", sa.Boolean(), nullable=False),
        sa.Column("time_seconds", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.String(length=10), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
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
            ["question_id"],
            ["questions.id"],
            name=op.f("fk_question_attempts_question_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["selected_alternative_id"],
            ["alternatives.id"],
            name=op.f("fk_question_attempts_selected_alternative_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_attempt_id"],
            ["simulation_attempts.id"],
            name=op.f("fk_question_attempts_simulation_attempt_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["study_task_id"],
            ["study_tasks.id"],
            name=op.f("fk_question_attempts_study_task_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_question_attempts_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_question_attempts_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_question_attempts")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_question_attempts_attempt", "question_attempts", ["simulation_attempt_id"], unique=False
    )
    op.create_index(
        op.f("ix_question_attempts_public_id"), "question_attempts", ["public_id"], unique=True
    )
    op.create_index(
        op.f("ix_question_attempts_question_id"), "question_attempts", ["question_id"], unique=False
    )
    op.create_index(
        "ix_question_attempts_user_created",
        "question_attempts",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_attempts_user_id"), "question_attempts", ["user_id"], unique=False
    )
    op.create_index(
        "ix_question_attempts_user_question",
        "question_attempts",
        ["user_id", "question_id"],
        unique=False,
    )


def downgrade() -> None:

    op.drop_index("ix_question_attempts_user_question", "question_attempts")
    op.drop_index(op.f("ix_question_attempts_user_id"), "question_attempts")
    op.drop_index("ix_question_attempts_user_created", "question_attempts")
    op.drop_index(op.f("ix_question_attempts_question_id"), "question_attempts")
    op.drop_index(op.f("ix_question_attempts_public_id"), "question_attempts")
    op.drop_index("ix_question_attempts_attempt", "question_attempts")

    op.drop_table("question_attempts")
    op.drop_index(op.f("ix_simulation_questions_simulation_id"), "simulation_questions")

    op.drop_table("simulation_questions")
    op.drop_index(op.f("ix_question_stats_question_id"), "question_stats")

    op.drop_table("question_stats")
    op.drop_index(op.f("ix_alternatives_question_id"), "alternatives")
    op.drop_index(op.f("ix_alternatives_public_id"), "alternatives")

    op.drop_table("alternatives")
    op.drop_index("ix_questions_subject_topic", "questions")
    op.drop_index(op.f("ix_questions_subject_id"), "questions")
    op.drop_index("ix_questions_status_origin", "questions")
    op.drop_index(op.f("ix_questions_public_id"), "questions")
    op.drop_index(op.f("ix_questions_exam_id"), "questions")
    op.drop_index(op.f("ix_questions_checksum"), "questions")
    op.drop_index("ix_questions_board_year", "questions")

    op.drop_table("questions")
    op.drop_index("ix_simulation_attempts_user_status", "simulation_attempts")
    op.drop_index(op.f("ix_simulation_attempts_user_id"), "simulation_attempts")
    op.drop_index(op.f("ix_simulation_attempts_simulation_id"), "simulation_attempts")
    op.drop_index(op.f("ix_simulation_attempts_public_id"), "simulation_attempts")

    op.drop_table("simulation_attempts")
    op.drop_index(op.f("ix_exams_year"), "exams")
    op.drop_index(op.f("ix_exams_public_id"), "exams")
    op.drop_index(op.f("ix_exams_exam_board_id"), "exams")
    op.drop_index("ix_exams_competition", "exams")
    op.drop_index("ix_exams_board_year", "exams")

    op.drop_table("exams")
    op.drop_index("ix_simulations_user_kind", "simulations")
    op.drop_index(op.f("ix_simulations_user_id"), "simulations")
    op.drop_index(op.f("ix_simulations_public_id"), "simulations")

    op.drop_table("simulations")
