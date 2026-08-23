"""Fase 1 - fundacao: identidade, acesso, auditoria e LGPD

Revision ID: b3a4f2805ab9
Revises:
Create Date: 2026-08-23 14:14:46.003996
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "b3a4f2805ab9"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Opções aplicadas somente no MySQL; ignoradas pelos demais dialetos (SQLite nos testes).
# SQLite (usado nos testes) só auto-incrementa colunas INTEGER.
BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

MYSQL_OPTS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("resource", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("slug", name="uq_permissions_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_permissions_slug"), "permissions", ["slug"], unique=False)

    op.create_table(
        "roles",
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("slug", name="uq_roles_slug"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_roles_slug"), "roles", ["slug"], unique=False)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name="uq_users_email"),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_public_id"), "users", ["public_id"], unique=True)
    op.create_index(op.f("ix_users_status"), "users", ["status"], unique=False)
    op.create_index("ix_users_status_created_at", "users", ["status", "created_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("actor_user_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("actor_ip", sa.String(length=45), nullable=True),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("meta", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(
        "ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"], unique=False
    )
    op.create_index(
        "ix_audit_logs_actor_user_id_created_at",
        "audit_logs",
        ["actor_user_id", "created_at"],
        unique=False,
    )
    op.create_index(op.f("ix_audit_logs_created_at"), "audit_logs", ["created_at"], unique=False)
    op.create_index(
        "ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"], unique=False
    )

    op.create_table(
        "auth_tokens",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=24), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=45), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_auth_tokens_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_tokens")),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_auth_tokens_expires_at", "auth_tokens", ["expires_at"], unique=False)
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"], unique=False)
    op.create_index("ix_auth_tokens_user_id_type", "auth_tokens", ["user_id", "type"], unique=False)

    op.create_table(
        "consent_logs",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", BIGINT_PK, autoincrement=True, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_consent_logs_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consent_logs")),
        **MYSQL_OPTS,
    )
    op.create_index(op.f("ix_consent_logs_user_id"), "consent_logs", ["user_id"], unique=False)
    op.create_index(
        "ix_consent_logs_user_id_kind",
        "consent_logs",
        ["user_id", "kind", "created_at"],
        unique=False,
    )

    op.create_table(
        "profiles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=10), nullable=False),
        sa.Column("theme", sa.String(length=10), nullable=False),
        sa.Column("study_goal", sa.String(length=255), nullable=True),
        sa.Column("bio", sa.String(length=500), nullable=True),
        sa.Column("preferences", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False),
        sa.Column("onboarding_completed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_profiles_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_profiles_user_id")),
        **MYSQL_OPTS,
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_role_permissions_role_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
        **MYSQL_OPTS,
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("granted_by_user_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_user_id"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
        **MYSQL_OPTS,
    )
    op.create_table(
        "user_sessions",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", sa.String(length=26), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=60), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_user_sessions_user_id"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("refresh_token_hash", name="uq_user_sessions_refresh_token_hash"),
        **MYSQL_OPTS,
    )
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)
    op.create_index("ix_user_sessions_family_id", "user_sessions", ["family_id"], unique=False)
    op.create_index(op.f("ix_user_sessions_public_id"), "user_sessions", ["public_id"], unique=True)
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.create_index(
        "ix_user_sessions_user_id_revoked_at",
        "user_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_sessions_user_id_revoked_at", "user_sessions")
    op.drop_index(op.f("ix_user_sessions_user_id"), "user_sessions")
    op.drop_index(op.f("ix_user_sessions_public_id"), "user_sessions")
    op.drop_index("ix_user_sessions_family_id", "user_sessions")
    op.drop_index("ix_user_sessions_expires_at", "user_sessions")

    op.drop_table("user_sessions")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("profiles")
    op.drop_index("ix_consent_logs_user_id_kind", "consent_logs")
    op.drop_index(op.f("ix_consent_logs_user_id"), "consent_logs")

    op.drop_table("consent_logs")
    op.drop_index("ix_auth_tokens_user_id_type", "auth_tokens")
    op.drop_index(op.f("ix_auth_tokens_user_id"), "auth_tokens")
    op.drop_index("ix_auth_tokens_expires_at", "auth_tokens")

    op.drop_table("auth_tokens")
    op.drop_index("ix_audit_logs_resource", "audit_logs")
    op.drop_index(op.f("ix_audit_logs_created_at"), "audit_logs")
    op.drop_index("ix_audit_logs_actor_user_id_created_at", "audit_logs")
    op.drop_index("ix_audit_logs_action_created_at", "audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), "audit_logs")

    op.drop_table("audit_logs")
    op.drop_index("ix_users_status_created_at", "users")
    op.drop_index(op.f("ix_users_status"), "users")
    op.drop_index(op.f("ix_users_public_id"), "users")
    op.drop_index(op.f("ix_users_email"), "users")

    op.drop_table("users")
    op.drop_index(op.f("ix_roles_slug"), "roles")

    op.drop_table("roles")
    op.drop_index(op.f("ix_permissions_slug"), "permissions")

    op.drop_table("permissions")
