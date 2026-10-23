"""Registro de adaptadores disponíveis — de texto e de julgamento.

Os dois tipos moram no mesmo painel porque, para quem administra, são a mesma
tarefa: cadastrar a chave de um fornecedor de IA. Mas são **portas diferentes**,
e o registro mantém isso explícito: pedir um provedor de texto onde há um de
julgamento recusa com o motivo, em vez de estourar mais adiante com um
``AttributeError`` que ninguém liga à configuração.
"""

from __future__ import annotations

from typing import Literal

from app.ai.base import AIProvider, ProviderCredentials
from app.ai.decisions import DecisionProvider
from app.ai.providers.aisa import AisaProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.typesafe import TypeSafeProvider
from app.core.errors import ConflictError, NotFoundError

ProviderKind = Literal["chat", "decision"]

_PROVIDERS: dict[str, type[AIProvider]] = {
    AisaProvider.slug: AisaProvider,
    OpenAIProvider.slug: OpenAIProvider,
}

_DECISION_PROVIDERS: dict[str, type[DecisionProvider]] = {
    TypeSafeProvider.slug: TypeSafeProvider,
}


def available_provider_slugs() -> list[str]:
    """Adaptadores já implementados, dos dois tipos."""
    return sorted({*_PROVIDERS, *_DECISION_PROVIDERS})


def provider_kind(slug: str) -> ProviderKind:
    """Que porta este fornecedor atende."""
    if slug in _DECISION_PROVIDERS:
        return "decision"
    return "chat"


def _unsupported(slug: str) -> NotFoundError:
    return NotFoundError(
        f"Provedor '{slug}' não possui adaptador implementado.",
        code="ai_provider_unsupported",
        details={"available": available_provider_slugs()},
    )


def build_provider(slug: str, credentials: ProviderCredentials) -> AIProvider:
    provider_class = _PROVIDERS.get(slug)
    if provider_class is None:
        if slug in _DECISION_PROVIDERS:
            raise ConflictError(
                f"O provedor '{slug}' responde julgamento tipado, não texto. "
                "Ele não atende funcionalidades de chat, embedding ou voz.",
                code="ai_provider_kind_mismatch",
            )
        raise _unsupported(slug)
    return provider_class(credentials)


def build_decision_provider(slug: str, credentials: ProviderCredentials) -> DecisionProvider:
    provider_class = _DECISION_PROVIDERS.get(slug)
    if provider_class is None:
        if slug in _PROVIDERS:
            raise ConflictError(
                f"O provedor '{slug}' responde texto, não julgamento tipado.",
                code="ai_provider_kind_mismatch",
            )
        raise _unsupported(slug)
    return provider_class(credentials)
