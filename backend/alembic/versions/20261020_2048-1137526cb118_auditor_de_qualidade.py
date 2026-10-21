"""auditor de qualidade

Revision ID: 1137526cb118
Revises: 68ce8082ab6c
Create Date: 2026-10-20 20:48:11.768949
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "1137526cb118"
down_revision: str | None = "68ce8082ab6c"
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
        "content_audit_rules",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("config", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            name=op.f("fk_content_audit_rules_updated_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_audit_rules")),
        sa.UniqueConstraint("key", name="uq_content_audit_rules_key"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_content_audit_rules_key"), "content_audit_rules", ["key"], unique=False
    )

    op.create_table(
        "content_audits",
        sa.Column("target_kind", sa.String(length=30), nullable=False),
        sa.Column("target_public_id", sa.String(length=26), nullable=False),
        sa.Column("verdict", sa.String(length=20), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False),
        sa.Column("blocked_publication", sa.Boolean(), nullable=False),
        sa.Column("findings", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("summary", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
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
            ["competition_id"],
            ["competitions.id"],
            name=op.f("fk_content_audits_competition_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_content_audits_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_audits")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_content_audits_public_id"), "content_audits", ["public_id"], unique=True
    )
    op.create_index(
        "ix_content_audits_target",
        "content_audits",
        ["target_kind", "target_public_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_content_audits_target_public_id"),
        "content_audits",
        ["target_public_id"],
        unique=False,
    )
    op.create_index(
        "ix_content_audits_verdict_created",
        "content_audits",
        ["verdict", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    # Derrubar a tabela já leva os índices dela, e remover índice antes do
    # DROP TABLE é o que falha no MySQL quando o índice sustenta uma chave
    # estrangeira. O SQLite dos testes não reclama — só o banco de verdade.
    op.drop_table("content_audits")
    op.drop_table("content_audit_rules")
