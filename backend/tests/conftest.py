"""Fixtures de teste.

Os testes rodam sobre SQLite (aiosqlite) para serem executáveis sem infraestrutura;
os fluxos são os mesmos exercitados em MySQL. As variáveis de ambiente são definidas
antes de qualquer import da aplicação, pois as configurações são carregadas no import.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

_TMP_DB = Path(tempfile.gettempdir()) / "mestre_test.sqlite3"
os.environ.update(
    ENVIRONMENT="test",
    DEBUG="true",
    SECRET_KEY="chave-de-teste-com-tamanho-suficiente-para-hs256-0123456789",
    DATABASE_URL=f"sqlite+aiosqlite:///{_TMP_DB}",
    RATE_LIMIT_ENABLED="false",
    EMAIL_BACKEND="console",
    LOG_LEVEL="WARNING",
    LOG_FORMAT="console",
    ARGON2_TIME_COST="1",
    ARGON2_MEMORY_COST="8192",
    ARGON2_PARALLELISM="1",
    MAX_LOGIN_ATTEMPTS="3",
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import dispose_engine, get_engine, get_session_factory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services import auth as auth_service  # noqa: E402
from app.services import mailer  # noqa: E402
from app.services.email import EmailMessageData  # noqa: E402
from app.services.seed import sync_rbac  # noqa: E402


class CapturingDispatcher:
    """Substitui o envio real de e-mail e guarda as mensagens para inspeção."""

    def __init__(self) -> None:
        self.messages: list[EmailMessageData] = []

    async def dispatch(self, message: EmailMessageData) -> None:
        self.messages.append(message)

    def last_token(self, path: str) -> str:
        """Extrai o token do último link enviado para a rota informada."""
        for message in reversed(self.messages):
            marker = f"/{path}?token="
            if marker in message.text_body:
                return message.text_body.split(marker, 1)[1].split()[0].strip()
        raise AssertionError(f"Nenhum e-mail com link /{path} foi enviado.")


@pytest.fixture
async def app_instance() -> AsyncIterator[Any]:
    _TMP_DB.unlink(missing_ok=True)
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    factory = get_session_factory()
    async with factory() as session:
        await sync_rbac(session)

    application = create_app()
    yield application

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await dispose_engine()
    _TMP_DB.unlink(missing_ok=True)


@pytest.fixture
def emails(monkeypatch: pytest.MonkeyPatch) -> CapturingDispatcher:
    dispatcher = CapturingDispatcher()
    monkeypatch.setattr(mailer, "_dispatcher", dispatcher)
    monkeypatch.setattr(mailer, "get_email_dispatcher", lambda: dispatcher)
    # AuthService importa a função diretamente; o patch precisa alcançar o módulo dele.
    monkeypatch.setattr(auth_service, "get_email_dispatcher", lambda: dispatcher)
    return dispatcher


@pytest.fixture
async def client(app_instance: Any) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(
        transport=transport, base_url="http://testserver", follow_redirects=True
    ) as http_client:
        yield http_client


@pytest.fixture
async def db_session(app_instance: Any) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
