"""Rank: o retrato do **desempenho real**, não do acúmulo.

XP não entra nesta conta. Um candidato pode ter muito XP e rank baixo — significa
que estudou bastante e ainda não domina; é exatamente essa distinção que o rank
existe para mostrar. E o rank **pode cair**: um número que só sobe não mede nada.

Como no Priority Score da Fase 6, **sinal sem amostra vale zero e é declarado**.
Candidato novo é FERRO porque ainda não há o que medir, não porque é ruim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Pesos da fórmula. Somam 1,0.
WEIGHT_ACCURACY = 0.30
WEIGHT_RETENTION = 0.25
WEIGHT_COVERAGE = 0.20
WEIGHT_SIMULATIONS = 0.15
WEIGHT_CONSISTENCY = 0.10

# Amostra mínima de cada sinal.
MIN_ATTEMPTS = 30
MIN_REVIEWS = 20
MIN_SIMULATIONS = 1
MIN_ACTIVE_DAYS = 7
CONSISTENCY_WINDOW = 30

LABELS: dict[str, str] = {
    "acerto": "Taxa de acerto",
    "retencao": "Retenção na revisão",
    "cobertura": "Cobertura do edital",
    "simulados": "Desempenho em simulados",
    "consistencia": "Consistência de estudo",
}


@dataclass(frozen=True, slots=True)
class RankTier:
    slug: str
    name: str
    min_score: float
    color_token: str


TIERS: tuple[RankTier, ...] = (
    RankTier("FERRO", "Ferro", 0.00, "rank-ferro"),
    RankTier("BRONZE", "Bronze", 0.30, "rank-bronze"),
    RankTier("PRATA", "Prata", 0.45, "rank-prata"),
    RankTier("OURO", "Ouro", 0.58, "rank-ouro"),
    RankTier("PLATINA", "Platina", 0.68, "rank-platina"),
    RankTier("DIAMANTE", "Diamante", 0.78, "rank-diamante"),
    RankTier("MESTRE", "Mestre", 0.86, "rank-mestre"),
    RankTier("GRAO_MESTRE", "Grão-Mestre", 0.93, "rank-grao-mestre"),
)


@dataclass(frozen=True, slots=True)
class RankInput:
    """Sinais reais do candidato. ``None`` significa **ausente**, não zero."""

    accuracy: float | None = None
    attempts: int = 0
    retention: float | None = None
    reviews: int = 0
    coverage: float | None = None
    simulation_accuracy: float | None = None
    simulations: int = 0
    active_days: int = 0
    has_plan: bool = False


@dataclass(frozen=True, slots=True)
class RankComponent:
    key: str
    label: str
    weight: float
    value: float | None
    points: float
    available: bool
    detail: str


@dataclass(frozen=True, slots=True)
class RankResult:
    slug: str
    name: str
    color_token: str
    score: float
    components: list[RankComponent] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    coverage: float = 0.0
    next_tier: RankTier | None = None
    progress_to_next: float = 0.0

    @property
    def components_sum(self) -> float:
        return round(sum(item.points for item in self.components), 4)


def _component(
    key: str, weight: float, value: float | None, available: bool, detail: str
) -> RankComponent:
    points = round((value or 0.0) * weight, 4) if available else 0.0
    return RankComponent(
        key=key,
        label=LABELS[key],
        weight=weight,
        value=value if available else None,
        points=points,
        available=available,
        detail=detail,
    )


def tier_for(score: float) -> RankTier:
    current = TIERS[0]
    for tier in TIERS:
        if score >= tier.min_score:
            current = tier
    return current


def compute_rank(data: RankInput) -> RankResult:
    """Calcula o rank e devolve as contribuições que somam o score exibido."""
    components: list[RankComponent] = []
    missing: list[str] = []

    ok = data.accuracy is not None and data.attempts >= MIN_ATTEMPTS
    if not ok:
        missing.append("acerto")
    components.append(
        _component(
            "acerto",
            WEIGHT_ACCURACY,
            data.accuracy,
            ok,
            f"{data.accuracy * 100:.1f}% em {data.attempts} respostas"
            if ok and data.accuracy is not None
            else f"{data.attempts} de {MIN_ATTEMPTS} respostas para entrar na conta",
        )
    )

    ok = data.retention is not None and data.reviews >= MIN_REVIEWS
    if not ok:
        missing.append("retencao")
    components.append(
        _component(
            "retencao",
            WEIGHT_RETENTION,
            data.retention,
            ok,
            f"{data.retention * 100:.1f}% de recordação em {data.reviews} revisões"
            if ok and data.retention is not None
            else f"{data.reviews} de {MIN_REVIEWS} revisões para entrar na conta",
        )
    )

    ok = data.coverage is not None and data.has_plan
    if not ok:
        missing.append("cobertura")
    components.append(
        _component(
            "cobertura",
            WEIGHT_COVERAGE,
            data.coverage,
            ok,
            f"{data.coverage * 100:.1f}% do plano cumprido"
            if ok and data.coverage is not None
            else "sem plano de estudo ativo para medir cobertura",
        )
    )

    ok = data.simulation_accuracy is not None and data.simulations >= MIN_SIMULATIONS
    if not ok:
        missing.append("simulados")
    components.append(
        _component(
            "simulados",
            WEIGHT_SIMULATIONS,
            data.simulation_accuracy,
            ok,
            f"{data.simulation_accuracy * 100:.1f}% de média em {data.simulations} simulado(s)"
            if ok and data.simulation_accuracy is not None
            else "nenhum simulado concluído ainda",
        )
    )

    ok = data.active_days >= MIN_ACTIVE_DAYS
    consistency = min(1.0, data.active_days / CONSISTENCY_WINDOW) if ok else None
    if not ok:
        missing.append("consistencia")
    components.append(
        _component(
            "consistencia",
            WEIGHT_CONSISTENCY,
            consistency,
            ok,
            f"{data.active_days} dias ativos nos últimos {CONSISTENCY_WINDOW}"
            if ok
            else f"{data.active_days} de {MIN_ACTIVE_DAYS} dias ativos para entrar na conta",
        )
    )

    score = round(sum(item.points for item in components), 4)
    tier = tier_for(score)
    following = next((item for item in TIERS if item.min_score > tier.min_score), None)

    progress = 0.0
    if following is not None:
        span = following.min_score - tier.min_score
        progress = round(min(1.0, max(0.0, (score - tier.min_score) / span)), 4) if span else 0.0

    return RankResult(
        slug=tier.slug,
        name=tier.name,
        color_token=tier.color_token,
        score=score,
        components=components,
        missing_signals=missing,
        coverage=round((len(components) - len(missing)) / len(components), 3),
        next_tier=following,
        progress_to_next=progress,
    )
