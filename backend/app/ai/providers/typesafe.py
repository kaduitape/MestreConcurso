"""Adaptador do TypeSafe (modelo **Jev**) — julgamento tipado, não texto.

Diferente dos outros adaptadores, este fala pelo **SDK oficial** em vez de HTTP
cru. O motivo é honesto: o contrato aqui não é "mande texto, receba texto" — são
primitivas com distribuição de probabilidade, e reimplementar a serialização
delas à mão seria assumir um formato de fio que o fornecedor pode mudar sem
avisar. O SDK é a fonte do contrato; este arquivo traduz entre ele e a porta
neutra da plataforma, e é só isso que ele faz.

A tradução acontece nos dois sentidos:

* as perguntas neutras (``ChoiceQuestion``, ``NoulQuestion``, ``ScoreQuestion``)
  viram primitivas do SDK;
* os erros do SDK viram a família ``ProviderError`` que a plataforma inteira já
  conhece — é o que faz a reserva da Fase 6, o teto da Fase 2 e as telas
  continuarem funcionando sem saber que existe um fornecedor novo.

Sem preço cadastrado não há custo inventado: a ficha do modelo sai com preço
nulo, e a medição grava os tokens com custo zero **declarado como desconhecido**,
do mesmo jeito que qualquer modelo sem preço.
"""

from __future__ import annotations

import time
from typing import Any

from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    ChoiceAnswer,
    Noul,
    NoulAnswer,
    NoulCriteria,
    Score,
    ScoreAnswer,
    TypeSafeAPIConnectionError,
    TypeSafeAPITimeoutError,
    TypeSafeAuthenticationError,
    TypeSafeError,
    TypeSafePermissionDeniedError,
    TypeSafeRateLimitError,
    constants,
)

from app.ai.base import (
    ConnectionCheck,
    ModelInfo,
    ProviderAuthError,
    ProviderError,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    Usage,
)
from app.ai.decisions import (
    ChoiceQuestion,
    ChoiceVerdict,
    DecisionProvider,
    DecisionRequest,
    DecisionResult,
    NoulQuestion,
    NoulVerdict,
    Question,
    ScoreQuestion,
    ScoreVerdict,
    Verdict,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class TypeSafeProvider(DecisionProvider):
    """Fala com o Jev pelo SDK oficial, por dentro da porta de julgamento."""

    slug = "typesafe"
    default_base_url = constants.DEFAULT_BASE_URL
    default_model = constants.DEFAULT_MODEL

    def _client(self) -> AsyncTypeSafeClient:
        """Um cliente por chamada.

        O SDK traz pool e repetição próprios; guardar o cliente entre
        requisições do FastAPI exigiria amarrar o ciclo de vida dele ao da
        aplicação, e o ganho não paga a chance de vazar conexão em recarga.
        """
        return AsyncTypeSafeClient(
            api_key=self.credentials.api_key,
            base_url=self.base_url,
            timeout=float(self.credentials.timeout_seconds or constants.DEFAULT_TIMEOUT),
        )

    # ------------------------------------------------------------------ #
    # Tradução
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_sdk(question: Question) -> Any:
        if isinstance(question, ChoiceQuestion):
            return Choice(instructions=question.instructions, criteria=dict(question.criteria))
        if isinstance(question, NoulQuestion):
            criteria = None
            if question.when_true or question.when_false:
                criteria = NoulCriteria(true=question.when_true, false=question.when_false)
            return Noul(instructions=question.instructions, criteria=criteria)
        if isinstance(question, ScoreQuestion):
            return Score(instructions=question.instructions, criteria=list(question.levels))
        raise ProviderError(f"Pergunta de tipo não suportado: {type(question).__name__}.")

    @staticmethod
    def _from_sdk(answer: Any) -> Verdict:
        if isinstance(answer, NoulAnswer):
            return NoulVerdict(probability=float(answer.noul))
        if isinstance(answer, ChoiceAnswer):
            return ChoiceVerdict(
                choice=answer.choice,
                confidence=float(answer.confidence),
                probabilities={str(k): float(v) for k, v in (answer.probabilities or {}).items()},
            )
        if isinstance(answer, ScoreAnswer):
            return ScoreVerdict(
                score=float(answer.score),
                confidence=float(answer.confidence),
                legend={int(k): str(v) for k, v in (answer.legend or {}).items()},
                probabilities={int(k): float(v) for k, v in (answer.probabilities or {}).items()},
            )
        # Primitiva nova no serviço é caso a tratar, não a adivinhar.
        raise ProviderError(f"Resposta de tipo desconhecido: {type(answer).__name__}.")

    # ------------------------------------------------------------------ #
    # Erros
    # ------------------------------------------------------------------ #
    @staticmethod
    def _translate(exc: TypeSafeError) -> ProviderError:
        """Erro do SDK → erro normalizado da plataforma.

        A reserva da Fase 6 só desvia em limite de taxa e indisponibilidade; por
        isso tempo esgotado e falha de conexão entram como *indisponível*, e
        credencial entra como erro de autenticação, que **não** se tenta de novo.
        """
        if isinstance(exc, TypeSafeAuthenticationError | TypeSafePermissionDeniedError):
            return ProviderAuthError("A chave do TypeSafe foi recusada.")
        if isinstance(exc, TypeSafeRateLimitError):
            return ProviderRateLimitedError()
        if isinstance(exc, TypeSafeAPITimeoutError | TypeSafeAPIConnectionError):
            return ProviderUnavailableError("O TypeSafe não respondeu no tempo esperado.")
        return ProviderError(f"O TypeSafe recusou a chamada: {exc}")

    # ------------------------------------------------------------------ #
    # A porta
    # ------------------------------------------------------------------ #
    async def test_connection(self) -> ConnectionCheck:
        started = time.perf_counter()
        try:
            async with self._client() as client:
                listados = await client.models.list()
        except TypeSafeError as exc:
            raise self._translate(exc) from exc
        latency = int((time.perf_counter() - started) * 1000)
        modelos = [item.name for item in listados.models]
        return ConnectionCheck(
            ok=True,
            message=f"{len(modelos)} modelo(s) de julgamento disponíveis.",
            latency_ms=latency,
            models_available=len(modelos),
            sample_models=modelos[:5],
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            async with self._client() as client:
                listados = await client.models.list()
        except TypeSafeError as exc:
            raise self._translate(exc) from exc
        return [
            ModelInfo(
                slug=item.name,
                display_name=item.description or item.name,
                kind="judgment",
                # Preço do julgamento não está na ficha do modelo: fica nulo em
                # vez de chutado, e o painel permite cadastrar quando se sabe.
                input_cost_per_1k=None,
                output_cost_per_1k=None,
                supports_json=True,
            )
            for item in listados.models
        ]

    async def judge(self, request: DecisionRequest, *, model: str | None = None) -> DecisionResult:
        perguntas = {key: self._to_sdk(item) for key, item in request.questions.items()}
        started = time.perf_counter()
        try:
            async with self._client() as client:
                resposta = await client.system_one(
                    state=dict(request.state),
                    questions=perguntas,
                    model=model or self.default_model,
                )
        except TypeSafeError as exc:
            logger.warning("typesafe.judge_failed", error=str(exc), questions=len(perguntas))
            raise self._translate(exc) from exc

        latency = int((time.perf_counter() - started) * 1000)
        return DecisionResult(
            answers={key: self._from_sdk(item) for key, item in resposta.answers.items()},
            model=resposta.model,
            usage=Usage(
                input_tokens=int(resposta.usage.input_tokens or 0),
                output_tokens=int(resposta.usage.output_tokens or 0),
            ),
            latency_ms=latency,
        )
