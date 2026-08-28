"""Gamificacao Fase 4 - duelos, eventos, Modo Guerra e card compartilhavel

Revision ID: fce1976e6881
Revises: 772a1d123a44
Create Date: 2026-08-28 16:11:25.568901
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "fce1976e6881"
down_revision: str | None = "772a1d123a44"
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
        "special_events",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("description", sa.String(length=400), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("goals", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("reward_label", sa.String(length=120), nullable=True),
        sa.Column("reward_utility", sa.String(length=400), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_special_events")),
        sa.UniqueConstraint("slug", name="uq_special_events_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_special_events_public_id"), "special_events", ["public_id"], unique=True
    )
    op.create_index(op.f("ix_special_events_slug"), "special_events", ["slug"], unique=False)
    op.create_index(
        "ix_special_events_window", "special_events", ["starts_on", "ends_on"], unique=False
    )

    op.create_table(
        "duels",
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column("challenger_id", sa.BigInteger(), nullable=False),
        sa.Column("opponent_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("question_ids", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winner_id", sa.BigInteger(), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=True),
        sa.Column("result", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["challenger_id"], ["users.id"], name=op.f("fk_duels_challenger_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["opponent_id"], ["users.id"], name=op.f("fk_duels_opponent_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["winner_id"], ["users.id"], name=op.f("fk_duels_winner_id"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_duels")),
        sa.UniqueConstraint("code", name="uq_duels_code"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_duels_challenger_id"), "duels", ["challenger_id"], unique=False)
    op.create_index(
        "ix_duels_challenger_status", "duels", ["challenger_id", "status"], unique=False
    )
    op.create_index(op.f("ix_duels_code"), "duels", ["code"], unique=False)
    op.create_index("ix_duels_opponent_status", "duels", ["opponent_id", "status"], unique=False)
    op.create_index(op.f("ix_duels_public_id"), "duels", ["public_id"], unique=True)

    op.create_table(
        "event_participations",
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["event_id"],
            ["special_events.id"],
            name=op.f("fk_event_participations_event_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_event_participations_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_participations")),
        sa.UniqueConstraint("event_id", "user_id", name="uq_event_participations_event_user"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_event_participations_event_id"), "event_participations", ["event_id"], unique=False
    )
    op.create_index(
        op.f("ix_event_participations_user_id"), "event_participations", ["user_id"], unique=False
    )

    op.create_table(
        "share_cards",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("token", sa.String(length=43), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("headline", sa.String(length=200), nullable=False),
        sa.Column("stats", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("omitted", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("footer", sa.String(length=400), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_share_cards_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_share_cards")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_share_cards_public_id"), "share_cards", ["public_id"], unique=True)
    op.create_index(op.f("ix_share_cards_token"), "share_cards", ["token"], unique=True)
    op.create_index("ix_share_cards_user", "share_cards", ["user_id"], unique=False)
    op.create_index(op.f("ix_share_cards_user_id"), "share_cards", ["user_id"], unique=False)

    op.create_table(
        "war_campaigns",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("daily_minutes", sa.Integer(), nullable=False),
        sa.Column("daily_questions", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("days_met", sa.Integer(), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
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
            ["user_id"], ["users.id"], name=op.f("fk_war_campaigns_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_war_campaigns")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_war_campaigns_public_id"), "war_campaigns", ["public_id"], unique=True)
    op.create_index(op.f("ix_war_campaigns_user_id"), "war_campaigns", ["user_id"], unique=False)
    op.create_index(
        "ix_war_campaigns_user_status", "war_campaigns", ["user_id", "status"], unique=False
    )

    with op.batch_alter_table("game_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("duel_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_game_runs_duel_id"), "duels", ["duel_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("game_runs", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_game_runs_duel_id"), type_="foreignkey")
        batch_op.drop_column("duel_id")

    op.drop_index("ix_war_campaigns_user_status", table_name="war_campaigns")
    op.drop_index(op.f("ix_war_campaigns_user_id"), table_name="war_campaigns")
    op.drop_index(op.f("ix_war_campaigns_public_id"), table_name="war_campaigns")

    op.drop_table("war_campaigns")
    op.drop_index(op.f("ix_share_cards_user_id"), table_name="share_cards")
    op.drop_index("ix_share_cards_user", table_name="share_cards")
    op.drop_index(op.f("ix_share_cards_token"), table_name="share_cards")
    op.drop_index(op.f("ix_share_cards_public_id"), table_name="share_cards")

    op.drop_table("share_cards")
    op.drop_index(op.f("ix_event_participations_user_id"), table_name="event_participations")
    op.drop_index(op.f("ix_event_participations_event_id"), table_name="event_participations")

    op.drop_table("event_participations")
    op.drop_index(op.f("ix_duels_public_id"), table_name="duels")
    op.drop_index("ix_duels_opponent_status", table_name="duels")
    op.drop_index(op.f("ix_duels_code"), table_name="duels")
    op.drop_index("ix_duels_challenger_status", table_name="duels")
    op.drop_index(op.f("ix_duels_challenger_id"), table_name="duels")

    op.drop_table("duels")
    op.drop_index("ix_special_events_window", table_name="special_events")
    op.drop_index(op.f("ix_special_events_slug"), table_name="special_events")
    op.drop_index(op.f("ix_special_events_public_id"), table_name="special_events")

    op.drop_table("special_events")
