"""vinculo de conteudo ao catalogo e concurso principal

Revision ID: 81ed603d085c
Revises: fea78a95bd3e
Create Date: 2026-10-20 12:24:40.933860

Migração **aditiva**. Nada é apagado e nada é obrigatório:

* ``training_lessons`` e ``mind_maps`` ganham ``subject_id``/``topic_id``
  anuláveis. Aula antiga continua abrindo exatamente como hoje — o vínculo é
  preenchido depois, com confirmação humana no painel, porque casar no chute
  mandaria o conteúdo para o tópico errado.
* ``profiles`` ganha o concurso principal, que é o que dá sentido à contagem
  regressiva do painel.
* ``competitions`` ganha o estado **editorial**, que é outro eixo que o
  ``status`` já existente: aquele descreve o concurso no mundo, este descreve
  o nosso registro dele. O valor inicial é derivado do ``is_published`` que já
  está em produção, para nenhuma ficha publicada voltar para rascunho.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "81ed603d085c"
down_revision: str | None = "fea78a95bd3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Colunas e chaves estrangeiras em batch: o SQLite dos testes não altera
    # constraint fora dele. Os índices ficam de fora, que no MySQL recriar a
    # tabela à toa sai caro.
    with op.batch_alter_table("competitions", schema=None) as batch_op:
        # O server_default é obrigatório aqui: a coluna é NOT NULL e a tabela
        # já tem linhas em produção. Sem ele o MySQL recusaria o ALTER.
        batch_op.add_column(
            sa.Column(
                "editorial_status",
                sa.String(length=20),
                nullable=False,
                server_default="DRAFT",
            )
        )
    op.create_index(
        op.f("ix_competitions_editorial_status"),
        "competitions",
        ["editorial_status"],
        unique=False,
    )
    # Ficha que já estava publicada continua publicada. Derivar do estado real
    # evita que a migração esconda concursos que os alunos já enxergavam.
    op.execute(
        sa.text("UPDATE competitions SET editorial_status = 'PUBLISHED' WHERE is_published = 1")
    )
    # O default existia só para o ALTER encontrar as linhas antigas preenchidas.
    # Quem decide o estado inicial de um concurso novo é a aplicação.
    with op.batch_alter_table("competitions", schema=None) as batch_op:
        batch_op.alter_column(
            "editorial_status", existing_type=sa.String(length=20), server_default=None
        )

    with op.batch_alter_table("mind_maps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("topic_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_mind_maps_topic_id"), "topics", ["topic_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index(op.f("ix_mind_maps_subject_id"), "mind_maps", ["subject_id"], unique=False)
    op.create_index(op.f("ix_mind_maps_topic_id"), "mind_maps", ["topic_id"], unique=False)

    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("primary_competition_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_profiles_primary_competition_id"),
            "competitions",
            ["primary_competition_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        op.f("ix_profiles_primary_competition_id"),
        "profiles",
        ["primary_competition_id"],
        unique=False,
    )

    with op.batch_alter_table("training_lessons", schema=None) as batch_op:
        batch_op.add_column(sa.Column("subject_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("topic_id", sa.BigInteger(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_training_lessons_subject_id"),
            "subjects",
            ["subject_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_training_lessons_topic_id"),
            "topics",
            ["topic_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        op.f("ix_training_lessons_subject_id"), "training_lessons", ["subject_id"], unique=False
    )
    op.create_index(
        op.f("ix_training_lessons_topic_id"), "training_lessons", ["topic_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_training_lessons_topic_id"), table_name="training_lessons")
    op.drop_index(op.f("ix_training_lessons_subject_id"), table_name="training_lessons")
    with op.batch_alter_table("training_lessons", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_training_lessons_topic_id"), type_="foreignkey")
        batch_op.drop_constraint(batch_op.f("fk_training_lessons_subject_id"), type_="foreignkey")
        batch_op.drop_column("topic_id")
        batch_op.drop_column("subject_id")

    op.drop_index(op.f("ix_profiles_primary_competition_id"), table_name="profiles")
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_profiles_primary_competition_id"), type_="foreignkey"
        )
        batch_op.drop_column("primary_competition_id")

    op.drop_index(op.f("ix_mind_maps_topic_id"), table_name="mind_maps")
    op.drop_index(op.f("ix_mind_maps_subject_id"), table_name="mind_maps")
    with op.batch_alter_table("mind_maps", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_mind_maps_topic_id"), type_="foreignkey")
        batch_op.drop_column("topic_id")

    op.drop_index(op.f("ix_competitions_editorial_status"), table_name="competitions")
    with op.batch_alter_table("competitions", schema=None) as batch_op:
        batch_op.drop_column("editorial_status")
