"""Jornada da Aprovação — onde o candidato está, medido pelo que ele fez.

Cada marco tem um **critério verificável**. Nada aqui é opinião sobre a chance de
aprovação: os marcos medem cobertura e desempenho, e a interface diz isso em voz
alta. Prometer aprovação seria a mentira mais cara que esta plataforma poderia
contar — o candidato reorganiza a vida em cima dela.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# O aviso que acompanha a jornada em toda tela onde ela aparece.
DISCLAIMER = (
    "Os marcos medem cobertura e desempenho no seu material. Não são previsão de "
    "aprovação, e nenhum número aqui diz se você vai passar."
)


class MilestoneState(StrEnum):
    DONE = "DONE"
    CURRENT = "CURRENT"
    PENDING = "PENDING"


@dataclass(frozen=True, slots=True)
class JourneyInput:
    """Sinais reais. ``None`` significa ausente, não zero."""

    study_sessions: int = 0
    questions_answered: int = 0
    simulations_finished: int = 0
    coverage: float | None = None
    days_until_exam: int | None = None
    has_plan: bool = False


@dataclass(frozen=True, slots=True)
class Milestone:
    key: str
    label: str
    description: str
    state: str
    current: float
    target: float
    ratio: float
    detail: str


@dataclass(frozen=True, slots=True)
class Journey:
    milestones: list[Milestone] = field(default_factory=list)
    current_key: str | None = None
    completed: int = 0
    total: int = 0
    days_until_exam: int | None = None
    disclaimer: str = DISCLAIMER
    empty_reason: str | None = None


def _milestone(
    key: str, label: str, description: str, current: float, target: float, unit: str
) -> tuple[str, str, str, float, float, str]:
    detail = (
        f"{round(current)} de {round(target)} {unit}" if target > 1 else f"{round(current)} {unit}"
    )
    return key, label, description, current, target, detail


def build_journey(data: JourneyInput) -> Journey:
    """Monta a trilha a partir dos números reais do candidato."""
    if not data.has_plan:
        return Journey(
            empty_reason=(
                "A jornada é traçada sobre o seu plano de estudo. Monte o plano para que os "
                "marcos passem a medir alguma coisa."
            ),
        )

    coverage = data.coverage or 0.0
    raw = [
        _milestone(
            "first_study",
            "Primeiro estudo",
            "Uma sessão de estudo com foco registrada.",
            data.study_sessions,
            1,
            "sessão",
        ),
        _milestone(
            "hundred_questions",
            "100 questões",
            "Volume mínimo para o seu desempenho começar a significar algo.",
            data.questions_answered,
            100,
            "questões",
        ),
        _milestone(
            "coverage_25",
            "25% do edital",
            "Um quarto do tempo planejado já cumprido.",
            coverage * 100,
            25,
            "% de cobertura",
        ),
        _milestone(
            "first_simulation",
            "Primeiro simulado",
            "Uma prova completa, com correção e comparação.",
            data.simulations_finished,
            1,
            "simulado",
        ),
        _milestone(
            "coverage_50",
            "50% do edital",
            "Metade do plano cumprida.",
            coverage * 100,
            50,
            "% de cobertura",
        ),
        _milestone(
            "coverage_70",
            "70% do edital",
            "A maior parte do conteúdo já passou pelo menos uma vez.",
            coverage * 100,
            70,
            "% de cobertura",
        ),
        _milestone(
            "final_stretch",
            "Reta final",
            "Últimos 30 dias: revisão e questões acima de teoria nova.",
            float(max(0, 30 - (data.days_until_exam if data.days_until_exam is not None else 999))),
            30,
            "dias dentro da reta final",
        ),
    ]

    milestones: list[Milestone] = []
    current_key: str | None = None
    for key, label, description, current, target, detail in raw:
        reached = current >= target
        state = MilestoneState.DONE if reached else MilestoneState.PENDING
        if not reached and current_key is None:
            state = MilestoneState.CURRENT
            current_key = key
        milestones.append(
            Milestone(
                key=key,
                label=label,
                description=description,
                state=state,
                current=round(current, 2),
                target=float(target),
                ratio=round(min(1.0, current / target), 4) if target else 0.0,
                detail=detail,
            )
        )

    return Journey(
        milestones=milestones,
        current_key=current_key,
        completed=len([item for item in milestones if item.state == MilestoneState.DONE]),
        total=len(milestones),
        days_until_exam=data.days_until_exam,
    )
