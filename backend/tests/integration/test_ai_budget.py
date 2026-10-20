"""Medição e teto de gasto com IA, ponta a ponta.

Dois comportamentos são cobrados aqui com mais insistência que os outros:

*Toda chamada é contada.* Antes desta camada a tabela ``ai_usage`` existia e
ninguém escrevia nela — o painel de custo reportava zero desde sempre.

*O teto corta de verdade.* Um limite que não interrompe nada é só um número
bonito na tela.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.models.ai import AIUsage
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin, create_user
from tests.fake_ai import FakeProvider

SCRIPT = {
    "objectives": ["Objetivo"],
    "scenes": [
        {"id": 1, "type": "intro", "narration": "Uma frase de abertura da aula.", "duration": 10}
    ],
}


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=SCRIPT)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _generate_lesson(
    client: AsyncClient, admin: RegisteredUser, *, topic: str = "Crase"
) -> int:
    """Gera uma aula. O tópico varia entre chamadas de propósito: prompt igual
    bate no cache, não chama o provedor e, por isso, não gasta nem é barrado."""
    created = await client.post(
        "/api/v1/admin/training",
        headers=admin.auth_header,
        json={
            "subject": "Língua Portuguesa",
            "topic": topic,
            "character_name": "Mestre Arcanus",
            "level": "INTERMEDIARIO",
            "style": "AULA",
            "target_duration_minutes": 10,
            "research_before_generate": False,
        },
    )
    assert created.status_code == 201, created.text
    public_id = created.json()["public_id"]
    response = await client.post(
        f"/api/v1/admin/training/{public_id}/generate", headers=admin.auth_header
    )
    return response.status_code


async def _set_price(session: AsyncSession, *, entrada: str, saida: str) -> None:
    from app.models.ai import AIModel

    model = (
        await session.execute(select(AIModel).where(AIModel.slug == "gpt-4o-mini"))
    ).scalar_one()
    model.input_cost_per_1k = Decimal(entrada)
    model.output_cost_per_1k = Decimal(saida)
    await session.commit()


# --------------------------------------------------------------------------- #
# Medição
# --------------------------------------------------------------------------- #
async def test_every_ai_call_is_recorded(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    db_session: AsyncSession,
) -> None:
    """A tabela existia e ninguém escrevia nela. Agora escreve."""
    admin = await create_admin(client, emails, email="orc1@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))

    assert await _generate_lesson(client, admin) == 200

    rows = (await db_session.execute(select(AIUsage))).scalars().all()
    assert len(rows) == 1
    registro = rows[0]
    assert registro.feature == "training.script"
    assert registro.model_slug == "gpt-4o-mini"
    assert registro.input_tokens == 1200
    assert registro.output_tokens == 400
    assert registro.status == "SUCCESS"


async def test_the_cost_comes_from_the_registered_price(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    db_session: AsyncSession,
) -> None:
    admin = await create_admin(client, emails, email="orc2@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    await _set_price(db_session, entrada="0.15", saida="0.60")

    await _generate_lesson(client, admin)

    registro = (await db_session.execute(select(AIUsage))).scalars().one()
    # 1,2k * 0,15 + 0,4k * 0,60 = 0,18 + 0,24 = 0,42 centavos
    assert registro.cost_cents == Decimal("0.420000")


async def test_a_model_without_a_price_is_flagged_not_counted_as_free(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
) -> None:
    """Somar desconhecido como zero faria o teto parecer respeitado."""
    admin = await create_admin(client, emails, email="orc3@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))

    await _generate_lesson(client, admin)

    resumo = await client.get("/api/v1/admin/ai/budget", headers=admin.auth_header)
    assert resumo.status_code == 200, resumo.text
    body = resumo.json()
    assert body["calls_month"] == 1
    assert body["is_complete"] is False
    assert "gpt-4o-mini" in body["models_without_price"]


async def test_a_provider_error_is_recorded_too(
    client: AsyncClient,
    emails: CapturingDispatcher,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
) -> None:
    """Uma sequência de falhas caras some da conta se só o sucesso for contado."""

    class ProvedorQueFalha(FakeProvider):
        async def complete(self, request: object) -> object:  # type: ignore[override]
            raise RuntimeError("provedor fora do ar")

    provider = ProvedorQueFalha()

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="orc4@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))

    # O erro do provedor sobe inteiro; o que importa é que a medição
    # aconteceu ANTES de ele subir.
    with pytest.raises(RuntimeError):
        await _generate_lesson(client, admin)

    registro = (await db_session.execute(select(AIUsage))).scalars().one()
    assert registro.status == "ERROR"
    assert registro.error_code == "RuntimeError"


# --------------------------------------------------------------------------- #
# O teto
# --------------------------------------------------------------------------- #
async def test_the_ceiling_starts_off_and_measuring_still_happens(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="orc5@exemplo.com.br")

    resumo = await client.get("/api/v1/admin/ai/budget", headers=admin.auth_header)

    assert resumo.status_code == 200
    assert resumo.json()["is_enabled"] is False
    assert Decimal(resumo.json()["monthly_limit_cents"]) == Decimal("0")


async def test_the_limits_are_configurable_not_hardcoded(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="orc6@exemplo.com.br")

    salvo = await client.put(
        "/api/v1/admin/ai/budget",
        headers=admin.auth_header,
        json={
            "is_enabled": True,
            "monthly_limit_cents": "5000",
            "per_run_limit_cents": "100",
        },
    )

    assert salvo.status_code == 200, salvo.text
    assert salvo.json()["is_enabled"] is True
    assert Decimal(salvo.json()["monthly_limit_cents"]) == Decimal("5000")


async def test_the_ceiling_actually_cuts_the_next_call(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    db_session: AsyncSession,
) -> None:
    """Um limite que não interrompe nada é só um número bonito na tela."""
    admin = await create_admin(client, emails, email="orc7@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    await _set_price(db_session, entrada="0.15", saida="0.60")

    # Teto baixíssimo: a primeira chamada já o estoura.
    await client.put(
        "/api/v1/admin/ai/budget",
        headers=admin.auth_header,
        json={
            "is_enabled": True,
            "monthly_limit_cents": "0.1",
            "per_run_limit_cents": "0",
        },
    )

    primeira = await _generate_lesson(client, admin, topic="Crase")
    assert primeira == 200, "a primeira passa: o custo só é conhecido depois dela"
    chamadas_antes = len(fake_provider.completion_calls)

    segunda = await _generate_lesson(client, admin, topic="Regência verbal")

    assert segunda == 429, "a seguinte tem que ser barrada"
    assert len(fake_provider.completion_calls) == chamadas_antes, (
        "o corte precisa acontecer ANTES de gastar"
    )


async def test_turning_the_ceiling_off_releases_again(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    db_session: AsyncSession,
) -> None:
    admin = await create_admin(client, emails, email="orc8@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    await _set_price(db_session, entrada="0.15", saida="0.60")
    await client.put(
        "/api/v1/admin/ai/budget",
        headers=admin.auth_header,
        json={"is_enabled": True, "monthly_limit_cents": "0.1", "per_run_limit_cents": "0"},
    )
    await _generate_lesson(client, admin, topic="Crase")
    assert await _generate_lesson(client, admin, topic="Regência verbal") == 429

    await client.put(
        "/api/v1/admin/ai/budget",
        headers=admin.auth_header,
        json={"is_enabled": False, "monthly_limit_cents": "0.1", "per_run_limit_cents": "0"},
    )

    assert await _generate_lesson(client, admin, topic="Concordância") == 200


async def test_a_student_cannot_see_or_change_the_budget(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.orc@exemplo.com.br")

    assert (
        await client.get("/api/v1/admin/ai/budget", headers=student.auth_header)
    ).status_code == 403
    assert (
        await client.put(
            "/api/v1/admin/ai/budget",
            headers=student.auth_header,
            json={"is_enabled": True, "monthly_limit_cents": "1", "per_run_limit_cents": "1"},
        )
    ).status_code == 403


async def test_the_usage_survives_a_failure_of_the_caller(
    client: AsyncClient,
    emails: CapturingDispatcher,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
) -> None:
    """O token foi gasto mesmo que a funcionalidade tenha falhado depois."""
    provider = FakeProvider(raw_completion='{"sem": "cenas"}')

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="orc9@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))

    status = await _generate_lesson(client, admin)
    assert status >= 400, "o roteiro sem cenas é recusado"

    total = (await db_session.execute(select(func.count(AIUsage.id)))).scalar_one()
    assert total >= 1, "o consumo continua registrado"
