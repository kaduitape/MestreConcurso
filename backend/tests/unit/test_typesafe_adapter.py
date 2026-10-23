"""O adaptador do TypeSafe (Jev), conferido contra o contrato real do SDK.

Nenhum destes testes toca a rede. O transporte é trocado por um `MockTransport`
do httpx2 que devolve o **modelo de resposta do próprio SDK**, serializado por
ele: é a forma de provar a tradução sem inventar formato de fio — que é
exatamente o que a documentação do fornecedor manda não fazer quando não se tem
acesso à API.

O que está sob teste é a fronteira: pergunta neutra → primitiva do SDK, resposta
do SDK → vereditos da plataforma, e erro do SDK → erro normalizado.
"""

from __future__ import annotations

from typing import Any

import httpx2
import pytest
from typesafe_sdk import (
    AsyncTypeSafeClient,
    ChoiceAnswer,
    NoulAnswer,
    ScoreAnswer,
    SystemOneResponse,
)
from typesafe_sdk import Usage as SDKUsage

from app.ai.base import (
    ProviderAuthError,
    ProviderCredentials,
    ProviderRateLimitedError,
    ProviderUnavailableError,
)
from app.ai.decisions import (
    ChoiceQuestion,
    ChoiceVerdict,
    DecisionRequest,
    NoulQuestion,
    NoulVerdict,
    ScoreQuestion,
    ScoreVerdict,
)
from app.ai.providers.typesafe import TypeSafeProvider


def _provider(handler: Any) -> TypeSafeProvider:
    """Provedor com o transporte trocado — o resto do caminho roda de verdade.

    A injeção usa o ponto que o próprio SDK oferece (``transport=``), e não um
    atributo privado dele: teste que mexe no que a biblioteca não expôs quebra
    na próxima versão e não diz por quê.
    """
    provider = TypeSafeProvider(ProviderCredentials(api_key="sk-teste", timeout_seconds=5))

    def build() -> AsyncTypeSafeClient:
        return AsyncTypeSafeClient(
            api_key="sk-teste",
            base_url=provider.base_url,
            transport=httpx2.MockTransport(handler),
        )

    provider._client = build  # type: ignore[method-assign]
    return provider


def _resposta(answers: dict[str, Any], *, model: str = "jev-1") -> httpx2.Response:
    corpo = SystemOneResponse(
        model=model,
        usage=SDKUsage(input_tokens=120, output_tokens=8),
        answers=answers,
    )
    return httpx2.Response(200, json=corpo.model_dump(mode="json"))


async def test_a_noul_answer_becomes_a_probability() -> None:
    """O caso que a parte 2c usa: "a citação sustenta o gabarito?"."""
    recebido: dict[str, Any] = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        import json

        recebido.update(json.loads(request.content))
        return _resposta({"sustenta": NoulAnswer(type="noul", noul=0.873)})

    provider = _provider(handler)
    resultado = await provider.judge(
        DecisionRequest(
            state={"citacao": "a crase é a contração da preposição"},
            questions={
                "sustenta": NoulQuestion(
                    instructions="A citação sustenta o gabarito?",
                    when_true="afirma o que a alternativa diz",
                )
            },
        )
    )

    assert resultado.noul("sustenta") == NoulVerdict(probability=0.873)
    assert resultado.model == "jev-1"
    # A medição da Fase 2 depende destes dois números.
    assert (resultado.usage.input_tokens, resultado.usage.output_tokens) == (120, 8)
    # E a pergunta chegou como primitiva do SDK, com o critério traduzido.
    assert recebido["questions"]["sustenta"]["type"] == "noul"
    assert recebido["questions"]["sustenta"]["criteria"]["true"] == "afirma o que a alternativa diz"
    assert recebido["state"]["citacao"].startswith("a crase")


async def test_a_choice_answer_keeps_the_distribution() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return _resposta(
            {
                "topico": ChoiceAnswer(
                    type="choice",
                    choice="crase",
                    confidence=0.62,
                    probabilities={"crase": 0.62, "regencia": 0.38},
                )
            }
        )

    resultado = await _provider(handler).judge(
        DecisionRequest(
            state={"rotulo": "Emprego do acento grave"},
            questions={
                "topico": ChoiceQuestion(
                    instructions="Qual tópico do catálogo é este?",
                    criteria={"crase": None, "regencia": "regência verbal e nominal"},
                )
            },
        )
    )

    veredito = resultado.choice("topico")
    assert isinstance(veredito, ChoiceVerdict)
    assert veredito.choice == "crase"
    # A confiança é concentração da distribuição, e a distribuição vem junto:
    # sem ela, "62%" não diz contra o quê.
    assert veredito.confidence == pytest.approx(0.62)
    assert veredito.probabilities == {"crase": 0.62, "regencia": 0.38}


async def test_a_score_answer_keeps_the_legend() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return _resposta(
            {
                "clareza": ScoreAnswer(
                    type="score",
                    score=2.4,
                    confidence=0.55,
                    legend={1: "confuso", 2: "aceitável", 3: "claro"},
                    probabilities={1: 0.1, 2: 0.5, 3: 0.4},
                )
            }
        )

    resultado = await _provider(handler).judge(
        DecisionRequest(
            state={"enunciado": "..."},
            questions={
                "clareza": ScoreQuestion(
                    instructions="Quão claro está o enunciado?",
                    levels=("confuso", "aceitável", "claro"),
                )
            },
        )
    )

    veredito = resultado.score("clareza")
    assert isinstance(veredito, ScoreVerdict)
    assert veredito.score == pytest.approx(2.4)
    # A legenda é o que torna a nota legível; sem ela "2,4" não significa nada.
    assert veredito.legend[2] == "aceitável"


async def test_asking_for_the_wrong_type_fails_loudly() -> None:
    """Pedir ``choice`` onde veio ``noul`` é defeito de código, não dado ruim."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return _resposta({"sustenta": NoulAnswer(type="noul", noul=0.5)})

    resultado = await _provider(handler).judge(
        DecisionRequest(state={}, questions={"sustenta": NoulQuestion(instructions="?")})
    )

    with pytest.raises(TypeError, match="NoulVerdict"):
        resultado.choice("sustenta")


@pytest.mark.parametrize(
    ("status", "esperado"),
    [
        (401, ProviderAuthError),
        (403, ProviderAuthError),
        (429, ProviderRateLimitedError),
    ],
)
async def test_provider_errors_are_normalised(status: int, esperado: type[Exception]) -> None:
    """A plataforma inteira já sabe lidar com estes três erros.

    É o que faz a reserva da Fase 6, o teto da Fase 2 e as telas continuarem
    funcionando sem saber que existe um fornecedor novo.
    """

    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json={"error": {"message": "não"}})

    provider = _provider(handler)
    with pytest.raises(esperado):
        await provider.judge(
            DecisionRequest(state={}, questions={"q": NoulQuestion(instructions="?")})
        )


async def test_a_timeout_becomes_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectTimeout("tempo esgotado")

    provider = _provider(handler)
    with pytest.raises(ProviderUnavailableError):
        await provider.judge(
            DecisionRequest(state={}, questions={"q": NoulQuestion(instructions="?")})
        )
