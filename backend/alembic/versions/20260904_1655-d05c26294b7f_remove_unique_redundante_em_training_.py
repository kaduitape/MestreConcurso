"""Remove a unique redundante de training_lessons.public_id

O ``PublicIdMixin`` já garante unicidade por índice único, como em todas as
outras tabelas do projeto. A constraint extra criada pela migração do Estúdio de
Treinamento deixava ``alembic check`` acusando desvio a cada autogenerate.

Corrigido por migração nova, e não editando a anterior, porque a master tem
deploy automático: a de origem pode já ter rodado, e mudá-la deixaria o banco e
o arquivo divergentes em silêncio.

Revision ID: d05c26294b7f
Revises: e5f6a7b8c9d0
Create Date: 2026-09-04 16:55:38.157279
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d05c26294b7f"
down_revision: str | None = "e5f6a7b8c9d0"
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
    with op.batch_alter_table("training_lessons", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("uq_training_lessons_public_id"), type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("training_lessons", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            batch_op.f("uq_training_lessons_public_id"), ["public_id"]
        )
