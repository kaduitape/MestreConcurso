"""Mapa do Edital — cada disciplina como um território, com o estado real dela.

O "domínio" de um território não é uma nota inventada: é a combinação de quanto
do tempo planejado foi cumprido (cobertura), quanto o candidato acerta ali
(desempenho) e quanto ele retém (revisão). Cada parte só entra com amostra.

O estado mais importante do mapa é **REVISAO_NECESSARIA**: uma disciplina que já
foi dominada e está sendo esquecida parece verde num gráfico de cobertura, e é
justamente onde a preparação costuma vazar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# Pesos do domínio. Somam 1,0.
WEIGHT_COVERAGE = 0.4
WEIGHT_ACCURACY = 0.4
WEIGHT_RETENTION = 0.2

MIN_ANSWERS = 20
MIN_REVIEWS = 10

# Fronteiras dos estados.
MASTERED_THRESHOLD = 0.75
STUDYING_THRESHOLD = 0.25
# Dias sem tocar numa disciplina já coberta antes de ela pedir revisão.
STALE_DAYS = 21


class TerritoryState(StrEnum):
    LOCKED = "LOCKED"  # no plano, ainda não começou
    STARTED = "STARTED"  # primeiros minutos
    STUDYING = "STUDYING"  # em andamento
    MASTERED = "MASTERED"  # domínio alto
    NEEDS_REVIEW = "NEEDS_REVIEW"  # coberto, mas esfriando


@dataclass(frozen=True, slots=True)
class TerritoryInput:
    subject_key: str
    subject_name: str
    color_token: str = "subject-especifica"
    subject_id: int | None = None
    coverage: float = 0.0
    planned_minutes: int = 0
    studied_minutes: int = 0
    accuracy: float | None = None
    answers: int = 0
    retention: float | None = None
    reviews: int = 0
    days_since_studied: int | None = None


@dataclass(frozen=True, slots=True)
class TerritoryPart:
    key: str
    label: str
    weight: float
    value: float | None
    points: float
    available: bool
    detail: str


@dataclass(frozen=True, slots=True)
class Territory:
    subject_key: str
    subject_name: str
    color_token: str
    subject_id: int | None
    state: str
    mastery: float
    parts: list[TerritoryPart] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    studied_minutes: int = 0
    planned_minutes: int = 0
    days_since_studied: int | None = None
    note: str = ""

    @property
    def parts_sum(self) -> float:
        return round(sum(item.points for item in self.parts), 4)


LABELS = {
    "cobertura": "Tempo planejado cumprido",
    "desempenho": "Acerto na disciplina",
    "retencao": "Retenção na revisão",
}


def _part(
    key: str, weight: float, value: float | None, available: bool, detail: str
) -> TerritoryPart:
    return TerritoryPart(
        key=key,
        label=LABELS[key],
        weight=weight,
        value=value if available else None,
        points=round((value or 0.0) * weight, 4) if available else 0.0,
        available=available,
        detail=detail,
    )


def _state_for(item: TerritoryInput, mastery: float) -> tuple[str, str]:
    if item.studied_minutes <= 0:
        return TerritoryState.LOCKED, "Ainda não estudada neste plano."

    stale = item.days_since_studied is not None and item.days_since_studied >= STALE_DAYS
    if mastery >= MASTERED_THRESHOLD:
        if stale:
            return TerritoryState.NEEDS_REVIEW, (
                f"Dominada, mas sem revisão há {item.days_since_studied} dias. "
                "Domínio alto esfria em silêncio."
            )
        return TerritoryState.MASTERED, "Domínio consolidado."

    if stale and mastery >= STUDYING_THRESHOLD:
        return TerritoryState.NEEDS_REVIEW, (
            f"Sem estudo há {item.days_since_studied} dias — o que já foi coberto começa a "
            "se perder."
        )

    if mastery >= STUDYING_THRESHOLD:
        return TerritoryState.STUDYING, "Em andamento."

    return TerritoryState.STARTED, "Começou há pouco."


def build_territory(item: TerritoryInput) -> Territory:
    """Calcula o domínio de uma disciplina e o estado do território."""
    parts: list[TerritoryPart] = []
    missing: list[str] = []

    coverage = min(1.0, max(0.0, item.coverage))
    parts.append(
        _part(
            "cobertura",
            WEIGHT_COVERAGE,
            coverage,
            True,
            f"{coverage * 100:.0f}% dos {item.planned_minutes} minutos planejados",
        )
    )

    accuracy_ok = item.accuracy is not None and item.answers >= MIN_ANSWERS
    if not accuracy_ok:
        missing.append("desempenho")
    parts.append(
        _part(
            "desempenho",
            WEIGHT_ACCURACY,
            item.accuracy,
            accuracy_ok,
            f"{item.accuracy * 100:.0f}% em {item.answers} respostas"
            if accuracy_ok and item.accuracy is not None
            else f"{item.answers} de {MIN_ANSWERS} respostas para entrar na conta",
        )
    )

    retention_ok = item.retention is not None and item.reviews >= MIN_REVIEWS
    if not retention_ok:
        missing.append("retencao")
    parts.append(
        _part(
            "retencao",
            WEIGHT_RETENTION,
            item.retention,
            retention_ok,
            f"{item.retention * 100:.0f}% de recordação em {item.reviews} revisões"
            if retention_ok and item.retention is not None
            else f"{item.reviews} de {MIN_REVIEWS} revisões para entrar na conta",
        )
    )

    # Sinal ausente não é penalidade: o domínio é reescalado pelo peso disponível,
    # para que uma disciplina sem questões cadastradas não pareça abandonada.
    available_weight = sum(part.weight for part in parts if part.available)
    raw = sum(part.points for part in parts)
    mastery = round(raw / available_weight, 4) if available_weight else 0.0

    state, note = _state_for(item, mastery)
    return Territory(
        subject_key=item.subject_key,
        subject_name=item.subject_name,
        color_token=item.color_token,
        subject_id=item.subject_id,
        state=state,
        mastery=mastery,
        parts=parts,
        missing_signals=missing,
        studied_minutes=item.studied_minutes,
        planned_minutes=item.planned_minutes,
        days_since_studied=item.days_since_studied,
        note=note,
    )


def build_map(items: list[TerritoryInput]) -> list[Territory]:
    """Monta o mapa inteiro, do território mais frágil ao mais consolidado."""
    territories = [build_territory(item) for item in items]
    order: dict[str, int] = {
        TerritoryState.NEEDS_REVIEW: 0,
        TerritoryState.STARTED: 1,
        TerritoryState.STUDYING: 2,
        TerritoryState.LOCKED: 3,
        TerritoryState.MASTERED: 4,
    }
    territories.sort(key=lambda item: (order[item.state], item.mastery, item.subject_name))
    return territories
