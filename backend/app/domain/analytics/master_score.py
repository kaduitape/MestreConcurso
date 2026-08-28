"""Mestre Score — a medida de competência real, de 0 a 1000.

Três coisas que este número **não** é, e que a interface repete:

1. Não é XP. Nenhum ponto de gamificação entra aqui; ``MasterScoreInput`` não
   tem sequer um campo para isso, de modo que a separação é estrutural e não
   depende de ninguém lembrar dela.
2. Não é probabilidade de aprovação. Ele mede o que o candidato domina hoje, no
   material que existe — não o que vai acontecer numa prova.
3. Não é um número exato. Ele vem com **faixa**, e a faixa aparece na tela do
   lado do valor, sempre.

O score pode cair. Um índice de competência que só sobe não mede competência:
mede tempo de cadastro.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.analytics.statistics import (
    Component,
    Composite,
    Confidence,
    Interval,
    combine,
    largest_remainder,
    wilson,
)

SCALE = 1000

# Pesos. Somam 1,0.
WEIGHT_ACCURACY = 0.30
WEIGHT_RETENTION = 0.20
WEIGHT_COVERAGE = 0.25
WEIGHT_SIMULATIONS = 0.15
WEIGHT_CONSISTENCY = 0.10

# Amostras mínimas de cada sinal.
MIN_ATTEMPTS = 30
MIN_REVIEWS = 20
MIN_SIMULATION_QUESTIONS = 20
MIN_ACTIVE_DAYS = 7
CONSISTENCY_WINDOW = 30

LABELS: dict[str, str] = {
    "acerto": "Acerto em questões",
    "retencao": "Retenção na revisão",
    "cobertura": "Cobertura do edital",
    "simulados": "Desempenho em simulados",
    "consistencia": "Consistência de estudo",
}

# Faixas de leitura. Existem para dar sentido ao número, não para premiar.
BANDS: tuple[tuple[int, str, str], ...] = (
    (0, "Início", "Ainda há pouco material medido."),
    (250, "Em formação", "A base está sendo construída."),
    (450, "Consolidando", "O conteúdo já responde, com pontos frágeis claros."),
    (650, "Avançado", "Desempenho consistente na maior parte do edital."),
    (820, "Domínio", "Poucos pontos frágeis, e todos identificados."),
)


@dataclass(frozen=True, slots=True)
class MasterScoreInput:
    """Sinais reais. Não existe campo de XP aqui — de propósito."""

    correct: int = 0
    attempts: int = 0
    recalled: int = 0
    reviews: int = 0
    #: Cobertura vem do plano (0..1) e não é proporção amostral.
    coverage: float | None = None
    covered_minutes: int = 0
    planned_minutes: int = 0
    simulation_correct: int = 0
    simulation_questions: int = 0
    active_days: int = 0
    has_plan: bool = False


@dataclass(frozen=True, slots=True)
class ScoreComponent:
    key: str
    label: str
    weight: float
    #: Pontos na escala de 0 a 1000. Somam exatamente o score exibido.
    points: int
    value: float | None
    low: float | None
    high: float | None
    sample: int
    available: bool
    confidence: str
    detail: str


@dataclass(frozen=True, slots=True)
class MasterScore:
    value: int
    low: int
    high: int
    band: str
    band_note: str
    confidence: str
    #: Peso dos sinais que existiam (0..1). Abaixo de 1 o índice foi reescalado.
    available_weight: float
    components: list[ScoreComponent] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    #: O que a faixa é, em uma frase — para a tela não precisar inventar.
    interval_note: str = (
        "A faixa é a propagação do intervalo de Wilson (95%) de cada sinal pelos "
        "respectivos pesos. Não é uma previsão, e não é probabilidade de aprovação."
    )
    empty_reason: str | None = None

    @property
    def components_sum(self) -> int:
        return sum(item.points for item in self.components)


def band_for(value: int) -> tuple[str, str]:
    label, note = BANDS[0][1], BANDS[0][2]
    for threshold, name, description in BANDS:
        if value >= threshold:
            label, note = name, description
    return label, note


def _ratio_interval(value: float | None) -> Interval | None:
    """Cobertura não é proporção amostral: entra sem incerteza estatística.

    Ela é uma razão exata entre minutos cumpridos e planejados. Fabricar um
    intervalo para ela só para "ficar uniforme" seria inventar incerteza.
    """
    if value is None:
        return None
    bounded = min(1.0, max(0.0, value))
    return Interval(
        value=round(bounded, 4),
        low=round(bounded, 4),
        high=round(bounded, 4),
        sample=1,
        confidence=Confidence.HIGH,
    )


def _build_components(data: MasterScoreInput) -> list[Component]:
    components: list[Component] = []

    ok = data.attempts >= MIN_ATTEMPTS
    interval = wilson(data.correct, data.attempts) if ok else None
    components.append(
        Component(
            key="acerto",
            label=LABELS["acerto"],
            weight=WEIGHT_ACCURACY,
            interval=interval,
            available=ok,
            detail=(
                f"{interval.value * 100:.1f}% em {data.attempts} respostas "
                f"(faixa {interval.low * 100:.0f}–{interval.high * 100:.0f}%)"
                if ok and interval
                else f"{data.attempts} de {MIN_ATTEMPTS} respostas para entrar na conta"
            ),
        )
    )

    ok = data.reviews >= MIN_REVIEWS
    interval = wilson(data.recalled, data.reviews) if ok else None
    components.append(
        Component(
            key="retencao",
            label=LABELS["retencao"],
            weight=WEIGHT_RETENTION,
            interval=interval,
            available=ok,
            detail=(
                f"{interval.value * 100:.1f}% em {data.reviews} revisões "
                f"(faixa {interval.low * 100:.0f}–{interval.high * 100:.0f}%)"
                if ok and interval
                else f"{data.reviews} de {MIN_REVIEWS} revisões para entrar na conta"
            ),
        )
    )

    ok = data.has_plan and data.coverage is not None
    interval = _ratio_interval(data.coverage) if ok else None
    components.append(
        Component(
            key="cobertura",
            label=LABELS["cobertura"],
            weight=WEIGHT_COVERAGE,
            interval=interval,
            available=ok,
            detail=(
                f"{interval.value * 100:.1f}% dos {data.planned_minutes} minutos planejados"
                if ok and interval
                else "sem plano de estudo ativo para medir cobertura"
            ),
        )
    )

    ok = data.simulation_questions >= MIN_SIMULATION_QUESTIONS
    interval = wilson(data.simulation_correct, data.simulation_questions) if ok else None
    components.append(
        Component(
            key="simulados",
            label=LABELS["simulados"],
            weight=WEIGHT_SIMULATIONS,
            interval=interval,
            available=ok,
            detail=(
                f"{interval.value * 100:.1f}% em {data.simulation_questions} questões de simulado"
                if ok and interval
                else (
                    f"{data.simulation_questions} de {MIN_SIMULATION_QUESTIONS} questões de "
                    "simulado para entrar na conta"
                )
            ),
        )
    )

    ok = data.active_days >= MIN_ACTIVE_DAYS
    consistency = min(1.0, data.active_days / CONSISTENCY_WINDOW) if ok else None
    components.append(
        Component(
            key="consistencia",
            label=LABELS["consistencia"],
            weight=WEIGHT_CONSISTENCY,
            interval=_ratio_interval(consistency) if ok else None,
            available=ok,
            detail=(
                f"{data.active_days} dias ativos nos últimos {CONSISTENCY_WINDOW}"
                if ok
                else f"{data.active_days} de {MIN_ACTIVE_DAYS} dias ativos para entrar na conta"
            ),
        )
    )

    return components


def compute(data: MasterScoreInput) -> MasterScore:
    """Calcula o Mestre Score, a faixa e as parcelas que somam o valor exibido."""
    components = _build_components(data)
    composite: Composite = combine(components)

    if composite.available_weight <= 0:
        return MasterScore(
            value=0,
            low=0,
            high=0,
            band=BANDS[0][1],
            band_note=BANDS[0][2],
            confidence=Confidence.NONE,
            available_weight=0.0,
            components=[
                ScoreComponent(
                    key=item.key,
                    label=item.label,
                    weight=item.weight,
                    points=0,
                    value=None,
                    low=None,
                    high=None,
                    sample=0,
                    available=False,
                    confidence=Confidence.NONE,
                    detail=item.detail,
                )
                for item in components
            ],
            missing_signals=[item.key for item in components],
            empty_reason=(
                "Ainda não há dados suficientes para medir competência. O Mestre Score "
                "aparece quando algum sinal alcança a amostra mínima — e cada sinal diz "
                "quanto falta."
            ),
        )

    value = round(composite.value * SCALE)
    low = round(composite.low * SCALE)
    high = round(composite.high * SCALE)

    # As parcelas exibidas precisam somar o valor exibido.
    available = [item for item in components if item.available and item.interval is not None]
    shares = [
        (item.interval.value * item.weight) / (composite.value * composite.available_weight)
        if composite.value > 0 and item.interval
        else 0.0
        for item in available
    ]
    points = largest_remainder(shares, total=value) if sum(shares) > 0 else [0] * len(available)
    by_key = dict(zip([item.key for item in available], points, strict=True))

    band, note = band_for(value)
    return MasterScore(
        value=value,
        low=low,
        high=high,
        band=band,
        band_note=note,
        confidence=composite.confidence,
        available_weight=composite.available_weight,
        components=[
            ScoreComponent(
                key=item.key,
                label=item.label,
                weight=item.weight,
                points=by_key.get(item.key, 0),
                value=item.interval.value if item.interval else None,
                low=item.interval.low if item.interval else None,
                high=item.interval.high if item.interval else None,
                sample=item.interval.sample if item.interval else 0,
                available=item.available,
                confidence=item.interval.confidence if item.interval else Confidence.NONE,
                detail=item.detail,
            )
            for item in components
        ],
        missing_signals=composite.missing,
    )
