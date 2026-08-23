"""Adaptador OpenAI — exercitado com transporte HTTP simulado."""

from __future__ import annotations

import httpx
import pytest

from app.ai.base import (
    ChatMessage,
    CompletionRequest,
    ProviderAuthError,
    ProviderCredentials,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.ai.providers.openai import OpenAIProvider


def _provider(handler: httpx.MockTransport, monkeypatch: pytest.MonkeyPatch) -> OpenAIProvider:
    provider = OpenAIProvider(ProviderCredentials(api_key="sk-teste-123456789012345"))
    original = httpx.AsyncClient.__init__

    def patched(self: httpx.AsyncClient, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = handler
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)
    return provider


async def test_test_connection_reports_usable_models(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        assert request.headers["Authorization"] == "Bearer sk-teste-123456789012345"
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-4o-mini"},
                    {"id": "text-embedding-3-small"},
                    {"id": "whisper-1"},
                    {"id": "dall-e-3"},
                ]
            },
        )

    provider = _provider(httpx.MockTransport(handler), monkeypatch)
    check = await provider.test_connection()

    assert check.ok is True
    # whisper e dall-e são descartados: não servem à plataforma.
    assert check.models_available == 2
    assert "gpt-4o-mini" in check.sample_models


async def test_list_models_maps_known_pricing(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"data": [{"id": "gpt-4o-mini"}, {"id": "modelo-desconhecido"}]}
        )
    )
    provider = _provider(handler, monkeypatch)
    models = await provider.list_models()

    by_slug = {model.slug: model for model in models}
    assert by_slug["gpt-4o-mini"].input_cost_per_1k is not None
    # Sem preço conhecido, o campo fica vazio em vez de receber um número inventado.
    assert by_slug["modelo-desconhecido"].input_cost_per_1k is None


async def test_complete_returns_content_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "model": "gpt-4o-mini",
                "choices": [{"message": {"content": "resposta"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30},
            },
        )

    provider = _provider(httpx.MockTransport(handler), monkeypatch)
    result = await provider.complete(
        CompletionRequest(messages=[ChatMessage(role="user", content="oi")], model="gpt-4o-mini")
    )

    assert result.content == "resposta"
    assert result.usage.input_tokens == 120
    assert result.usage.total == 150


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, ProviderAuthError),
        (429, ProviderRateLimitedError),
        (503, ProviderUnavailableError),
    ],
)
async def test_http_errors_are_normalized(
    status: int, expected: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    handler = httpx.MockTransport(
        lambda request: httpx.Response(status, json={"error": {"message": "falhou"}})
    )
    provider = _provider(handler, monkeypatch)
    with pytest.raises(expected):
        await provider.test_connection()


async def test_network_failure_becomes_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota para o host")

    provider = _provider(httpx.MockTransport(handler), monkeypatch)
    with pytest.raises(ProviderUnavailableError):
        await provider.test_connection()
