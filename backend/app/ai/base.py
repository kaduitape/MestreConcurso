"""Contratos neutros da camada de IA (porta ``AIProvider``)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.core.errors import AppError

Role = Literal["system", "user", "assistant"]


# --------------------------------------------------------------------------- #
# Erros normalizados (independentes do fornecedor)
# --------------------------------------------------------------------------- #
class ProviderError(AppError):
    status_code = 502
    code = "ai_provider_error"
    message = "O provedor de IA não respondeu como esperado."


class ProviderAuthError(ProviderError):
    status_code = 401
    code = "ai_provider_unauthorized"
    message = "Chave de API inválida ou sem permissão."


class ProviderRateLimitedError(ProviderError):
    status_code = 429
    code = "ai_provider_rate_limited"
    message = "O provedor está limitando as requisições. Tente novamente em instantes."


class ProviderUnavailableError(ProviderError):
    status_code = 503
    code = "ai_provider_unavailable"
    message = "Não foi possível falar com o provedor de IA."


class SpeechNotSupportedError(AppError):
    status_code = 409
    code = "ai_speech_unsupported"
    message = "Este provedor de IA não gera áudio."


class ProviderNotConfiguredError(AppError):
    status_code = 409
    code = "ai_provider_not_configured"
    message = "Nenhum provedor de IA configurado para esta funcionalidade."


# --------------------------------------------------------------------------- #
# Estruturas de requisição/resposta
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class CompletionRequest:
    messages: list[ChatMessage]
    model: str
    temperature: float = 0.2
    max_output_tokens: int | None = None
    json_response: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CompletionResult:
    content: str
    model: str
    usage: Usage
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SpeechRequest:
    """Um trecho para virar voz.

    ``instructions`` é a direção de cena: o texto que diz **como** ler, não o
    que ler. É o que separa uma leitura de robô de uma narração — e, como vem
    do próprio roteiro, não inventa nada sobre o conteúdo.
    """

    text: str
    model: str
    voice: str
    instructions: str | None = None
    #: Formato do arquivo. ``mp3`` toca em qualquer navegador.
    audio_format: str = "mp3"
    speed: float = 1.0


@dataclass(frozen=True, slots=True)
class SpeechResult:
    audio: bytes
    mime_type: str
    model: str
    voice: str
    latency_ms: int
    #: Caracteres cobrados — a unidade de preço das APIs de voz.
    characters: int = 0


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    usage: Usage
    latency_ms: int


@dataclass(frozen=True, slots=True)
class ModelInfo:
    slug: str
    display_name: str
    kind: Literal["chat", "embedding", "rerank", "speech", "judgment"] = "chat"
    context_window: int | None = None
    max_output_tokens: int | None = None
    input_cost_per_1k: Decimal | None = None
    output_cost_per_1k: Decimal | None = None
    supports_tools: bool = False
    supports_json: bool = False


@dataclass(frozen=True, slots=True)
class ConnectionCheck:
    """Resultado de um teste real contra a API do fornecedor."""

    ok: bool
    message: str
    latency_ms: int
    models_available: int = 0
    sample_models: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProviderCredentials:
    api_key: str
    base_url: str | None = None
    organization: str | None = None
    timeout_seconds: int = 60


class AIProvider(ABC):
    """Porta que todo fornecedor precisa implementar."""

    slug: str
    default_base_url: str

    def __init__(self, credentials: ProviderCredentials) -> None:
        self.credentials = credentials

    @property
    def base_url(self) -> str:
        return (self.credentials.base_url or self.default_base_url).rstrip("/")

    @abstractmethod
    async def test_connection(self) -> ConnectionCheck:
        """Faz uma chamada real e barata para validar credencial e conectividade."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Lista os modelos disponíveis para a credencial informada."""

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResult:
        """Gera uma resposta de texto."""

    @abstractmethod
    async def embed(self, texts: list[str], model: str) -> EmbeddingResult:
        """Gera embeddings para os textos informados."""

    async def synthesize_speech(self, request: SpeechRequest) -> SpeechResult:
        """Gera áudio a partir de texto.

        Opcional de propósito: nem todo fornecedor fala. O padrão recusa em vez
        de devolver silêncio, para a tela poder dizer ao administrador que o
        provedor escolhido não serve para narrar.
        """
        raise SpeechNotSupportedError(f"O provedor '{self.slug}' não implementa geração de voz.")

    #: Vozes que o adaptador oferece. Lista vazia quando ele não fala.
    @property
    def voices(self) -> tuple[tuple[str, str], ...]:
        """Pares ``(slug, rótulo)`` para o painel escolher sem adivinhar."""
        return ()
