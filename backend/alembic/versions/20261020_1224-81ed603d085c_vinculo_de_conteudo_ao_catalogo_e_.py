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
from typing import Any

import sqlalchemy as sa

from alembic import op

revision: str = "81ed603d085c"
down_revision: str | None = "fea78a95bd3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------- #
# Reparo de carimbo perdido
#
# Esta migração rodou **inteira** em produção e o carimbo de versão se perdeu.
# A trava de migração executava o ``GET_LOCK`` na mesma conexão que o Alembic
# ia usar; o SQLAlchemy abre transação no primeiro comando, o Alembic concluía
# que a transação era de outra pessoa e parava de confirmar qualquer coisa. Em
# MySQL o DDL se auto-confirma, então o schema subiu e o deploy ficou verde; o
# ``UPDATE alembic_version`` foi descartado ao fechar a conexão. O deploy
# seguinte repetiu esta revisão e morreu com "Duplicate column name".
#
# A causa está corrigida em ``app/db/migration_lock.py``: a trava tem conexão
# própria e uma conexão suja é recusada aos berros, em vez de virar um carimbo
# perdido em silêncio. O que sobra aqui é o conserto — a subida pula o que já
# existe, para o banco machucado alcançar a versão certa.
# --------------------------------------------------------------------------- #
def _columns(table: str) -> dict[str, dict[str, Any]]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return {}
    return {column["name"]: column for column in inspector.get_columns(table)}


def _indexes(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return set()
    return {index["name"] for index in inspector.get_indexes(table) if index["name"]}


def _has_foreign_key(table: str, column: str) -> bool:
    """Procura pela coluna, não pelo nome.

    O nome da constraint não é confiável para esta checagem: o SQLite nem
    sempre devolve um, e dois dialetos nomeiam a chave de formas diferentes.
    A coluna é o que importa.
    """
    inspector = sa.inspect(op.get_bind())
    if table not in inspector.get_table_names():
        return False
    return any(
        column in (fk.get("constrained_columns") or []) for fk in inspector.get_foreign_keys(table)
    )


def _upgrade_competitions() -> None:
    if "editorial_status" not in _columns("competitions"):
        # Colunas em batch: o SQLite dos testes não altera constraint fora
        # dele. Os índices ficam de fora, que no MySQL recriar a tabela à toa
        # sai caro.
        with op.batch_alter_table("competitions", schema=None) as batch_op:
            # O server_default é obrigatório aqui: a coluna é NOT NULL e a
            # tabela já tem linhas em produção. Sem ele o MySQL recusaria o
            # ALTER.
            batch_op.add_column(
                sa.Column(
                    "editorial_status",
                    sa.String(length=20),
                    nullable=False,
                    server_default="DRAFT",
                )
            )

    if op.f("ix_competitions_editorial_status") not in _indexes("competitions"):
        op.create_index(
            op.f("ix_competitions_editorial_status"),
            "competitions",
            ["editorial_status"],
            unique=False,
        )

    # Ficha que já estava publicada continua publicada. Derivar do estado real
    # evita que a migração esconda concursos que os alunos já enxergavam. O
    # ``editorial_status = 'DRAFT'`` limita o preenchimento às linhas que
    # ninguém decidiu ainda: numa segunda passada, quem já foi arquivado ou
    # publicado à mão fica como está.
    op.execute(
        sa.text(
            "UPDATE competitions SET editorial_status = 'PUBLISHED' "
            "WHERE is_published = 1 AND editorial_status = 'DRAFT'"
        )
    )

    coluna = _columns("competitions").get("editorial_status", {})
    if coluna.get("default") is not None:
        # O default existia só para o ALTER encontrar as linhas antigas
        # preenchidas. Quem decide o estado inicial de um concurso novo é a
        # aplicação.
        with op.batch_alter_table("competitions", schema=None) as batch_op:
            batch_op.alter_column(
                "editorial_status", existing_type=sa.String(length=20), server_default=None
            )


def _upgrade_mind_maps() -> None:
    if "topic_id" not in _columns("mind_maps"):
        with op.batch_alter_table("mind_maps", schema=None) as batch_op:
            batch_op.add_column(sa.Column("topic_id", sa.BigInteger(), nullable=True))
            batch_op.create_foreign_key(
                batch_op.f("fk_mind_maps_topic_id"),
                "topics",
                ["topic_id"],
                ["id"],
                ondelete="SET NULL",
            )
    elif not _has_foreign_key("mind_maps", "topic_id"):
        with op.batch_alter_table("mind_maps", schema=None) as batch_op:
            batch_op.create_foreign_key(
                batch_op.f("fk_mind_maps_topic_id"),
                "topics",
                ["topic_id"],
                ["id"],
                ondelete="SET NULL",
            )

    indexes = _indexes("mind_maps")
    if op.f("ix_mind_maps_subject_id") not in indexes:
        op.create_index(op.f("ix_mind_maps_subject_id"), "mind_maps", ["subject_id"], unique=False)
    if op.f("ix_mind_maps_topic_id") not in indexes:
        op.create_index(op.f("ix_mind_maps_topic_id"), "mind_maps", ["topic_id"], unique=False)


def _upgrade_profiles() -> None:
    if "primary_competition_id" not in _columns("profiles"):
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.add_column(sa.Column("primary_competition_id", sa.BigInteger(), nullable=True))
            batch_op.create_foreign_key(
                batch_op.f("fk_profiles_primary_competition_id"),
                "competitions",
                ["primary_competition_id"],
                ["id"],
                ondelete="SET NULL",
            )
    elif not _has_foreign_key("profiles", "primary_competition_id"):
        with op.batch_alter_table("profiles", schema=None) as batch_op:
            batch_op.create_foreign_key(
                batch_op.f("fk_profiles_primary_competition_id"),
                "competitions",
                ["primary_competition_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if op.f("ix_profiles_primary_competition_id") not in _indexes("profiles"):
        op.create_index(
            op.f("ix_profiles_primary_competition_id"),
            "profiles",
            ["primary_competition_id"],
            unique=False,
        )


def _upgrade_training_lessons() -> None:
    colunas = _columns("training_lessons")
    faltando = [nome for nome in ("subject_id", "topic_id") if nome not in colunas]
    if faltando:
        with op.batch_alter_table("training_lessons", schema=None) as batch_op:
            for nome in faltando:
                batch_op.add_column(sa.Column(nome, sa.BigInteger(), nullable=True))
            if "subject_id" in faltando:
                batch_op.create_foreign_key(
                    batch_op.f("fk_training_lessons_subject_id"),
                    "subjects",
                    ["subject_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
            if "topic_id" in faltando:
                batch_op.create_foreign_key(
                    batch_op.f("fk_training_lessons_topic_id"),
                    "topics",
                    ["topic_id"],
                    ["id"],
                    ondelete="SET NULL",
                )

    for nome, alvo in (("subject_id", "subjects"), ("topic_id", "topics")):
        if nome in faltando or _has_foreign_key("training_lessons", nome):
            continue
        with op.batch_alter_table("training_lessons", schema=None) as batch_op:
            batch_op.create_foreign_key(
                batch_op.f(f"fk_training_lessons_{nome}"),
                alvo,
                [nome],
                ["id"],
                ondelete="SET NULL",
            )

    indexes = _indexes("training_lessons")
    if op.f("ix_training_lessons_subject_id") not in indexes:
        op.create_index(
            op.f("ix_training_lessons_subject_id"), "training_lessons", ["subject_id"], unique=False
        )
    if op.f("ix_training_lessons_topic_id") not in indexes:
        op.create_index(
            op.f("ix_training_lessons_topic_id"), "training_lessons", ["topic_id"], unique=False
        )


def upgrade() -> None:
    _upgrade_competitions()
    _upgrade_mind_maps()
    _upgrade_profiles()
    _upgrade_training_lessons()


def _recreates_tables() -> bool:
    """O SQLite não altera constraint: o ``batch_alter_table`` recria a tabela."""
    return op.get_bind().dialect.name == "sqlite"


def _drop_index_if_present(table: str, name: str) -> None:
    if name in _indexes(table):
        op.drop_index(name, table_name=table)


# A ordem da descida depende do dialeto, e os dois erros são reais:
#
# * onde a tabela é **recriada** (SQLite), o índice precisa sair **antes** — o
#   batch tentaria recriá-lo sobre uma coluna que já não existe
#   ("no such column: topic_id");
# * onde a tabela é alterada **no lugar** (MySQL), o índice precisa sair
#   **depois** — enquanto a chave estrangeira existe ele não pode ser removido
#   ("needed in a foreign key constraint"), e quando a coluna cai ele cai junto.
#
# Por isso a remoção aparece nas duas pontas, sempre condicional: o que já
# desapareceu não é removido de novo.
def downgrade() -> None:
    recria = _recreates_tables()

    if recria:
        _drop_index_if_present("training_lessons", op.f("ix_training_lessons_topic_id"))
        _drop_index_if_present("training_lessons", op.f("ix_training_lessons_subject_id"))
    with op.batch_alter_table("training_lessons", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_training_lessons_topic_id"), type_="foreignkey")
        batch_op.drop_constraint(batch_op.f("fk_training_lessons_subject_id"), type_="foreignkey")
        batch_op.drop_column("topic_id")
        batch_op.drop_column("subject_id")
    _drop_index_if_present("training_lessons", op.f("ix_training_lessons_topic_id"))
    _drop_index_if_present("training_lessons", op.f("ix_training_lessons_subject_id"))

    if recria:
        _drop_index_if_present("profiles", op.f("ix_profiles_primary_competition_id"))
    with op.batch_alter_table("profiles", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_profiles_primary_competition_id"), type_="foreignkey"
        )
        batch_op.drop_column("primary_competition_id")
    _drop_index_if_present("profiles", op.f("ix_profiles_primary_competition_id"))

    if recria:
        _drop_index_if_present("mind_maps", op.f("ix_mind_maps_topic_id"))
        _drop_index_if_present("mind_maps", op.f("ix_mind_maps_subject_id"))
    with op.batch_alter_table("mind_maps", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_mind_maps_topic_id"), type_="foreignkey")
        batch_op.drop_column("topic_id")
    _drop_index_if_present("mind_maps", op.f("ix_mind_maps_topic_id"))
    # O índice de subject_id é desta revisão, mas a coluna não: ela continua de
    # pé com a chave estrangeira dela. No MySQL é este índice que sustenta a
    # chave, e removê-lo é impossível ("needed in a foreign key constraint").
    # Deixar um índice a mais é inofensivo; impedir a volta não é.
    if not _has_foreign_key("mind_maps", "subject_id"):
        _drop_index_if_present("mind_maps", op.f("ix_mind_maps_subject_id"))

    if recria:
        _drop_index_if_present("competitions", op.f("ix_competitions_editorial_status"))
    with op.batch_alter_table("competitions", schema=None) as batch_op:
        batch_op.drop_column("editorial_status")
    _drop_index_if_present("competitions", op.f("ix_competitions_editorial_status"))
