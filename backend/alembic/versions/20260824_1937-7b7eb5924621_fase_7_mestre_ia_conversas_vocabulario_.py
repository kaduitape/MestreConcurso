"""fase 7 mestre ia conversas vocabulario e videos

Revision ID: 7b7eb5924621
Revises: 58a7df8c368d
Create Date: 2026-08-24 19:37:58.685309
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "7b7eb5924621"
down_revision: str | None = "58a7df8c368d"
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
        "video_resources",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("channel", sa.String(length=160), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("summary", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("verified_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_video_resources_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["topics.id"],
            name=op.f("fk_video_resources_topic_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"],
            ["users.id"],
            name=op.f("fk_video_resources_verified_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_video_resources")),
        sa.UniqueConstraint("url", name="uq_video_resources_url"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_video_resources_public_id"), "video_resources", ["public_id"], unique=True
    )
    op.create_index(
        "ix_video_resources_subject", "video_resources", ["subject_id", "is_active"], unique=False
    )

    op.create_table(
        "chat_conversations",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("notice_id", sa.BigInteger(), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False),
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
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_chat_conversations_notice_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_chat_conversations_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_conversations_user_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_conversations")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_chat_conversations_public_id"), "chat_conversations", ["public_id"], unique=True
    )
    op.create_index(
        "ix_chat_conversations_user_activity",
        "chat_conversations",
        ["user_id", "last_message_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_conversations_user_id"), "chat_conversations", ["user_id"], unique=False
    )

    op.create_table(
        "chat_messages",
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("claims", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("sources", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column(
            "computed_context", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False
        ),
        sa.Column("is_refusal", sa.Boolean(), nullable=False),
        sa.Column(
            "refusal_reason", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("grounding_ratio", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
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
            ["conversation_id"],
            ["chat_conversations.id"],
            name=op.f("fk_chat_messages_conversation_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_chat_messages_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_chat_messages_conversation", "chat_messages", ["conversation_id", "id"], unique=False
    )
    op.create_index(
        op.f("ix_chat_messages_conversation_id"), "chat_messages", ["conversation_id"], unique=False
    )
    op.create_index(op.f("ix_chat_messages_public_id"), "chat_messages", ["public_id"], unique=True)
    op.create_index(op.f("ix_chat_messages_user_id"), "chat_messages", ["user_id"], unique=False)

    op.create_table(
        "vocabulary_terms",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("term", sa.String(length=160), nullable=False),
        sa.Column("term_key", sa.String(length=160), nullable=False),
        sa.Column(
            "definition", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False
        ),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "source_quote", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("origin", sa.String(length=20), nullable=False),
        sa.Column("times_reviewed", sa.Integer(), nullable=False),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["message_id"],
            ["chat_messages.id"],
            name=op.f("fk_vocabulary_terms_message_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_vocabulary_terms_subject_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_vocabulary_terms_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vocabulary_terms")),
        sa.UniqueConstraint("user_id", "term_key", name="uq_vocabulary_terms_user_term"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_vocabulary_terms_public_id"), "vocabulary_terms", ["public_id"], unique=True
    )
    op.create_index(
        "ix_vocabulary_terms_user_created",
        "vocabulary_terms",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vocabulary_terms_user_id"), "vocabulary_terms", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_vocabulary_terms_user_id"), table_name="vocabulary_terms")
    op.drop_index("ix_vocabulary_terms_user_created", table_name="vocabulary_terms")
    op.drop_index(op.f("ix_vocabulary_terms_public_id"), table_name="vocabulary_terms")

    op.drop_table("vocabulary_terms")
    op.drop_index(op.f("ix_chat_messages_user_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_public_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_conversation_id"), table_name="chat_messages")
    op.drop_index("ix_chat_messages_conversation", table_name="chat_messages")

    op.drop_table("chat_messages")
    op.drop_index(op.f("ix_chat_conversations_user_id"), table_name="chat_conversations")
    op.drop_index("ix_chat_conversations_user_activity", table_name="chat_conversations")
    op.drop_index(op.f("ix_chat_conversations_public_id"), table_name="chat_conversations")

    op.drop_table("chat_conversations")
    op.drop_index("ix_video_resources_subject", table_name="video_resources")
    op.drop_index(op.f("ix_video_resources_public_id"), table_name="video_resources")

    op.drop_table("video_resources")
