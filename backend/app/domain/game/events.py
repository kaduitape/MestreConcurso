"""Eventos especiais: janelas curtas com meta declarada e prêmio de utilidade.

Um evento é um período com **metas medidas nos mesmos números do resto da
plataforma** — minutos de foco, questões respondidas, revisões, desafios. Não há
métrica exclusiva de evento, porque uma métrica que só existe dentro do evento
seria um número inventado para gerar urgência.

Prêmio de evento segue a regra da temporada: critério verificável e utilidade
escrita. E, como tudo aqui, **não desbloqueia conteúdo de estudo**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# As únicas métricas que um evento pode cobrar. A lista é fechada de propósito.
EVENT_METRICS: dict[str, str] = {
    "focus_minutes": "Minutos de estudo com foco",
    "questions": "Questões respondidas",
    "reviews": "Flashcards revisados",
    "challenges": "Rodadas de desafio concluídas",
    "qualified_days": "Dias qualificados",
}


@dataclass(frozen=True, slots=True)
class EventGoal:
    metric: str
    target: int

    @property
    def label(self) -> str:
        return EVENT_METRICS.get(self.metric, self.metric)


@dataclass(frozen=True, slots=True)
class GoalProgress:
    metric: str
    label: str
    current: int
    target: int
    ratio: float
    completed: bool


@dataclass(frozen=True, slots=True)
class EventProgress:
    goals: list[GoalProgress] = field(default_factory=list)
    completed: bool = False
    completed_goals: int = 0
    total_goals: int = 0
    days_left: int | None = None
    is_open: bool = True
    #: Nulo quando o evento não define prêmio.
    reward_label: str | None = None
    reward_utility: str | None = None
    note: str = (
        "Eventos medem atividade no período com os mesmos números do restante da "
        "plataforma. Participar é opcional e não altera o seu rank."
    )


def validate_goals(goals: list[EventGoal]) -> list[str]:
    errors: list[str] = []
    if not goals:
        errors.append("Um evento precisa de pelo menos uma meta.")
    for goal in goals:
        if goal.metric not in EVENT_METRICS:
            errors.append(
                f"Métrica desconhecida: {goal.metric}. "
                f"As aceitas são {', '.join(sorted(EVENT_METRICS))}."
            )
        if goal.target <= 0:
            errors.append(f"A meta de {goal.label.lower()} precisa ser maior que zero.")
    return errors


def evaluate(
    goals: list[EventGoal],
    metrics: dict[str, int],
    *,
    starts_on: date | None = None,
    ends_on: date | None = None,
    today: date | None = None,
    reward_label: str | None = None,
    reward_utility: str | None = None,
) -> EventProgress:
    """Mede o progresso do candidato no evento a partir de números reais."""
    progress: list[GoalProgress] = []
    for goal in goals:
        current = int(metrics.get(goal.metric, 0))
        progress.append(
            GoalProgress(
                metric=goal.metric,
                label=goal.label,
                current=current,
                target=goal.target,
                ratio=round(min(1.0, current / goal.target), 4) if goal.target else 0.0,
                completed=current >= goal.target,
            )
        )

    done = len([item for item in progress if item.completed])
    days_left = None
    is_open = True
    if ends_on is not None and today is not None:
        days_left = max(0, (ends_on - today).days)
        is_open = (starts_on is None or today >= starts_on) and today <= ends_on

    return EventProgress(
        goals=progress,
        # Evento só é cumprido com **todas** as metas atingidas.
        completed=bool(progress) and done == len(progress),
        completed_goals=done,
        total_goals=len(progress),
        days_left=days_left,
        is_open=is_open,
        reward_label=reward_label,
        reward_utility=reward_utility,
    )
