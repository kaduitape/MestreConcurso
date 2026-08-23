"""Configuração de provedores de IA pelo painel."""

from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import create_admin, create_user

API_KEY = "sk-proj-chave-de-teste-1234567890"


def _mock_openai(monkeypatch: pytest.MonkeyPatch, handler: httpx.MockTransport) -> None:
    """Intercepta o HTTP do adaptador sem trocar o adaptador em si."""
    original = httpx.AsyncClient.__init__

    def patched(self: httpx.AsyncClient, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = handler
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)


def _models_transport() -> httpx.MockTransport:
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o-mini"},
                    {"id": "gpt-4o"},
                    {"id": "text-embedding-3-small"},
                ]
            },
        )
    )


async def test_student_cannot_touch_ai_settings(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.ia@exemplo.com.br")
    response = await client.get("/api/v1/admin/ai/providers", headers=student.auth_header)
    assert response.status_code == 403


async def test_available_providers_lists_implemented_adapters(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="ia1@exemplo.com.br")
    response = await client.get("/api/v1/admin/ai/providers/available", headers=admin.auth_header)
    assert response.status_code == 200
    assert "openai" in response.json()["available"]
    assert response.json()["configured"] == []


async def test_register_openai_and_store_key_encrypted(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="ia2@exemplo.com.br")

    created = await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["display_name"] == "OpenAI (ChatGPT)"
    assert body["has_api_key"] is False
    assert body["is_active"] is False

    duplicated = await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    assert duplicated.status_code == 409

    with_key = await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )
    assert with_key.status_code == 200
    payload = with_key.json()
    assert payload["has_api_key"] is True
    assert payload["api_key_hint"] == "sk-…7890"
    # A chave em claro nunca aparece na resposta.
    assert API_KEY not in with_key.text

    # E também não é gravada em claro no banco.
    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.ai import AIProviderConfig

    factory = get_session_factory()
    async with factory() as session:
        provider = (
            await session.execute(select(AIProviderConfig).where(AIProviderConfig.slug == "openai"))
        ).scalar_one()
        assert provider.api_key_encrypted is not None
        assert API_KEY not in provider.api_key_encrypted


async def test_unsupported_provider_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="ia3@exemplo.com.br")
    response = await client.post(
        "/api/v1/admin/ai/providers",
        headers=admin.auth_header,
        json={"slug": "provedor-inexistente"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ai_provider_unsupported"


async def test_cannot_activate_provider_without_key(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="ia4@exemplo.com.br")
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    response = await client.patch(
        "/api/v1/admin/ai/providers/openai",
        headers=admin.auth_header,
        json={"is_active": True},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ai_provider_missing_key"


async def test_test_connection_and_sync_models(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="ia5@exemplo.com.br")
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )

    _mock_openai(monkeypatch, _models_transport())

    test = await client.post("/api/v1/admin/ai/providers/openai/test", headers=admin.auth_header)
    assert test.status_code == 200
    assert test.json()["ok"] is True
    assert test.json()["models_available"] == 3

    synced = await client.post(
        "/api/v1/admin/ai/providers/openai/models/sync", headers=admin.auth_header
    )
    assert synced.status_code == 200
    slugs = {model["slug"] for model in synced.json()}
    assert {"gpt-4o", "gpt-4o-mini", "text-embedding-3-small"} == slugs

    listed = await client.get("/api/v1/admin/ai/providers", headers=admin.auth_header)
    provider = listed.json()[0]
    assert provider["last_test_status"] == "OK"
    assert len(provider["models"]) == 3


async def test_failed_connection_is_recorded(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="ia6@exemplo.com.br")
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )

    _mock_openai(
        monkeypatch,
        httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": {"message": "chave inválida"}})
        ),
    )
    response = await client.post(
        "/api/v1/admin/ai/providers/openai/test", headers=admin.auth_header
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ai_provider_unauthorized"

    listed = await client.get("/api/v1/admin/ai/providers", headers=admin.auth_header)
    assert listed.json()[0]["last_test_status"] == "FAILED"


async def test_feature_binding_requires_active_provider(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="ia7@exemplo.com.br")
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )
    _mock_openai(monkeypatch, _models_transport())
    await client.post("/api/v1/admin/ai/providers/openai/models/sync", headers=admin.auth_header)

    features = await client.get("/api/v1/admin/ai/features", headers=admin.auth_header)
    assert features.status_code == 200
    assert {item["feature"] for item in features.json()} >= {"board.profile", "chat.tutor"}
    assert all(item["is_enabled"] is False for item in features.json())

    blocked = await client.put(
        "/api/v1/admin/ai/features/board.profile",
        headers=admin.auth_header,
        json={"provider_slug": "openai", "model_slug": "gpt-4o-mini", "is_enabled": True},
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "ai_provider_inactive"

    activated = await client.patch(
        "/api/v1/admin/ai/providers/openai",
        headers=admin.auth_header,
        json={"is_active": True},
    )
    assert activated.status_code == 200

    bound = await client.put(
        "/api/v1/admin/ai/features/board.profile",
        headers=admin.auth_header,
        json={
            "provider_slug": "openai",
            "model_slug": "gpt-4o-mini",
            "is_enabled": True,
            "cache_ttl_hours": 720,
        },
    )
    assert bound.status_code == 200
    assert bound.json()["model_slug"] == "gpt-4o-mini"
    assert bound.json()["cache_ttl_hours"] == 720


async def test_removing_key_deactivates_provider(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="ia8@exemplo.com.br")
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )
    removed = await client.delete(
        "/api/v1/admin/ai/providers/openai/key", headers=admin.auth_header
    )
    assert removed.status_code == 200
    assert removed.json()["has_api_key"] is False
    assert removed.json()["is_active"] is False


async def test_ai_actions_are_audited(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="ia9@exemplo.com.br")
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )
    logs = await client.get(
        "/api/v1/admin/audit-logs?action=ai.provider_key_set", headers=admin.auth_header
    )
    assert logs.json()["total"] == 1
    assert logs.json()["items"][0]["meta"]["hint"] == "sk-…7890"
