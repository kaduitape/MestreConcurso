"""Batalha RPG: arte cadastravel de monstros, guerreiro e cenario

Revision ID: 7d0f0c1a654a
Revises: dc0c6263929d
Create Date: 2026-09-05 14:49:05.063237
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7d0f0c1a654a"
down_revision: str | None = "dc0c6263929d"
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
        "battle_assets",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=60), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=True),
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
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_battle_assets_uploaded_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_battle_assets")),
        sa.UniqueConstraint("kind", "slug", name="uq_battle_assets_kind_slug"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_battle_assets_kind", "battle_assets", ["kind"], unique=False)
    op.create_index(op.f("ix_battle_assets_public_id"), "battle_assets", ["public_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_battle_assets_public_id"), table_name="battle_assets")
    op.drop_index("ix_battle_assets_kind", table_name="battle_assets")

    op.drop_table("battle_assets")
