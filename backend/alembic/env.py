"""Ambiente Alembic com engine assíncrona (mesma URL da aplicação)."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from alembic import context
from app import models  # noqa: F401  (registra todos os modelos no metadata)
from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sqlalchemy_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


#: Nome da trava consultiva no MySQL. Qualquer processo que vá migrar pega
#: esta trava antes de olhar a versão do banco.
MIGRATION_LOCK = "mestre_concurso_alembic"

#: Tempo de espera pela trava. Uma migração longa pode segurar o outro
#: processo por um bom tempo, e esperar é exatamente o comportamento certo.
MIGRATION_LOCK_TIMEOUT_SECONDS = 600


def _acquire_lock(connection: Connection) -> bool:
    """Impede que dois processos migrem o mesmo banco ao mesmo tempo.

    Em MySQL o DDL **não tem rollback**: dois ``alembic upgrade head``
    simultâneos leem a mesma versão, os dois tentam criar a mesma tabela, um
    vence e o outro morre com "already exists" — e a tabela fica de pé sem o
    carimbo de versão, deixando o banco num estado que nenhuma migração
    descreve. Foi exatamente isso que derrubou o deploy de produção quando o
    entrypoint do contêiner e o passo do deploy rodaram juntos.

    A trava é consultiva e vive na sessão: se o processo morrer, o MySQL a
    solta sozinho. Em SQLite (os testes) não há o que travar.
    """
    if connection.dialect.name != "mysql":
        return False
    acquired = connection.exec_driver_sql(
        f"SELECT GET_LOCK('{MIGRATION_LOCK}', {MIGRATION_LOCK_TIMEOUT_SECONDS})"
    ).scalar()
    if acquired != 1:
        raise RuntimeError(
            "Outro processo segurou a trava de migração por mais de "
            f"{MIGRATION_LOCK_TIMEOUT_SECONDS}s. Nada foi migrado."
        )
    return True


def _release_lock(connection: Connection) -> None:
    connection.exec_driver_sql(f"SELECT RELEASE_LOCK('{MIGRATION_LOCK}')")


def do_run_migrations(connection: Connection) -> None:
    locked = _acquire_lock(connection)
    try:
        _run_migrations(connection)
    finally:
        if locked:
            _release_lock(connection)


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.sqlalchemy_url},
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
