"""Adaptador do OpenAI (ChatGPT) — fala HTTP direto, sem SDK proprietário.

Também atende endpoints compatíveis com a API da OpenAI (Azure OpenAI, gateways
locais) quando o administrador informa outra ``base_url``.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import Any

import httpx

from app.ai.base import (
    AIProvider,
    ChatMessage,
    CompletionRequest,
    CompletionResult,
    ConnectionCheck,
    EmbeddingResult,
    ModelInfo,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    Usage,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Preços públicos por 1k tokens (USD). Servem só para estimar custo; o painel
# permite corrigir qualquer valor, e o que não estiver aqui fica sem preço em vez
# de receber um número inventado.
KNOWN_PRICING: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4o": (Decimal("0.0025"), Decimal("0.01")),
    "gpt-4o-mini": (Decimal("0.00015"), Decimal("0.0006")),
    "gpt-4.1": (Decimal("0.002"), Decimal("0.008")),
    "gpt-4.1-mini": (Decimal("0.0004"), Decimal("0.0016")),
    "gpt-4.1-nano": (Decimal("0.0001"), Decimal("0.0004")),
    "text-embedding-3-small": (Decimal("0.00002"), Decimal("0")),
    "text-embedding-3-large": (Decimal("0.00013"), Decimal("0")),
}

CONTEXT_WINDOWS: dict[str, int] = {
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1-nano": 1_047_576,
}


def _classify_model(slug: str) -> str:
    if "embedding" in slug:
        return "embedding"
    if "rerank" in slug:
        return "rerank"
    return "chat"


def _is_usable(slug: str) -> bool:
    """Filtra modelos que não interessam à plataforma (áudio, imagem, moderação)."""
    ignored = ("whisper", "tts", "dall-e", "moderation", "audio", "image", "realtime")
    return not any(token in slug for token in ignored)


class OpenAIProvider(AIProvider):
    slug = "openai"
    default_base_url = "https://api.openai.com/v1"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.credentials.api_key}",
            "Content-Type": "application/json",
        }
        if self.credentials.organization:
            headers["OpenAI-Organization"] = self.credentials.organization
        return headers

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers(),
            timeout=httpx.Timeout(self.credentials.timeout_seconds, connect=10),
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        detail = ""
        try:
            body = response.json()
            detail = str(body.get("error", {}).get("message", ""))[:200]
        # Corpo não-JSON não deve mascarar o status HTTP.
        except Exception:
            detail = response.text[:200]

        if response.status_code in (401, 403):
            raise ProviderAuthError(detail or None)
        if response.status_code == 429:
            raise ProviderRateLimitedError(detail or None)
        if response.status_code >= 500:
            raise ProviderUnavailableError(detail or None)
        raise ProviderError(detail or None, details={"status": response.status_code})

    async def test_connection(self) -> ConnectionCheck:
        started = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.get("/models")
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"Falha de rede ao contatar o provedor: {exc}") from exc

        self._raise_for_status(response)
        latency = int((time.perf_counter() - started) * 1000)
        data: list[dict[str, Any]] = response.json().get("data", [])
        usable = sorted(item["id"] for item in data if _is_usable(str(item.get("id", ""))))

        return ConnectionCheck(
            ok=True,
            message="Conexão estabelecida com sucesso.",
            latency_ms=latency,
            models_available=len(usable),
            sample_models=usable[:8],
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with self._client() as client:
                response = await client.get("/models")
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        self._raise_for_status(response)
        models: list[ModelInfo] = []
        for item in response.json().get("data", []):
            slug = str(item.get("id", ""))
            if not slug or not _is_usable(slug):
                continue
            pricing = KNOWN_PRICING.get(slug)
            kind = _classify_model(slug)
            models.append(
                ModelInfo(
                    slug=slug,
                    display_name=slug,
                    kind=kind,  # type: ignore[arg-type]
                    context_window=CONTEXT_WINDOWS.get(slug),
                    input_cost_per_1k=pricing[0] if pricing else None,
                    output_cost_per_1k=pricing[1] if pricing else None,
                    supports_tools=kind == "chat",
                    supports_json=kind == "chat",
                )
            )
        return sorted(models, key=lambda model: model.slug)

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": message.role, "content": message.content} for message in request.messages
            ],
            "temperature": request.temperature,
        }
        if request.max_output_tokens:
            payload["max_tokens"] = request.max_output_tokens
        if request.json_response:
            payload["response_format"] = {"type": "json_object"}

        started = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        self._raise_for_status(response)
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise ProviderError("O provedor devolveu uma resposta vazia.")

        usage = body.get("usage") or {}
        return CompletionResult(
            content=choices[0].get("message", {}).get("content", ""),
            model=body.get("model", request.model),
            usage=Usage(
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
            ),
            latency_ms=int((time.perf_counter() - started) * 1000),
            raw={"finish_reason": choices[0].get("finish_reason")},
        )

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        started = time.perf_counter()
        try:
            async with self._client() as client:
                response = await client.post("/embeddings", json={"model": model, "input": texts})
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

        self._raise_for_status(response)
        body = response.json()
        usage = body.get("usage") or {}
        return EmbeddingResult(
            vectors=[item["embedding"] for item in body.get("data", [])],
            model=body.get("model", model),
            usage=Usage(input_tokens=int(usage.get("prompt_tokens", 0))),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )


__all__ = ["ChatMessage", "OpenAIProvider"]
