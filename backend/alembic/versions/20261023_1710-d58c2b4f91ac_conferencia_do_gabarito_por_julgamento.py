"""conferencia do gabarito por julgamento tipado

Revision ID: d58c2b4f91ac
Revises: c4a1f2e97d3b
Create Date: 2026-10-23 17:10:44.512903
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d58c2b4f91ac"
down_revision: str | None = "c4a1f2e97d3b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Coluna anulável de propósito: ``NULL`` quer dizer **não conferido**, que é
    # diferente de zero. A fila de revisão ordena por ela, e é por isso que o
    # número não ficou dentro do JSON de sugestão.
    op.add_column("questions", sa.Column("answer_key_support", sa.Numeric(4, 3), nullable=True))
    op.create_index(
        "ix_questions_origin_support",
        "questions",
        ["origin", "answer_key_support"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_questions_origin_support", table_name="questions")
    op.drop_column("questions", "answer_key_support")
