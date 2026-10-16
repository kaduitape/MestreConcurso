"""Narracao do Estudio de Treinamento

Revision ID: 05598f0ab8c9
Revises: 7d0f0c1a654a
Create Date: 2026-10-15 16:53:30.012767
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "05598f0ab8c9"
down_revision: str | None = "7d0f0c1a654a"
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


# --------------------------------------------------------------------------- #
# Reparo de meia-aplicação
#
# Esta migração chegou a rodar duas vezes em paralelo em produção (o entrypoint
# do contêiner e o passo do deploy disparavam `alembic upgrade head` juntos).
# Em MySQL o DDL não tem rollback: a tabela foi criada, o processo perdedor
# morreu com "already exists" e a versão nunca foi carimbada — o banco ficou num
# estado que nenhuma revisão descreve.
#
# A corrida está corrigida na origem (trava consultiva em `alembic/env.py` e um
# único ponto de migração no deploy). O que sobra aqui é o conserto: a subida
# pula o que já existe, para que o banco machucado alcance a versão certa.
# --------------------------------------------------------------------------- #
def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table)}


def _existing_indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table)}


def upgrade() -> None:
    if "training_narrations" not in _existing_tables():
        _create_narrations_table()

    indexes = _existing_indexes("training_narrations")
    if op.f("ix_training_narrations_checksum") not in indexes:
        op.create_index(
            op.f("ix_training_narrations_checksum"),
            "training_narrations",
            ["checksum"],
            unique=False,
        )
    if "ix_training_narrations_lesson_scene" not in indexes:
        op.create_index(
            "ix_training_narrations_lesson_scene",
            "training_narrations",
            ["lesson_id", "scene_id"],
            unique=False,
        )
    if op.f("ix_training_narrations_public_id") not in indexes:
        op.create_index(
            op.f("ix_training_narrations_public_id"),
            "training_narrations",
            ["public_id"],
            unique=True,
        )

    if "options" not in _existing_columns("ai_feature_bindings"):
        with op.batch_alter_table("ai_feature_bindings", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("options", sa.JSON().with_variant(mysql.JSON(), "mysql"), nullable=False)
            )

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.alter_column(
            "text_coverage", existing_type=sa.FLOAT(), type_=sa.Double(), existing_nullable=True
        )

    if "narration_voice" not in _existing_columns("training_lessons"):
        with op.batch_alter_table("training_lessons", schema=None) as batch_op:
            batch_op.add_column(sa.Column("narration_voice", sa.String(length=40), nullable=True))


def _create_narrations_table() -> None:
    op.create_table(
        "training_narrations",
        sa.Column("lesson_id", sa.BigInteger(), nullable=False),
        sa.Column("scene_id", sa.Integer(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("direction", sa.Text().with_variant(mysql.MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=60), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("voice", sa.String(length=40), nullable=False),
        sa.Column("model_slug", sa.String(length=120), nullable=False),
        sa.Column("provider_slug", sa.String(length=40), nullable=False),
        sa.Column("characters", sa.Integer(), nullable=False),
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
            ["lesson_id"],
            ["training_lessons.id"],
            name=op.f("fk_training_narrations_lesson_id"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_narrations")),
        sa.UniqueConstraint("checksum", name="uq_training_narrations_checksum"),
        **MYSQL_OPTS,
    )


def downgrade() -> None:
    with op.batch_alter_table("training_lessons", schema=None) as batch_op:
        batch_op.drop_column("narration_voice")

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.alter_column(
            "text_coverage", existing_type=sa.Double(), type_=sa.FLOAT(), existing_nullable=True
        )

    with op.batch_alter_table("ai_feature_bindings", schema=None) as batch_op:
        batch_op.drop_column("options")

    op.drop_index(op.f("ix_training_narrations_public_id"), table_name="training_narrations")
    op.drop_index("ix_training_narrations_lesson_scene", table_name="training_narrations")
    op.drop_index(op.f("ix_training_narrations_checksum"), table_name="training_narrations")

    op.drop_table("training_narrations")
