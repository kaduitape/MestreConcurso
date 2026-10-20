"""A trava de migração não pode custar o carimbo de versão.

Este arquivo existe por causa de um defeito que ficou verde em produção. A
trava consultiva rodava na mesma conexão que o Alembic ia usar; o SQLAlchemy
abre transação no primeiro comando, o Alembic concluía que a transação era de
outra pessoa e **parava de confirmar qualquer coisa**. Em MySQL o DDL se
auto-confirma, então o schema subiu e o deploy passou; o ``UPDATE
alembic_version`` da última revisão foi descartado. O deploy seguinte repetiu
a migração e morreu com "Duplicate column name".

O que se cobra aqui é o aviso: conexão suja é recusada aos berros, porque
carimbo perdido em silêncio quebra o deploy seguinte, não este.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from app.db.migration_lock import (
    MigrationConnectionBusyError,
    acquire,
    ensure_clean_for_alembic,
    lock_supported,
    release,
)


def test_a_connection_with_an_open_transaction_is_refused() -> None:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            # Um comando qualquer basta: o SQLAlchemy 2 abre a transação sozinho.
            connection.execute(text("SELECT 1"))
            assert connection.in_transaction()

            with pytest.raises(MigrationConnectionBusyError) as erro:
                ensure_clean_for_alembic(connection)

            # A mensagem precisa dizer o que aconteceria, não só que falhou.
            assert "carimbo" in str(erro.value).lower()
    finally:
        engine.dispose()


def test_a_clean_connection_passes() -> None:
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            ensure_clean_for_alembic(connection)  # não levanta
    finally:
        engine.dispose()


def test_the_lock_leaves_no_transaction_behind() -> None:
    """Fora do MySQL não há o que travar — e nada é executado na conexão.

    É o detalhe que conserta o defeito: a conexão continua limpa depois de
    pedir a trava, então o Alembic assume a transação e confirma o carimbo.
    """
    engine = create_engine("sqlite://")
    try:
        with engine.connect() as connection:
            assert acquire(connection) is False
            release(connection)
            assert not connection.in_transaction()
            ensure_clean_for_alembic(connection)
    finally:
        engine.dispose()


def test_only_mysql_has_an_advisory_lock() -> None:
    assert lock_supported("mysql") is True
    assert lock_supported("sqlite") is False
    assert lock_supported("postgresql") is False
