"""Fase 2 - catalogo de concursos, editais e configuracao de IA

Revision ID: ff1ce9f90a98
Revises: b3a4f2805ab9
Create Date: 2026-08-23 15:14:53.992599
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "ff1ce9f90a98"
down_revision: str | None = "b3a4f2805ab9"
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
        "ai_cache_entries",
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("provider_slug", sa.String(length=40), nullable=False),
        sa.Column("model_slug", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("payload", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_cache_entries")),
        sa.UniqueConstraint("fingerprint", name="uq_ai_cache_entries_fingerprint"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_ai_cache_entries_expires_at", "ai_cache_entries", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_ai_cache_entries_feature"), "ai_cache_entries", ["feature"], unique=False
    )
    op.create_index(
        "ix_ai_cache_entries_feature_created_at",
        "ai_cache_entries",
        ["feature", "created_at"],
        unique=False,
    )

    op.create_table(
        "exam_boards",
        sa.Column("slug", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("short_name", sa.String(length=60), nullable=False),
        sa.Column("aliases", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column(
            "description", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_boards")),
        sa.UniqueConstraint("slug", name="uq_exam_boards_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_exam_boards_public_id"), "exam_boards", ["public_id"], unique=True)
    op.create_index(op.f("ix_exam_boards_slug"), "exam_boards", ["slug"], unique=False)

    op.create_table(
        "organizations",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("short_name", sa.String(length=60), nullable=False),
        sa.Column("sphere", sa.String(length=20), nullable=False),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_organizations_public_id"), "organizations", ["public_id"], unique=True)
    op.create_index(op.f("ix_organizations_slug"), "organizations", ["slug"], unique=False)

    op.create_table(
        "subjects",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=140), nullable=False),
        sa.Column("area", sa.String(length=80), nullable=True),
        sa.Column("color_token", sa.String(length=40), nullable=False),
        sa.Column(
            "description", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("slug", name="uq_subjects_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_subjects_public_id"), "subjects", ["public_id"], unique=True)
    op.create_index(op.f("ix_subjects_slug"), "subjects", ["slug"], unique=False)

    op.create_table(
        "ai_providers",
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("organization", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "api_key_encrypted", sa.Text().with_variant(mysql.LONGTEXT(), "mysql"), nullable=True
        ),
        sa.Column("api_key_hint", sa.String(length=32), nullable=True),
        sa.Column("api_key_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("api_key_set_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=20), nullable=True),
        sa.Column("last_test_message", sa.String(length=255), nullable=True),
        sa.Column("settings", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["api_key_set_by_user_id"],
            ["users.id"],
            name=op.f("fk_ai_providers_api_key_set_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_providers")),
        sa.UniqueConstraint("slug", name="uq_ai_providers_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_ai_providers_slug"), "ai_providers", ["slug"], unique=False)

    op.create_table(
        "ai_usage",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("provider_slug", sa.String(length=40), nullable=False),
        sa.Column("model_slug", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_cents", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("cached", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_ai_usage_user_id"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_ai_usage_created_at"), "ai_usage", ["created_at"], unique=False)
    op.create_index(
        "ix_ai_usage_feature_created_at", "ai_usage", ["feature", "created_at"], unique=False
    )
    op.create_index(
        "ix_ai_usage_user_id_created_at", "ai_usage", ["user_id", "created_at"], unique=False
    )

    op.create_table(
        "board_knowledge_entries",
        sa.Column("exam_board_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("entry_key", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("data", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("sample_exams", sa.Integer(), nullable=True),
        sa.Column("sample_questions", sa.Integer(), nullable=True),
        sa.Column("period_start_year", sa.Integer(), nullable=True),
        sa.Column("period_end_year", sa.Integer(), nullable=True),
        sa.Column("provider_slug", sa.String(length=40), nullable=True),
        sa.Column("model_slug", sa.String(length=120), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
            ["exam_board_id"],
            ["exam_boards.id"],
            name=op.f("fk_board_knowledge_entries_exam_board_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("fk_board_knowledge_entries_reviewed_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_board_knowledge_entries_subject_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_board_knowledge_entries")),
        sa.UniqueConstraint(
            "exam_board_id", "kind", "entry_key", name="uq_board_knowledge_entries_board_kind_key"
        ),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_board_knowledge_entries_board_kind",
        "board_knowledge_entries",
        ["exam_board_id", "kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_board_knowledge_entries_exam_board_id"),
        "board_knowledge_entries",
        ["exam_board_id"],
        unique=False,
    )
    op.create_index(
        "ix_board_knowledge_entries_expires_at",
        "board_knowledge_entries",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "competitions",
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("exam_board_id", sa.BigInteger(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("education_level", sa.String(length=20), nullable=True),
        sa.Column("vacancies_total", sa.Integer(), nullable=True),
        sa.Column("salary_max_cents", sa.BigInteger(), nullable=True),
        sa.Column("registration_start", sa.Date(), nullable=True),
        sa.Column("registration_end", sa.Date(), nullable=True),
        sa.Column("exam_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False),
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
            ["exam_board_id"],
            ["exam_boards.id"],
            name=op.f("fk_competitions_exam_board_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_competitions_organization_id"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitions")),
        sa.UniqueConstraint("slug", name="uq_competitions_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_competitions_exam_board_id"), "competitions", ["exam_board_id"], unique=False
    )
    op.create_index(
        "ix_competitions_exam_board_id_year",
        "competitions",
        ["exam_board_id", "year"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competitions_is_published"), "competitions", ["is_published"], unique=False
    )
    op.create_index(
        op.f("ix_competitions_organization_id"), "competitions", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_competitions_public_id"), "competitions", ["public_id"], unique=True)
    op.create_index(op.f("ix_competitions_slug"), "competitions", ["slug"], unique=False)
    op.create_index(
        "ix_competitions_status_exam_date", "competitions", ["status", "exam_date"], unique=False
    )
    op.create_index(op.f("ix_competitions_year"), "competitions", ["year"], unique=False)

    op.create_table(
        "topics",
        sa.Column("subject_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "description", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
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
            ["parent_id"], ["topics.id"], name=op.f("fk_topics_parent_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"], ["subjects.id"], name=op.f("fk_topics_subject_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_topics")),
        sa.UniqueConstraint("subject_id", "slug", name="uq_topics_subject_id_slug"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_topics_path", "topics", ["path"], unique=False)
    op.create_index(op.f("ix_topics_public_id"), "topics", ["public_id"], unique=True)
    op.create_index(op.f("ix_topics_subject_id"), "topics", ["subject_id"], unique=False)
    op.create_index(
        "ix_topics_subject_id_parent_id", "topics", ["subject_id", "parent_id"], unique=False
    )

    op.create_table(
        "ai_models",
        sa.Column("provider_id", sa.BigInteger(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("input_cost_per_1k", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("output_cost_per_1k", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("supports_tools", sa.Boolean(), nullable=False),
        sa.Column("supports_json", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
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
            ["provider_id"],
            ["ai_providers.id"],
            name=op.f("fk_ai_models_provider_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_models")),
        sa.UniqueConstraint("provider_id", "slug", name="uq_ai_models_provider_id_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(
        "ix_ai_models_provider_id_is_active",
        "ai_models",
        ["provider_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "notices",
        sa.Column("competition_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("number", sa.String(length=60), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True),
        sa.Column("extra", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            name=op.f("fk_notices_competition_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_notices_created_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notices")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_notices_competition_id"), "notices", ["competition_id"], unique=False)
    op.create_index(
        "ix_notices_competition_id_kind", "notices", ["competition_id", "kind"], unique=False
    )
    op.create_index(op.f("ix_notices_public_id"), "notices", ["public_id"], unique=True)
    op.create_index("ix_notices_status", "notices", ["status"], unique=False)

    op.create_table(
        "positions",
        sa.Column("competition_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("education_level", sa.String(length=20), nullable=True),
        sa.Column("salary_cents", sa.BigInteger(), nullable=True),
        sa.Column("vacancies", sa.Integer(), nullable=True),
        sa.Column("cr_vacancies", sa.Integer(), nullable=True),
        sa.Column("workload_hours", sa.Integer(), nullable=True),
        sa.Column(
            "requirements", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=True
        ),
        sa.Column("questions_count", sa.Integer(), nullable=True),
        sa.Column("exam_duration_minutes", sa.Integer(), nullable=True),
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
            name=op.f("fk_positions_competition_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_positions")),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_positions_competition_id"), "positions", ["competition_id"], unique=False
    )
    op.create_index(
        "ix_positions_competition_id_name", "positions", ["competition_id", "name"], unique=False
    )
    op.create_index(op.f("ix_positions_public_id"), "positions", ["public_id"], unique=True)

    op.create_table(
        "ai_feature_bindings",
        sa.Column("feature", sa.String(length=60), nullable=False),
        sa.Column("model_id", sa.BigInteger(), nullable=True),
        sa.Column("fallback_model_id", sa.BigInteger(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("temperature", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("cache_ttl_hours", sa.Integer(), nullable=True),
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
            ["fallback_model_id"],
            ["ai_models.id"],
            name=op.f("fk_ai_feature_bindings_fallback_model_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["ai_models.id"],
            name=op.f("fk_ai_feature_bindings_model_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_feature_bindings")),
        sa.UniqueConstraint("feature", name="uq_ai_feature_bindings_feature"),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_ai_feature_bindings_feature"), "ai_feature_bindings", ["feature"], unique=False
    )

    op.create_table(
        "notice_files",
        sa.Column("notice_id", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_notice_files_notice_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            name=op.f("fk_notice_files_uploaded_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notice_files")),
        sa.UniqueConstraint(
            "notice_id", "checksum_sha256", name="uq_notice_files_notice_id_checksum_sha256"
        ),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_notice_files_checksum_sha256"), "notice_files", ["checksum_sha256"], unique=False
    )
    op.create_index(op.f("ix_notice_files_notice_id"), "notice_files", ["notice_id"], unique=False)
    op.create_index(op.f("ix_notice_files_public_id"), "notice_files", ["public_id"], unique=True)
    op.create_index("ix_notice_files_status", "notice_files", ["status"], unique=False)

    op.create_table(
        "position_subjects",
        sa.Column("position_id", sa.BigInteger(), nullable=False),
        sa.Column("subject_id", sa.BigInteger(), nullable=False),
        sa.Column("weight", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("questions_count", sa.Integer(), nullable=True),
        sa.Column("min_score", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("is_eliminatory", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("extra", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
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
            ["position_id"],
            ["positions.id"],
            name=op.f("fk_position_subjects_position_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subject_id"],
            ["subjects.id"],
            name=op.f("fk_position_subjects_subject_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position_subjects")),
        sa.UniqueConstraint(
            "position_id", "subject_id", name="uq_position_subjects_position_id_subject_id"
        ),
        **MYSQL_OPTS,
    )
    op.create_index(
        op.f("ix_position_subjects_position_id"), "position_subjects", ["position_id"], unique=False
    )
    op.create_index(
        op.f("ix_position_subjects_subject_id"), "position_subjects", ["subject_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_position_subjects_subject_id"), "position_subjects")
    op.drop_index(op.f("ix_position_subjects_position_id"), "position_subjects")

    op.drop_table("position_subjects")
    op.drop_index("ix_notice_files_status", "notice_files")
    op.drop_index(op.f("ix_notice_files_public_id"), "notice_files")
    op.drop_index(op.f("ix_notice_files_notice_id"), "notice_files")
    op.drop_index(op.f("ix_notice_files_checksum_sha256"), "notice_files")

    op.drop_table("notice_files")
    op.drop_index(op.f("ix_ai_feature_bindings_feature"), "ai_feature_bindings")

    op.drop_table("ai_feature_bindings")
    op.drop_index(op.f("ix_positions_public_id"), "positions")
    op.drop_index("ix_positions_competition_id_name", "positions")
    op.drop_index(op.f("ix_positions_competition_id"), "positions")

    op.drop_table("positions")
    op.drop_index("ix_notices_status", "notices")
    op.drop_index(op.f("ix_notices_public_id"), "notices")
    op.drop_index("ix_notices_competition_id_kind", "notices")
    op.drop_index(op.f("ix_notices_competition_id"), "notices")

    op.drop_table("notices")
    op.drop_index("ix_ai_models_provider_id_is_active", "ai_models")

    op.drop_table("ai_models")
    op.drop_index("ix_topics_subject_id_parent_id", "topics")
    op.drop_index(op.f("ix_topics_subject_id"), "topics")
    op.drop_index(op.f("ix_topics_public_id"), "topics")
    op.drop_index("ix_topics_path", "topics")

    op.drop_table("topics")
    op.drop_index(op.f("ix_competitions_year"), "competitions")
    op.drop_index("ix_competitions_status_exam_date", "competitions")
    op.drop_index(op.f("ix_competitions_slug"), "competitions")
    op.drop_index(op.f("ix_competitions_public_id"), "competitions")
    op.drop_index(op.f("ix_competitions_organization_id"), "competitions")
    op.drop_index(op.f("ix_competitions_is_published"), "competitions")
    op.drop_index("ix_competitions_exam_board_id_year", "competitions")
    op.drop_index(op.f("ix_competitions_exam_board_id"), "competitions")

    op.drop_table("competitions")
    op.drop_index("ix_board_knowledge_entries_expires_at", "board_knowledge_entries")
    op.drop_index(op.f("ix_board_knowledge_entries_exam_board_id"), "board_knowledge_entries")
    op.drop_index("ix_board_knowledge_entries_board_kind", "board_knowledge_entries")

    op.drop_table("board_knowledge_entries")
    op.drop_index("ix_ai_usage_user_id_created_at", "ai_usage")
    op.drop_index("ix_ai_usage_feature_created_at", "ai_usage")
    op.drop_index(op.f("ix_ai_usage_created_at"), "ai_usage")

    op.drop_table("ai_usage")
    op.drop_index(op.f("ix_ai_providers_slug"), "ai_providers")

    op.drop_table("ai_providers")
    op.drop_index(op.f("ix_subjects_slug"), "subjects")
    op.drop_index(op.f("ix_subjects_public_id"), "subjects")

    op.drop_table("subjects")
    op.drop_index(op.f("ix_organizations_slug"), "organizations")
    op.drop_index(op.f("ix_organizations_public_id"), "organizations")

    op.drop_table("organizations")
    op.drop_index(op.f("ix_exam_boards_slug"), "exam_boards")
    op.drop_index(op.f("ix_exam_boards_public_id"), "exam_boards")

    op.drop_table("exam_boards")
    op.drop_index("ix_ai_cache_entries_feature_created_at", "ai_cache_entries")
    op.drop_index(op.f("ix_ai_cache_entries_feature"), "ai_cache_entries")
    op.drop_index("ix_ai_cache_entries_expires_at", "ai_cache_entries")

    op.drop_table("ai_cache_entries")
