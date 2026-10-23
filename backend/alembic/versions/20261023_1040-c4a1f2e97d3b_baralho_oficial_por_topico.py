"""baralho oficial por topico

Revision ID: c4a1f2e97d3b
Revises: b717f6d45b01
Create Date: 2026-10-23 10:40:18.221043
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "c4a1f2e97d3b"
down_revision: str | None = "b717f6d45b01"
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
        "official_decks",
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", MEDIUM_TEXT, nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source_kind", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=60), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("published_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_official_decks_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_official_decks_published_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_official_decks_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_official_decks_topic_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_official_decks")),
        sa.UniqueConstraint("topic_id", name="uq_official_decks_topic"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_official_decks_public_id"), "official_decks", ["public_id"], unique=True
    )
    op.create_index(op.f("ix_official_decks_status"), "official_decks", ["status"], unique=False)
    op.create_index(
        op.f("ix_official_decks_subject_id"), "official_decks", ["subject_id"], unique=False
    )
    op.create_index(
        op.f("ix_official_decks_topic_id"), "official_decks", ["topic_id"], unique=False
    )
    op.create_index(
        "ix_official_decks_status_created_at",
        "official_decks",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "official_deck_subscriptions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("deck_id", sa.BigInteger(), nullable=False),
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
            ["deck_id"],
            ["official_decks.id"],
            name=op.f("fk_official_deck_subscriptions_deck_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_official_deck_subscriptions_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_official_deck_subscriptions")),
        sa.UniqueConstraint("user_id", "deck_id", name="uq_deck_subscriptions_user_deck"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_official_deck_subscriptions_deck_id"),
        "official_deck_subscriptions",
        ["deck_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_official_deck_subscriptions_user_id"),
        "official_deck_subscriptions",
        ["user_id"],
        unique=False,
    )

    # O SQLite dos testes não faz ALTER de constraint: a coluna e a chave
    # entram em ``batch_alter_table``, que no MySQL continua um ALTER só.
    with op.batch_alter_table("flashcards", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deck_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_flashcards_deck_id"),
            "official_decks",
            ["deck_id"],
            ["id"],
            ondelete="CASCADE",
        )
    op.create_index(op.f("ix_flashcards_deck_id"), "flashcards", ["deck_id"], unique=False)
    op.create_index("ix_flashcards_deck_active", "flashcards", ["deck_id", "is_active"])


def downgrade() -> None:
    # A coluna de ``flashcards`` sai primeiro: no MySQL a chave estrangeira dela
    # impediria o ``DROP TABLE`` dos baralhos.
    #
    # E a chave sai antes dos índices: o MySQL exige um índice que comece pela
    # coluna da chave estrangeira e recusa soltá-lo enquanto ela existe
    # (``ERROR 1553``). Soltar o índice primeiro deixava o banco com a migração
    # meio desfeita e a versão ainda carimbada como aplicada.
    with op.batch_alter_table("flashcards", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_flashcards_deck_id"), type_="foreignkey")
    op.drop_index("ix_flashcards_deck_active", table_name="flashcards")
    op.drop_index(op.f("ix_flashcards_deck_id"), table_name="flashcards")
    with op.batch_alter_table("flashcards", schema=None) as batch_op:
        batch_op.drop_column("deck_id")
    # Derrubar a tabela leva os índices dela junto, nos dois dialetos.
    op.drop_table("official_deck_subscriptions")
    op.drop_table("official_decks")
