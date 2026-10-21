"""Provedor de reserva: o que fazer quando o modelo escolhido não responde.

A coluna ``ai_feature_bindings.fallback_model_id`` existe desde a Fase 2 e
**nunca foi lida por ninguém**. Era um campo no banco sem comportamento — o
tipo de coisa que o projeto proíbe. Esta camada é o comportamento.

Três escolhas que valem explicação:

*Só erro passageiro aciona a reserva.* Limite de requisições e provedor fora
do ar são problemas do momento, e trocar de modelo resolve. Chave inválida não
é: cair na reserva ali esconderia uma configuração errada que alguém precisa
consertar. O erro de credencial sobe.

*Uma tentativa, não uma cadeia.* A reserva da reserva não existe. Se as duas
falharem, o erro da segunda sobe, e as duas chamadas ficam registradas como
tentativas que custaram o que custaram.

*Cada chamada é medida separadamente.* A falha vai para ``ai_usage`` com
``status=ERROR`` pelo medidor do primeiro provedor; o acerto vai pelo medidor
do segundo, com uma decisão de roteamento própria dizendo
``FALLBACK_AFTER_ERROR``. Somar as duas sob um registro só esconderia a
primeira — que consumiu token mesmo tendo falhado.

A narração não tem reserva. A voz é escolhida por slug dentro de um provedor,
e trocar de provedor no meio trocaria a voz do narrador da aula sem avisar
ninguém. Preferi deixar o erro subir.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any

from app.ai.base import (
    AIProvider,
    CompletionRequest,
    CompletionResult,
    ConnectionCheck,
    EmbeddingResult,
    ModelInfo,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    SpeechRequest,
    SpeechResult,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Erros em que vale tentar outro modelo. Deliberadamente curto.
RETRYABLE = (ProviderRateLimitedError, ProviderUnavailableError)


class FallbackProvider(AIProvider):
    """Tenta o modelo escolhido e, em erro passageiro, o modelo de reserva.

    ``build_reserve`` é assíncrono e só é chamado quando a reserva vai ser
    usada de verdade: é ele que grava a decisão de roteamento do desvio. Uma
    decisão gravada antes da falha afirmaria um desvio que talvez não aconteça.
    """

    def __init__(
        self,
        primary: AIProvider,
        *,
        build_reserve: Callable[[str], Awaitable[AIProvider]],
        primary_model_slug: str,
        feature: str,
    ) -> None:
        super().__init__(primary.credentials)
        self.primary = primary
        self.build_reserve = build_reserve
        self.primary_model_slug = primary_model_slug
        self.feature = feature
        self.slug = primary.slug
        self.default_base_url = primary.default_base_url

    # ------------------------------------------------------------------ #
    # Passagem direta
    # ------------------------------------------------------------------ #
    async def test_connection(self) -> ConnectionCheck:
        return await self.primary.test_connection()

    async def list_models(self) -> list[ModelInfo]:
        return await self.primary.list_models()

    async def synthesize_speech(self, request: SpeechRequest) -> SpeechResult:
        return await self.primary.synthesize_speech(request)

    @property
    def voices(self) -> tuple[tuple[str, str], ...]:
        return self.primary.voices

    # ------------------------------------------------------------------ #
    # Caminhos com reserva
    # ------------------------------------------------------------------ #
    async def _reserve(self, error_code: str) -> AIProvider:
        logger.warning(
            "ai.fallback.engaged",
            feature=self.feature,
            failed_model=self.primary_model_slug,
            error=error_code,
        )
        return await self.build_reserve(error_code)

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        try:
            return await self.primary.complete(request)
        except RETRYABLE as exc:
            reserva = await self._reserve(exc.code)
            modelo = getattr(reserva, "model_slug", request.model)
            return await reserva.complete(replace(request, model=modelo))

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        # Embedding não tem reserva, e isso é uma decisão, não um esquecimento:
        # o vetor precisa vir do mesmo modelo que indexou a coleção. Um vetor
        # gerado por outro modelo vive em outro espaço, e a busca o compararia
        # com os demais como se fossem comparáveis — devolvendo trechos errados
        # com a mesma cara de certos. O erro sobe.
        return await self.primary.embed(texts, model)

    def __getattr__(self, name: str) -> Any:
        if name == "primary":
            # Sem esta guarda, qualquer acesso a ``primary`` antes de ele ser
            # atribuído cairia aqui e chamaria a si mesmo para sempre.
            raise AttributeError(name)
        return getattr(self.primary, name)
