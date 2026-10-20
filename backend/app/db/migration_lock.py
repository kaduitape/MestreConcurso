"""A trava de migração — e a conexão limpa que o Alembic precisa receber.

Duas regras moram aqui, e a segunda existe por causa de um defeito que custou
um deploy inteiro.

**Um alembic por banco.** Em MySQL o DDL não tem rollback: dois
``alembic upgrade head`` simultâneos leem a mesma versão, os dois tentam criar
a mesma tabela, um vence e o outro morre com "already exists" — e a tabela fica
de pé sem o carimbo de versão, num estado que nenhuma revisão descreve. A trava
consultiva impede a corrida.

**A trava não pode tocar na conexão das migrações.** A primeira versão desta
trava rodava ``SELECT GET_LOCK(...)`` na mesma conexão que o Alembic ia usar.
O SQLAlchemy 2 abre transação sozinho no primeiro comando, então o Alembic
recebia uma conexão com transação aberta, concluía que *outra pessoa* era dona
dela e, a partir daí, ``begin_transaction()`` virava um no-op: ele nunca mais
fazia commit. O DDL do MySQL se auto-confirma, então o schema subia; o
``UPDATE alembic_version`` da última revisão ficava pendente e era descartado
no fechamento da conexão. Resultado em produção: o banco com o schema novo e o
carimbo na revisão anterior, o deploy verde, e o deploy **seguinte** morrendo
com "Duplicate column name" ao repetir a migração que já tinha rodado.

Por isso a trava vive numa conexão só dela e ``ensure_clean_for_alembic``
recusa, aos berros, uma conexão que chegue suja. Carimbo perdido em silêncio é
pior que falha: a falha para o deploy, o silêncio quebra o próximo.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

#: Nome da trava consultiva. Qualquer processo que vá migrar pega esta trava
#: antes de olhar a versão do banco.
MIGRATION_LOCK = "mestre_concurso_alembic"

#: Tempo de espera pela trava. Uma migração longa pode segurar o outro processo
#: por um bom tempo, e esperar é exatamente o comportamento certo.
MIGRATION_LOCK_TIMEOUT_SECONDS = 600


class MigrationLockBusyError(RuntimeError):
    """Outro processo segurou a trava além do tempo de espera."""


class MigrationConnectionBusyError(RuntimeError):
    """O Alembic receberia uma conexão com transação já aberta."""


def lock_supported(dialect_name: str) -> bool:
    """Só o MySQL tem trava consultiva aqui; no SQLite dos testes não há o que travar."""
    return dialect_name == "mysql"


def acquire(connection: Connection) -> bool:
    """Pega a trava consultiva nesta conexão.

    A trava é de sessão, não de transação: o commit abaixo encerra a transação
    que o SQLAlchemy abriu para rodar o ``SELECT`` **sem** soltar a trava. Se o
    processo morrer, o MySQL a solta sozinho.
    """
    if not lock_supported(connection.dialect.name):
        return False
    acquired = connection.exec_driver_sql(
        "SELECT GET_LOCK(%s, %s)", (MIGRATION_LOCK, MIGRATION_LOCK_TIMEOUT_SECONDS)
    ).scalar()
    connection.commit()
    if acquired != 1:
        raise MigrationLockBusyError(
            "Outro processo segurou a trava de migração por mais de "
            f"{MIGRATION_LOCK_TIMEOUT_SECONDS}s. Nada foi migrado."
        )
    return True


def release(connection: Connection) -> None:
    if not lock_supported(connection.dialect.name):
        return
    connection.exec_driver_sql("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK,))
    connection.commit()


def ensure_clean_for_alembic(connection: Connection) -> None:
    """Recusa uma conexão com transação aberta antes de configurar o Alembic.

    Com transação aberta por outra pessoa, o Alembic não assume a
    responsabilidade de confirmar nada — e o carimbo de versão da última
    revisão se perde em silêncio. É melhor derrubar o deploy aqui.
    """
    if connection.in_transaction():
        raise MigrationConnectionBusyError(
            "A conexão entregue ao Alembic já tinha transação aberta. Ele não "
            "faria commit do carimbo de versão, e o banco terminaria com o "
            "schema novo carimbado na revisão antiga. Nada foi migrado."
        )
