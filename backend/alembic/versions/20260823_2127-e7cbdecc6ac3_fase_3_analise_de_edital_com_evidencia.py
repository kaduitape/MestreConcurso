"""Fase 3 - analise de edital com prova de origem

Revision ID: e7cbdecc6ac3
Revises: ff1ce9f90a98
Create Date: 2026-08-23 21:27:41.002599
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "e7cbdecc6ac3"
down_revision: str | None = "ff1ce9f90a98"
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
        "documents",
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("owner_type", sa.String(length=30), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant", sa.String(length=40), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("extraction_method", sa.String(length=20), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=True),
        sa.Column("text_coverage", sa.Float(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("meta", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("checksum_sha256", "kind", name="uq_documents_checksum_kind"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_documents_checksum_sha256"), "documents", ["checksum_sha256"], unique=False
    )
    op.create_index("ix_documents_owner", "documents", ["owner_type", "owner_id"], unique=False)
    op.create_index(op.f("ix_documents_public_id"), "documents", ["public_id"], unique=True)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)
    op.create_index(op.f("ix_documents_tenant"), "documents", ["tenant"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.String(length=500), nullable=True),
        sa.Column("section_kind", sa.String(length=40), nullable=True),
        sa.Column("vector_id", sa.String(length=36), nullable=True),
        sa.Column("embedding_model", sa.String(length=120), nullable=True),
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
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"], unique=False
    )
    op.create_index(
        "ix_document_chunks_document_page",
        "document_chunks",
        ["document_id", "page_number"],
        unique=False,
    )
    op.create_index("ix_document_chunks_vector_id", "document_chunks", ["vector_id"], unique=False)

    op.create_table(
        "notice_facts",
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("field_path", sa.String(length=120), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("value", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("evidence_level", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("extracted_by", sa.String(length=20), nullable=False),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_notice_facts_chunk_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_facts_notice_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_notice_facts_reviewed_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_facts")),
        sa.UniqueConstraint("notice_id", "field_path", name="uq_notice_facts_notice_field"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_notice_facts_evidence_level",
        "notice_facts",
        ["notice_id", "evidence_level"],
        unique=False,
    )
    op.create_index(op.f("ix_notice_facts_notice_id"), "notice_facts", ["notice_id"], unique=False)

    op.create_table(
        "notice_sections",
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
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
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_sections_notice_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_sections")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_notice_sections_notice_id"), "notice_sections", ["notice_id"], unique=False
    )
    op.create_index(
        "ix_notice_sections_notice_kind", "notice_sections", ["notice_id", "kind"], unique=False
    )

    op.create_table(
        "notice_subjects",
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("position_label", sa.String(length=200), nullable=True),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_label", sa.String(length=255), nullable=False),
        sa.Column("weight", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("questions_count", sa.Integer(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("evidence_level", sa.String(length=20), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
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
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_subjects_notice_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_notice_subjects_subject_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_subjects")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_notice_subjects_notice", "notice_subjects", ["notice_id", "order_index"], unique=False
    )
    op.create_index(
        op.f("ix_notice_subjects_notice_id"), "notice_subjects", ["notice_id"], unique=False
    )
    op.create_index(
        op.f("ix_notice_subjects_public_id"), "notice_subjects", ["public_id"], unique=True
    )

    op.create_table(
        "notice_events",
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("date_start", sa.Date(), nullable=True),
        sa.Column("date_end", sa.Date(), nullable=True),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("evidence_fact_id", sa.BigInteger(), nullable=True),
        sa.Column("evidence_level", sa.String(length=20), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
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
            ["evidence_fact_id"],
            ["notice_facts.id"],
            name=op.f("fk_notice_events_evidence_fact_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"],
            ["notices.id"],
            name=op.f("fk_notice_events_notice_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_events")),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_notice_events_notice_date", "notice_events", ["notice_id", "date_start"], unique=False
    )
    op.create_index(
        op.f("ix_notice_events_notice_id"), "notice_events", ["notice_id"], unique=False
    )

    op.create_table(
        "notice_topics",
        sa.Column("notice_subject_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=True),
        sa.Column("raw_label", sa.String(length=500), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
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
            ["notice_subject_id"],
            ["notice_subjects.id"],
            name=op.f("fk_notice_topics_notice_subject_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"], ["topics.id"], name=op.f("fk_notice_topics_topic_id"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_topics")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_notice_topics_notice_subject_id"),
        "notice_topics",
        ["notice_subject_id"],
        unique=False,
    )
    op.create_index(
        "ix_notice_topics_subject_order",
        "notice_topics",
        ["notice_subject_id", "order_index"],
        unique=False,
    )

    # Liga o arquivo enviado ao documento extraído dele.
    with op.batch_alter_table("notice_files", schema=None) as batch_op:
        batch_op.add_column(sa.Column("document_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            op.f("fk_notice_files_document_id"),
            "documents",
            ["document_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("notice_files", schema=None) as batch_op:
        batch_op.drop_constraint(op.f("fk_notice_files_document_id"), type_="foreignkey")
        batch_op.drop_column("document_id")

    op.drop_index("ix_notice_topics_subject_order", "notice_topics")
    op.drop_index(op.f("ix_notice_topics_notice_subject_id"), "notice_topics")

    op.drop_table("notice_topics")
    op.drop_index(op.f("ix_notice_events_notice_id"), "notice_events")
    op.drop_index("ix_notice_events_notice_date", "notice_events")

    op.drop_table("notice_events")
    op.drop_index(op.f("ix_notice_subjects_public_id"), "notice_subjects")
    op.drop_index(op.f("ix_notice_subjects_notice_id"), "notice_subjects")
    op.drop_index("ix_notice_subjects_notice", "notice_subjects")

    op.drop_table("notice_subjects")
    op.drop_index("ix_notice_sections_notice_kind", "notice_sections")
    op.drop_index(op.f("ix_notice_sections_notice_id"), "notice_sections")

    op.drop_table("notice_sections")
    op.drop_index(op.f("ix_notice_facts_notice_id"), "notice_facts")
    op.drop_index("ix_notice_facts_evidence_level", "notice_facts")

    op.drop_table("notice_facts")
    op.drop_index("ix_document_chunks_vector_id", "document_chunks")
    op.drop_index("ix_document_chunks_document_page", "document_chunks")
    op.drop_index(op.f("ix_document_chunks_document_id"), "document_chunks")

    op.drop_table("document_chunks")
    op.drop_index(op.f("ix_documents_tenant"), "documents")
    op.drop_index("ix_documents_status", "documents")
    op.drop_index(op.f("ix_documents_public_id"), "documents")
    op.drop_index("ix_documents_owner", "documents")
    op.drop_index(op.f("ix_documents_checksum_sha256"), "documents")

    op.drop_table("documents")
