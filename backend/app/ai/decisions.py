"""A porta do **julgamento tipado** — e por que ela não é a porta de texto.

O item 15 do plano pedia um adaptador para o JEV, e o diagnóstico da Fase 6
advertia para não presumir o que ele faz. Com a documentação em mãos, o que ele
faz ficou claro, e é diferente do que o pedido original supunha:

* o JEV **não orquestra** nada, **não escolhe modelo** e **não pesquisa** fora;
* ele recebe estado da aplicação e perguntas com resposta de tipo declarado, e
  devolve **respostas tipadas com probabilidade** — nunca texto para interpretar.

Quem manda no fluxo continua sendo o código. É por isso que isto é uma porta
**paralela** à de texto, e não um provedor a mais em ``app/ai/base.py``: um
modelo que devolve "qual das cinco" com distribuição de probabilidade não cabe
em ``complete()`` sem que alguém volte a fazer *prompt-and-parse* — exatamente o
que esta camada existe para eliminar.

O que é reaproveitado, de propósito: credencial, medição (``Usage``), teste de
conexão, ficha de modelo e a família de erros normalizados. Duas taxonomias de
erro para dois fornecedores de IA seria o começo de duas plataformas.

Três primitivas, porque são as três que o serviço oferece:

``ChoiceQuestion``
    uma de um conjunto declarado. A distribuição compara as opções entre si.
``NoulQuestion``
    uma condição vale ou não. A resposta é a **probabilidade de sim** — não há
    confiança separada, e 0,5 significa "tão provável quanto improvável", não
    "meio verdadeiro".
``ScoreQuestion``
    posição numa escala de níveis descritos, com a distribuição entre eles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.ai.base import ConnectionCheck, ModelInfo, ProviderCredentials, Usage


# --------------------------------------------------------------------------- #
# Perguntas
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ChoiceQuestion:
    """Uma de um conjunto declarado de opções."""

    instructions: str
    #: Opção → descrição (ou ``None`` quando o nome já diz tudo).
    criteria: Mapping[str, str | None]


@dataclass(frozen=True, slots=True)
class NoulQuestion:
    """Uma condição que vale ou não vale. A resposta é a probabilidade de sim."""

    instructions: str
    #: O que significa "sim" e o que significa "não", quando não é óbvio.
    when_true: str | None = None
    when_false: str | None = None


@dataclass(frozen=True, slots=True)
class ScoreQuestion:
    """Posição numa escala de níveis descritos, do menor para o maior."""

    instructions: str
    #: Cada nível descrito por extenso. Nível vago torna a nota inútil.
    levels: Sequence[str]


Question = ChoiceQuestion | NoulQuestion | ScoreQuestion


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """O estado da aplicação e as perguntas feitas sobre ele.

    As perguntas de um mesmo pedido **não se enxergam**: elas correm em paralelo
    sobre o mesmo estado. Quando uma depende da resposta da outra, são dois
    pedidos — e é o código que encadeia.
    """

    state: Mapping[str, Any]
    questions: Mapping[str, Question]


# --------------------------------------------------------------------------- #
# Respostas
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ChoiceVerdict:
    choice: str
    #: Concentração da distribuição — não é "chance de estar certo".
    confidence: float
    probabilities: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NoulVerdict:
    """A probabilidade de a condição valer. Sem confiança separada, por desenho."""

    probability: float


@dataclass(frozen=True, slots=True)
class ScoreVerdict:
    score: float
    confidence: float
    #: Nível → descrição, do jeito que o serviço devolveu.
    legend: Mapping[int, str] = field(default_factory=dict)
    probabilities: Mapping[int, float] = field(default_factory=dict)


Verdict = ChoiceVerdict | NoulVerdict | ScoreVerdict


@dataclass(frozen=True, slots=True)
class DecisionResult:
    """O que voltou de uma chamada, pronto para o código compor."""

    answers: Mapping[str, Verdict]
    model: str
    usage: Usage
    latency_ms: int

    def choice(self, key: str) -> ChoiceVerdict:
        return self._typed(key, ChoiceVerdict)

    def noul(self, key: str) -> NoulVerdict:
        return self._typed(key, NoulVerdict)

    def score(self, key: str) -> ScoreVerdict:
        return self._typed(key, ScoreVerdict)

    def _typed(self, key: str, expected: type[Any]) -> Any:
        """Leitura com tipo cobrado.

        Pedir ``noul`` e receber ``choice`` é defeito de código, não dado ruim:
        falhar aqui é melhor que seguir com um número que significa outra coisa.
        """
        found = self.answers.get(key)
        if found is None:
            raise KeyError(f"A resposta '{key}' não veio no resultado.")
        if not isinstance(found, expected):
            raise TypeError(
                f"A resposta '{key}' é {type(found).__name__}, não {expected.__name__}."
            )
        return found


# --------------------------------------------------------------------------- #
# A porta
# --------------------------------------------------------------------------- #
class DecisionProvider(ABC):
    """Porta de um fornecedor de julgamento tipado."""

    slug: str
    default_base_url: str
    #: Modelo usado quando a funcionalidade não escolhe um.
    default_model: str

    def __init__(self, credentials: ProviderCredentials) -> None:
        self.credentials = credentials

    @property
    def base_url(self) -> str:
        return (self.credentials.base_url or self.default_base_url).rstrip("/")

    @abstractmethod
    async def test_connection(self) -> ConnectionCheck:
        """Chamada real e barata para validar credencial e conectividade."""

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Modelos de julgamento disponíveis para a credencial."""

    @abstractmethod
    async def judge(self, request: DecisionRequest, *, model: str | None = None) -> DecisionResult:
        """Faz as perguntas e devolve as respostas tipadas."""
