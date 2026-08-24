"""Fase 4 - plano de estudo, agenda, sessoes e progresso

Revision ID: 0b9cb9f337b5
Revises: e7cbdecc6ac3
Create Date: 2026-08-24 10:08:50.711621
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0b9cb9f337b5"
down_revision: str | None = "e7cbdecc6ac3"
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
        "user_subject_progress",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_key", sa.String(length=60), nullable=False),
        sa.Column("subject_label", sa.String(length=200), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("color_token", sa.String(length=40), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column("studied_minutes", sa.Integer(), nullable=False),
        sa.Column("tasks_done", sa.Integer(), nullable=False),
        sa.Column("tasks_skipped", sa.Integer(), nullable=False),
        sa.Column("last_studied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("is_weak_point", sa.Boolean(), nullable=False),
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
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_user_subject_progress_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_subject_progress_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_subject_progress")),
        sa.UniqueConstraint("user_id", "subject_key", name="uq_user_subject_progress_user_key"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_user_subject_progress_user",
        "user_subject_progress",
        ["user_id", "last_studied_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_subject_progress_user_id"), "user_subject_progress", ["user_id"], unique=False
    )

    op.create_table(
        "study_plans",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("notice_id", sa.BigInteger(), nullable=True),
        sa.Column("position_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("weekly_minutes_target", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recalculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            name=op.f("fk_study_plans_competition_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_study_plans_notice_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["position_id"],
            ["positions.id"],
            name=op.f("fk_study_plans_position_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_study_plans_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_plans")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_study_plans_public_id"), "study_plans", ["public_id"], unique=True)
    op.create_index(op.f("ix_study_plans_user_id"), "study_plans", ["user_id"], unique=False)
    op.create_index(
        "ix_study_plans_user_status", "study_plans", ["user_id", "status"], unique=False
    )

    op.create_table(
        "study_availability",
        sa.Column("study_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=True),
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
            ["study_plan_id"],
            ["study_plans.id"],
            name=op.f("fk_study_availability_study_plan_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_availability")),
        sa.UniqueConstraint("study_plan_id", "weekday", name="uq_study_availability_plan_weekday"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_study_availability_study_plan_id"),
        "study_availability",
        ["study_plan_id"],
        unique=False,
    )

    op.create_table(
        "study_tasks",
        sa.Column("study_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("subject_key", sa.String(length=60), nullable=True),
        sa.Column("subject_label", sa.String(length=200), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("notice_subject_id", sa.BigInteger(), nullable=True),
        sa.Column("color_token", sa.String(length=40), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column("actual_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("reschedule_count", sa.Integer(), nullable=False),
        sa.Column("rescheduled_from", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score_breakdown", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["notice_subject_id"],
            ["notice_subjects.id"],
            name=op.f("fk_study_tasks_notice_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["study_plan_id"],
            ["study_plans.id"],
            name=op.f("fk_study_tasks_study_plan_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_study_tasks_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_study_tasks_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_tasks")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_study_tasks_plan_day", "study_tasks", ["study_plan_id", "scheduled_for"], unique=False
    )
    op.create_index(op.f("ix_study_tasks_public_id"), "study_tasks", ["public_id"], unique=True)
    op.create_index(
        op.f("ix_study_tasks_scheduled_for"), "study_tasks", ["scheduled_for"], unique=False
    )
    op.create_index(
        op.f("ix_study_tasks_study_plan_id"), "study_tasks", ["study_plan_id"], unique=False
    )
    op.create_index(
        "ix_study_tasks_user_day_status",
        "study_tasks",
        ["user_id", "scheduled_for", "status"],
        unique=False,
    )
    op.create_index(op.f("ix_study_tasks_user_id"), "study_tasks", ["user_id"], unique=False)

    op.create_table(
        "study_sessions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("study_task_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_key", sa.String(length=60), nullable=True),
        sa.Column("subject_label", sa.String(length=200), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("focus_seconds", sa.Integer(), nullable=False),
        sa.Column("pause_seconds", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
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
            ["study_task_id"],
            ["study_tasks.id"],
            name=op.f("fk_study_sessions_study_task_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_study_sessions_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_sessions")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_study_sessions_public_id"), "study_sessions", ["public_id"], unique=True
    )
    op.create_index(op.f("ix_study_sessions_user_id"), "study_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_study_sessions_user_started", "study_sessions", ["user_id", "started_at"], unique=False
    )


def downgrade() -> None:

    op.drop_index("ix_study_sessions_user_started", "study_sessions")
    op.drop_index(op.f("ix_study_sessions_user_id"), "study_sessions")
    op.drop_index(op.f("ix_study_sessions_public_id"), "study_sessions")

    op.drop_table("study_sessions")
    op.drop_index(op.f("ix_study_tasks_user_id"), "study_tasks")
    op.drop_index("ix_study_tasks_user_day_status", "study_tasks")
    op.drop_index(op.f("ix_study_tasks_study_plan_id"), "study_tasks")
    op.drop_index(op.f("ix_study_tasks_scheduled_for"), "study_tasks")
    op.drop_index(op.f("ix_study_tasks_public_id"), "study_tasks")
    op.drop_index("ix_study_tasks_plan_day", "study_tasks")

    op.drop_table("study_tasks")
    op.drop_index(op.f("ix_study_availability_study_plan_id"), "study_availability")

    op.drop_table("study_availability")
    op.drop_index("ix_study_plans_user_status", "study_plans")
    op.drop_index(op.f("ix_study_plans_user_id"), "study_plans")
    op.drop_index(op.f("ix_study_plans_public_id"), "study_plans")

    op.drop_table("study_plans")
    op.drop_index(op.f("ix_user_subject_progress_user_id"), "user_subject_progress")
    op.drop_index("ix_user_subject_progress_user", "user_subject_progress")

    op.drop_table("user_subject_progress")
