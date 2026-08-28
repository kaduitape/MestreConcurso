"""Estatística da plataforma — o único lugar onde intervalo é calculado.

Este módulo existe por causa de uma regra do projeto: **a IA nunca é responsável
sozinha por cálculo estatístico**. Todo número com incerteza sai daqui, em Python
determinístico e testável.

O intervalo usado é o de **Wilson**, e não o normal simples. A diferença importa
justamente onde o produto mais precisa de honestidade: com amostra pequena ou
proporção perto de 0 ou 1, o intervalo normal produz limites impossíveis (acerto
de −4% ou 108%) e uma falsa sensação de precisão. O de Wilson não sai de [0, 1] e
é assimétrico quando a proporção é extrema — que é exatamente o comportamento
correto para "acertei 9 de 10".
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

# 95%. Um número só, em um lugar só, para toda a plataforma.
Z_95 = 1.959963985

# Escadinha de confiança pela amostra. São limiares de produto, não de teoria:
# servem para a interface dizer o quanto se pode apoiar naquele número.
SAMPLE_LOW = 30  # abaixo disto o número existe, mas a faixa é larga
SAMPLE_HIGH = 300  # daqui para cima a faixa já é estreita o bastante


class Confidence(StrEnum):
    NONE = "NONE"  # sem amostra: não há número
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


CONFIDENCE_LABEL: dict[str, str] = {
    Confidence.NONE: "sem amostra",
    Confidence.LOW: "amostra pequena",
    Confidence.MEDIUM: "amostra razoável",
    Confidence.HIGH: "amostra sólida",
}


@dataclass(frozen=True, slots=True)
class Interval:
    """Uma proporção com a faixa em que ela plausivelmente está."""

    value: float
    low: float
    high: float
    sample: int
    confidence: str

    @property
    def width(self) -> float:
        return round(self.high - self.low, 4)

    @property
    def label(self) -> str:
        return CONFIDENCE_LABEL[self.confidence]


def confidence_for(sample: int) -> str:
    if sample <= 0:
        return Confidence.NONE
    if sample < SAMPLE_LOW:
        return Confidence.LOW
    if sample < SAMPLE_HIGH:
        return Confidence.MEDIUM
    return Confidence.HIGH


def wilson(successes: int, total: int, *, z: float = Z_95) -> Interval:
    """Intervalo de Wilson para uma proporção.

    Sem amostra devolve o intervalo inteiro [0, 1] com confiança ``NONE`` — o que
    é a verdade: não sabemos nada. Devolver 0 com intervalo zero seria afirmar
    que o candidato erra tudo, que é coisa bem diferente de não ter dados.
    """
    if total <= 0:
        return Interval(value=0.0, low=0.0, high=1.0, sample=0, confidence=Confidence.NONE)

    successes = max(0, min(successes, total))
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z / denominator * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
    )

    return Interval(
        value=round(proportion, 4),
        low=round(max(0.0, center - margin), 4),
        high=round(min(1.0, center + margin), 4),
        sample=total,
        confidence=confidence_for(total),
    )


@dataclass(frozen=True, slots=True)
class Component:
    """Uma parcela de um índice composto, com a incerteza que ela carrega."""

    key: str
    label: str
    weight: float
    interval: Interval | None
    #: Falso quando o sinal não tem amostra suficiente para entrar na conta.
    available: bool
    detail: str

    @property
    def points(self) -> float:
        return round((self.interval.value if self.interval else 0.0) * self.weight, 4)


@dataclass(frozen=True, slots=True)
class Composite:
    """Índice composto com faixa de incerteza propagada.

    A faixa **não** é um intervalo de confiança do composto no sentido estrito —
    é a propagação dos limites de cada parcela pelos respectivos pesos. A
    interface diz isso com essas palavras; chamar de "intervalo de confiança do
    Mestre Score" seria emprestar uma precisão que a conta não tem.
    """

    value: float
    low: float
    high: float
    components: list[Component] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    #: Peso dos sinais que existiam. Abaixo de 1,0 o índice foi reescalado.
    available_weight: float = 0.0
    confidence: str = Confidence.NONE

    @property
    def components_sum(self) -> float:
        return round(sum(item.points for item in self.components), 4)


#: Ordem crescente de confiança. Serve para responder "qual é o sinal mais frágil".
CONFIDENCE_ORDER: tuple[str, ...] = (
    Confidence.NONE,
    Confidence.LOW,
    Confidence.MEDIUM,
    Confidence.HIGH,
)


def weakest_confidence(levels: list[str]) -> str:
    """Um índice não é mais confiável do que a sua pior parcela."""
    if not levels:
        return Confidence.NONE
    return min(levels, key=lambda item: CONFIDENCE_ORDER.index(item))


def combine(components: list[Component]) -> Composite:
    """Combina parcelas em 0..1, reescalando pelo peso disponível.

    Sinal ausente **não** é penalidade: o índice é dividido pelo peso que de fato
    existia. Uma disciplina sem questões cadastradas não pode empurrar o número
    do candidato para baixo — ela só reduz a confiança, e isso é declarado.
    """
    available = [item for item in components if item.available and item.interval is not None]
    weight = round(sum(item.weight for item in available), 4)
    if weight <= 0:
        return Composite(
            value=0.0,
            low=0.0,
            high=1.0,
            components=components,
            missing=[item.key for item in components],
            available_weight=0.0,
            confidence=Confidence.NONE,
        )

    def _scaled(pick: str) -> float:
        total = sum(getattr(item.interval, pick) * item.weight for item in available)
        return round(total / weight, 4)

    # A confiança do composto é a do sinal mais frágil: um índice não é mais
    # confiável do que a sua pior parcela.
    weakest = weakest_confidence([item.interval.confidence for item in available if item.interval])

    return Composite(
        value=_scaled("value"),
        low=_scaled("low"),
        high=_scaled("high"),
        components=components,
        missing=[item.key for item in components if not item.available],
        available_weight=weight,
        confidence=weakest,
    )


def largest_remainder(raw: list[float], *, total: int) -> list[int]:
    """Arredonda mantendo a soma exatamente igual a ``total``.

    A mesma técnica do Priority Score e do rank: as parcelas exibidas precisam
    somar o número exibido, ou a tela vira uma conta que não fecha.
    """
    if not raw:
        return []
    scaled = [item * total for item in raw]
    floors = [int(item) for item in scaled]
    remainder = total - sum(floors)
    if remainder <= 0:
        return floors
    order = sorted(
        range(len(scaled)), key=lambda index: scaled[index] - floors[index], reverse=True
    )
    for index in order[:remainder]:
        floors[index] += 1
    return floors
