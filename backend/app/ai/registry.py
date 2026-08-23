"""Registro de adaptadores disponíveis."""

from __future__ import annotations

from app.ai.base import AIProvider, ProviderCredentials
from app.ai.providers.openai import OpenAIProvider
from app.core.errors import NotFoundError

_PROVIDERS: dict[str, type[AIProvider]] = {
    OpenAIProvider.slug: OpenAIProvider,
}


def available_provider_slugs() -> list[str]:
    """Adaptadores já implementados (outros entram sem mexer no restante do código)."""
    return sorted(_PROVIDERS)


def build_provider(slug: str, credentials: ProviderCredentials) -> AIProvider:
    provider_class = _PROVIDERS.get(slug)
    if provider_class is None:
        raise NotFoundError(
            f"Provedor '{slug}' não possui adaptador implementado.",
            code="ai_provider_unsupported",
            details={"available": available_provider_slugs()},
        )
    return provider_class(credentials)
