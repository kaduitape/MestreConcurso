"""Replanejamento quando o candidato perde dias.

Regra do produto: o plano **nunca** vira uma pilha infinita de atrasos. O que não
foi feito volta para a fila com prioridade, mas cada dia tem um teto — o que não
couber até a prova é declarado como removido, e não escondido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.planner.availability import DailyCapacity
from app.domain.planner.scheduler import MIN_TASK_MINUTES, PlannedTask

# Um dia pode absorver no máximo 20% além da disponibilidade declarada.
OVERLOAD_TOLERANCE = 0.20
# Cada vez que uma tarefa é remarcada ela perde tempo: repetir sem fim não ajuda.
CARRY_OVER_DECAY = 0.7
MAX_RESCHEDULES = 2


@dataclass(frozen=True, slots=True)
class PendingTask:
    """Tarefa não realizada que volta para a fila."""

    kind: str
    subject_key: str | None
    subject_name: str | None
    minutes: int
    original_day: date
    reschedule_count: int = 0
    reason: dict[str, float | str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RebalanceResult:
    rescheduled: list[PlannedTask]
    dropped: list[PendingTask]
    dropped_minutes: int
    days_touched: int

    @property
    def summary(self) -> str:
        if not self.dropped:
            return f"{len(self.rescheduled)} tarefa(s) remarcada(s)."
        return (
            f"{len(self.rescheduled)} tarefa(s) remarcada(s) e {len(self.dropped)} "
            f"removida(s) do plano por falta de tempo até a prova."
        )


def rebalance(
    *,
    pending: list[PendingTask],
    calendar: list[DailyCapacity],
    committed_minutes: dict[date, int],
    today: date,
) -> RebalanceResult:
    """Redistribui o que ficou para trás pelos dias que ainda existem.

    ``committed_minutes`` traz o que já está agendado em cada dia; o rebalanceamento
    só ocupa a folga, respeitando a tolerância de sobrecarga.
    """
    future_days = [day for day in calendar if day.day > today and day.is_study_day]
    if not future_days:
        return RebalanceResult([], list(pending), sum(item.minutes for item in pending), 0)

    # Mais antigas primeiro; entre iguais, a de maior duração.
    queue = sorted(pending, key=lambda item: (item.original_day, -item.minutes))

    capacity: dict[date, int] = {}
    for day in future_days:
        limit = int(day.minutes * (1 + OVERLOAD_TOLERANCE))
        capacity[day.day] = max(0, limit - committed_minutes.get(day.day, 0))

    rescheduled: list[PlannedTask] = []
    dropped: list[PendingTask] = []
    order_by_day: dict[date, int] = {}

    for task in queue:
        if task.reschedule_count >= MAX_RESCHEDULES:
            # Já foi adiada demais: insistir só empurra o problema adiante.
            dropped.append(task)
            continue

        minutes = int(task.minutes * (CARRY_OVER_DECAY**task.reschedule_count))
        minutes = minutes // 5 * 5
        if minutes < MIN_TASK_MINUTES:
            dropped.append(task)
            continue

        placed = False
        for day in future_days:
            if capacity[day.day] >= minutes:
                order = order_by_day.get(day.day, 0)
                rescheduled.append(
                    PlannedTask(
                        day=day.day,
                        kind=task.kind,
                        subject_key=task.subject_key,
                        subject_name=task.subject_name,
                        minutes=minutes,
                        order_index=order,
                        reason={
                            **task.reason,
                            "remarcada_de": task.original_day.isoformat(),
                            "tentativa": task.reschedule_count + 1,
                        },
                    )
                )
                capacity[day.day] -= minutes
                order_by_day[day.day] = order + 1
                placed = True
                break

        if not placed:
            dropped.append(task)

    return RebalanceResult(
        rescheduled=rescheduled,
        dropped=dropped,
        dropped_minutes=sum(item.minutes for item in dropped),
        days_touched=len({task.day for task in rescheduled}),
    )
