"""Gamificacao Fase 3 - temporadas, ligas e rodadas de desafio

Revision ID: 772a1d123a44
Revises: e0f012012024
Create Date: 2026-08-28 14:43:27.970509
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "772a1d123a44"
down_revision: str | None = "e0f012012024"
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
        "seasons",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seasons")),
        sa.UniqueConstraint("slug", name="uq_seasons_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_seasons_public_id"), "seasons", ["public_id"], unique=True)
    op.create_index(op.f("ix_seasons_slug"), "seasons", ["slug"], unique=False)
    op.create_index("ix_seasons_window", "seasons", ["starts_on", "ends_on"], unique=False)

    op.create_table(
        "game_runs",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("question_ids", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("selection", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_label", sa.String(length=200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("best_combo", sa.Integer(), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("achieved", sa.Boolean(), nullable=False),
        sa.Column("summary", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            name=op.f("fk_game_runs_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_game_runs_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_runs")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_game_runs_public_id"), "game_runs", ["public_id"], unique=True)
    op.create_index(
        "ix_game_runs_user_created", "game_runs", ["user_id", "created_at"], unique=False
    )
    op.create_index(op.f("ix_game_runs_user_id"), "game_runs", ["user_id"], unique=False)
    op.create_index("ix_game_runs_user_status", "game_runs", ["user_id", "status"], unique=False)

    op.create_table(
        "season_participations",
        sa.Column("season_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("seasonal_xp", sa.Integer(), nullable=False),
        sa.Column("qualified_days", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("participants", sa.Integer(), nullable=False),
        sa.Column("division_index", sa.Integer(), nullable=False),
        sa.Column("context_label", sa.String(length=160), nullable=False),
        sa.Column("rewards", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["season_id"],
            ["seasons.id"],
            name=op.f("fk_season_participations_season_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_season_participations_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_season_participations")),
        sa.UniqueConstraint("season_id", "user_id", name="uq_season_participations_season_user"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_season_participations_season_id"),
        "season_participations",
        ["season_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_season_participations_user_id"), "season_participations", ["user_id"], unique=False
    )

    with op.batch_alter_table("gamification_profiles", schema=None) as batch_op:
        # A coluna nasce em tabela povoada: sem default de servidor, o MySQL
        # recusaria o NOT NULL nas linhas existentes.
        batch_op.add_column(
            sa.Column("league_opt_out", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("league_display_name", sa.String(length=40), nullable=True))

    # Com as linhas existentes já preenchidas, o default sai de cena: quem
    # define o valor de uma linha nova é o modelo, não o banco.
    with op.batch_alter_table("gamification_profiles", schema=None) as batch_op:
        batch_op.alter_column(
            "league_opt_out",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=None,
        )

    with op.batch_alter_table("question_attempts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("game_run_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_question_attempts_game_run_id"),
            "game_runs",
            ["game_run_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("question_attempts", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_question_attempts_game_run_id"), type_="foreignkey")
        batch_op.drop_column("game_run_id")

    with op.batch_alter_table("gamification_profiles", schema=None) as batch_op:
        batch_op.drop_column("league_display_name")
        batch_op.drop_column("league_opt_out")

    op.drop_index(op.f("ix_season_participations_user_id"), table_name="season_participations")
    op.drop_index(op.f("ix_season_participations_season_id"), table_name="season_participations")

    op.drop_table("season_participations")
    op.drop_index("ix_game_runs_user_status", table_name="game_runs")
    op.drop_index(op.f("ix_game_runs_user_id"), table_name="game_runs")
    op.drop_index("ix_game_runs_user_created", table_name="game_runs")
    op.drop_index(op.f("ix_game_runs_public_id"), table_name="game_runs")

    op.drop_table("game_runs")
    op.drop_index("ix_seasons_window", table_name="seasons")
    op.drop_index(op.f("ix_seasons_slug"), table_name="seasons")
    op.drop_index(op.f("ix_seasons_public_id"), table_name="seasons")

    op.drop_table("seasons")
