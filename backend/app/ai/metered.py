"""Provedor medido: o único lugar onde o gasto com IA é contado.

Existem nove pontos no código que falam com um provedor. Medir em cada um
deles daria nove chances de esquecer — e o esquecido não aparece na conta, que
é justamente o defeito que esta camada veio consertar.

Em vez disso, o ``resolve_feature`` devolve o provedor **já embrulhado** aqui.
Quem chama continua escrevendo ``await resolved.provider.complete(...)`` e não
precisa saber de nada. Toda chamada passa a:

1. ser barrada se o teto já foi estourado;
2. acontecer de verdade;
3. ser registrada em ``ai_usage``, com tokens reais e custo calculado.

A falha também é registrada. Uma chamada que estourou depois de consumir token
custou dinheiro, e some da conta se só o sucesso for contado.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.ai.base import (
    AIProvider,
    CompletionRequest,
    CompletionResult,
    ConnectionCheck,
    EmbeddingResult,
    ModelInfo,
    SpeechRequest,
    SpeechResult,
)


class MeteredProvider(AIProvider):
    """Embrulha um provedor somando medição e teto de gasto.

    Herda de ``AIProvider`` para continuar satisfazendo o mesmo contrato — o
    resto da aplicação não distingue um do outro, que é o ponto.
    """

    def __init__(
        self,
        inner: AIProvider,
        *,
        feature: str,
        model_slug: str,
        input_cost_per_1k: Decimal | None,
        output_cost_per_1k: Decimal | None,
        user_id: int | None = None,
        routing_decision_id: int | None = None,
    ) -> None:
        super().__init__(inner.credentials)
        self.inner = inner
        self.slug = inner.slug
        self.default_base_url = inner.default_base_url
        self.feature = feature
        self.model_slug = model_slug
        self.input_cost_per_1k = input_cost_per_1k
        self.output_cost_per_1k = output_cost_per_1k
        self.user_id = user_id
        #: Liga cada linha de gasto à explicação de por que este modelo foi
        #: usado. Sem isso, "por que este modelo?" só se responde por
        #: aproximação de horário entre duas tabelas.
        self.routing_decision_id = routing_decision_id

    # ------------------------------------------------------------------ #
    # Passagem direta: não custam token, não entram na conta.
    # ------------------------------------------------------------------ #
    async def test_connection(self) -> ConnectionCheck:
        return await self.inner.test_connection()

    async def list_models(self) -> list[ModelInfo]:
        return await self.inner.list_models()

    @property
    def voices(self) -> tuple[tuple[str, str], ...]:
        return self.inner.voices

    # ------------------------------------------------------------------ #
    # Caminhos medidos
    # ------------------------------------------------------------------ #
    async def _guard(self) -> None:
        from app.db.session import get_session_factory
        from app.services.ai_budget import AIBudgetService

        factory = get_session_factory()
        async with factory() as session:
            await AIBudgetService(session).guard(feature=self.feature)

    async def _record(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int | None,
        status: str = "SUCCESS",
        error_code: str | None = None,
    ) -> None:
        from app.services.ai_budget import record_usage

        await record_usage(
            feature=self.feature,
            provider_slug=self.slug,
            model_slug=self.model_slug,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost_per_1k=self.input_cost_per_1k,
            output_cost_per_1k=self.output_cost_per_1k,
            latency_ms=latency_ms,
            user_id=self.user_id,
            status=status,
            error_code=error_code,
            routing_decision_id=self.routing_decision_id,
        )

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        await self._guard()
        try:
            result = await self.inner.complete(request)
        except Exception as exc:
            # Sem tokens conhecidos, mas o erro precisa constar: uma sequência
            # de falhas caras some da conta se só o sucesso for contado.
            await self._record(
                input_tokens=0,
                output_tokens=0,
                latency_ms=None,
                status="ERROR",
                error_code=type(exc).__name__[:60],
            )
            raise
        await self._record(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=result.latency_ms,
        )
        return result

    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        await self._guard()
        result = await self.inner.embed(texts, model)
        await self._record(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=result.latency_ms,
        )
        return result

    async def synthesize_speech(self, request: SpeechRequest) -> SpeechResult:
        await self._guard()
        result = await self.inner.synthesize_speech(request)
        # A API de fala cobra por caractere, não por token. Registrar o
        # tamanho do texto na entrada mantém o volume visível mesmo quando o
        # preço por 1k não descreve esse modelo.
        await self._record(
            input_tokens=len(request.text),
            output_tokens=0,
            latency_ms=getattr(result, "latency_ms", None),
        )
        return result

    def __getattr__(self, name: str) -> Any:
        # Qualquer coisa que um provedor específico exponha além do contrato.
        return getattr(self.inner, name)
