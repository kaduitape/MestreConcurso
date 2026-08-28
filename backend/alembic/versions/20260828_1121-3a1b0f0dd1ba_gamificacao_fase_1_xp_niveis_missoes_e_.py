"""gamificacao fase 1 xp niveis missoes e conquistas

Revision ID: 3a1b0f0dd1ba
Revises: 27ea19957ee9
Create Date: 2026-08-28 11:21:50.462261
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "3a1b0f0dd1ba"
down_revision: str | None = "27ea19957ee9"
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
        "achievements",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("icon", sa.String(length=10), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("criteria", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_achievements")),
        sa.UniqueConstraint("slug", name="uq_achievements_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_achievements_slug"), "achievements", ["slug"], unique=False)

    op.create_table(
        "game_rules",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("xp_value", sa.Integer(), nullable=False),
        sa.Column("daily_cap", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by_user_id", sa.BigInteger(), nullable=True),
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
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_game_rules_updated_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_game_rules")),
        sa.UniqueConstraint("key", name="uq_game_rules_key"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_game_rules_key"), "game_rules", ["key"], unique=False)

    op.create_table(
        "gamification_profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("xp_total", sa.Integer(), nullable=False),
        sa.Column("rank_slug", sa.String(length=20), nullable=False),
        sa.Column("rank_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("rank_components", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column(
            "rank_missing_signals", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False
        ),
        sa.Column("current_streak", sa.Integer(), nullable=False),
        sa.Column("longest_streak", sa.Integer(), nullable=False),
        sa.Column("last_active_on", sa.Date(), nullable=True),
        sa.Column("streak_shields_left", sa.Integer(), nullable=False),
        sa.Column("streak_shield_renewed_on", sa.Date(), nullable=True),
        sa.Column("missions_completed", sa.Integer(), nullable=False),
        sa.Column("achievements_count", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_gamification_profiles_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gamification_profiles")),
        sa.UniqueConstraint("user_id", name="uq_gamification_profiles_user"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_gamification_profiles_user_id"), "gamification_profiles", ["user_id"], unique=False
    )

    op.create_table(
        "missions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("scope", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=False),
        sa.Column("target_metric", sa.String(length=40), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("current_value", sa.Integer(), nullable=False),
        sa.Column("baseline_value", sa.Integer(), nullable=False),
        sa.Column("xp_reward", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("generated_by", sa.String(length=10), nullable=False),
        sa.Column("rationale", sa.String(length=400), nullable=False),
        sa.Column("source", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_missions_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_missions")),
        sa.UniqueConstraint("user_id", "kind", "valid_from", name="uq_missions_user_kind_day"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_missions_public_id"), "missions", ["public_id"], unique=True)
    op.create_index(op.f("ix_missions_user_id"), "missions", ["user_id"], unique=False)
    op.create_index(
        "ix_missions_user_period", "missions", ["user_id", "valid_from", "status"], unique=False
    )
    op.create_index(op.f("ix_missions_valid_from"), "missions", ["valid_from"], unique=False)

    op.create_table(
        "streak_days",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=False),
        sa.Column("tasks_done", sa.Integer(), nullable=False),
        sa.Column("mission_completed", sa.Boolean(), nullable=False),
        sa.Column("qualified", sa.Boolean(), nullable=False),
        sa.Column("shield_used", sa.Boolean(), nullable=False),
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
            ["user_id"], ["users.id"], name=op.f("fk_streak_days_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_streak_days")),
        sa.UniqueConstraint("user_id", "day", name="uq_streak_days_user_day"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_streak_days_user_day", "streak_days", ["user_id", "day"], unique=False)
    op.create_index(op.f("ix_streak_days_user_id"), "streak_days", ["user_id"], unique=False)

    op.create_table(
        "user_achievements",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("achievement_id", sa.BigInteger(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("progress", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["achievement_id"],
            ["achievements.id"],
            name=op.f("fk_user_achievements_achievement_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_achievements_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_achievements")),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievements_user_item"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_user_achievements_user_id"), "user_achievements", ["user_id"], unique=False
    )
    op.create_index(
        "ix_user_achievements_user_unlocked",
        "user_achievements",
        ["user_id", "unlocked_at"],
        unique=False,
    )

    op.create_table(
        "xp_transactions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_kind", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.SmallInteger(), nullable=False),
        sa.Column("base_amount", sa.Integer(), nullable=False),
        sa.Column("multiplier", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=400), nullable=False),
        sa.Column("reference", sa.String(length=60), nullable=False),
        sa.Column("metrics", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("capped", sa.Boolean(), nullable=False),
        sa.Column("cap_reason", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
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
            ["user_id"], ["users.id"], name=op.f("fk_xp_transactions_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_xp_transactions")),
        sa.UniqueConstraint(
            "user_id", "event_kind", "reference", name="uq_xp_transactions_user_event_ref"
        ),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_xp_transactions_day"), "xp_transactions", ["day"], unique=False)
    op.create_index(
        op.f("ix_xp_transactions_public_id"), "xp_transactions", ["public_id"], unique=True
    )
    op.create_index(
        "ix_xp_transactions_user_created",
        "xp_transactions",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_xp_transactions_user_day", "xp_transactions", ["user_id", "day"], unique=False
    )
    op.create_index(
        op.f("ix_xp_transactions_user_id"), "xp_transactions", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_xp_transactions_user_id"), table_name="xp_transactions")
    op.drop_index("ix_xp_transactions_user_day", table_name="xp_transactions")
    op.drop_index("ix_xp_transactions_user_created", table_name="xp_transactions")
    op.drop_index(op.f("ix_xp_transactions_public_id"), table_name="xp_transactions")
    op.drop_index(op.f("ix_xp_transactions_day"), table_name="xp_transactions")

    op.drop_table("xp_transactions")
    op.drop_index("ix_user_achievements_user_unlocked", table_name="user_achievements")
    op.drop_index(op.f("ix_user_achievements_user_id"), table_name="user_achievements")

    op.drop_table("user_achievements")
    op.drop_index(op.f("ix_streak_days_user_id"), table_name="streak_days")
    op.drop_index("ix_streak_days_user_day", table_name="streak_days")

    op.drop_table("streak_days")
    op.drop_index(op.f("ix_missions_valid_from"), table_name="missions")
    op.drop_index("ix_missions_user_period", table_name="missions")
    op.drop_index(op.f("ix_missions_user_id"), table_name="missions")
    op.drop_index(op.f("ix_missions_public_id"), table_name="missions")

    op.drop_table("missions")
    op.drop_index(op.f("ix_gamification_profiles_user_id"), table_name="gamification_profiles")

    op.drop_table("gamification_profiles")
    op.drop_index(op.f("ix_game_rules_key"), table_name="game_rules")

    op.drop_table("game_rules")
    op.drop_index(op.f("ix_achievements_slug"), table_name="achievements")

    op.drop_table("achievements")
