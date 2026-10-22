"""analista de melhorias

Revision ID: 9de7389084a8
Revises: 8b9f371ddc04
Create Date: 2026-10-22 11:18:49.558366
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "9de7389084a8"
down_revision: str | None = "8b9f371ddc04"
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
        "improvement_detector_settings",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_detail", sa.String(length=500), nullable=True),
        sa.Column("last_found", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_improvement_detector_settings")),
        sa.UniqueConstraint("key", name="uq_improvement_detectors_key"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_improvement_detector_settings_key"),
        "improvement_detector_settings",
        ["key"],
        unique=False,
    )

    op.create_table(
        "improvement_findings",
        sa.Column("detector", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("destination", sa.String(length=20), nullable=False),
        sa.Column("fingerprint", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("proposal", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("evidence", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("target_kind", sa.String(length=30), nullable=True),
        sa.Column("target_public_id", sa.String(length=60), nullable=True),
        sa.Column("measured_waste_cents", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("seen_count", sa.Integer(), nullable=False),
        sa.Column("decided_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(length=500), nullable=True),
        sa.Column("muted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reopened_count", sa.Integer(), nullable=False),
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
            ["decided_by_user_id"],
            ["users.id"],
            name=op.f("fk_improvement_findings_decided_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_improvement_findings")),
        sa.UniqueConstraint("fingerprint", name="uq_improvement_findings_fingerprint"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_improvement_findings_detector",
        "improvement_findings",
        ["detector", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_improvement_findings_public_id"),
        "improvement_findings",
        ["public_id"],
        unique=True,
    )
    op.create_index(
        "ix_improvement_findings_status_severity",
        "improvement_findings",
        ["status", "severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_improvement_findings_target_public_id"),
        "improvement_findings",
        ["target_public_id"],
        unique=False,
    )


def downgrade() -> None:
    # Derrubar a tabela leva os índices dela junto, nos dois dialetos. Soltar
    # índice antes do DROP TABLE só cria a chance de o MySQL recusar um que ele
    # considere necessário a alguma chave estrangeira.
    op.drop_table("improvement_findings")
    op.drop_table("improvement_detector_settings")
