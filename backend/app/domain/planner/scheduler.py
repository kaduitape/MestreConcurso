"""Montagem da agenda: tarefas concretas em cada dia disponível."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from app.domain.planner.allocation import SubjectShare
from app.domain.planner.availability import DailyCapacity

MIN_TASK_MINUTES = 15
DEFAULT_BLOCK_MINUTES = 30
MAX_TASKS_PER_DAY = 6


class TaskKind(StrEnum):
    THEORY = "THEORY"
    QUESTIONS = "QUESTIONS"
    REVIEW = "REVIEW"
    FLASHCARDS = "FLASHCARDS"
    SIMULATION = "SIMULATION"
    SPRINT = "SPRINT"


# Divisão do tempo por tipo de atividade. Ajustável por plano; estes são os padrões.
DEFAULT_MIX: dict[str, float] = {
    TaskKind.THEORY: 0.45,
    TaskKind.QUESTIONS: 0.30,
    TaskKind.REVIEW: 0.20,
    TaskKind.FLASHCARDS: 0.05,
}

# Perto da prova o peso migra de teoria para questões e revisão (Reta Final, Fase 9,
# aprofunda isso; aqui já evitamos gastar os últimos dias em conteúdo novo).
FINAL_STRETCH_DAYS = 30
FINAL_STRETCH_MIX: dict[str, float] = {
    TaskKind.THEORY: 0.20,
    TaskKind.QUESTIONS: 0.45,
    TaskKind.REVIEW: 0.30,
    TaskKind.FLASHCARDS: 0.05,
}


@dataclass(frozen=True, slots=True)
class PlannedTask:
    day: date
    kind: str
    subject_key: str | None
    subject_name: str | None
    minutes: int
    order_index: int
    reason: dict[str, float | str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    tasks: list[PlannedTask]
    total_minutes: int
    study_days: int
    minutes_by_subject: dict[str, int]
    minutes_by_kind: dict[str, int]
    dropped_minutes: int = 0


def mix_for_day(day: date, exam_date: date | None, base_mix: dict[str, float]) -> dict[str, float]:
    """Composição do dia: conteúdo novo perde espaço à medida que a prova se aproxima."""
    if exam_date is None:
        return base_mix
    remaining = (exam_date - day).days
    if remaining <= FINAL_STRETCH_DAYS:
        return FINAL_STRETCH_MIX
    return base_mix


def _round_to_block(minutes: int) -> int:
    """Arredonda para blocos de 5 minutos, respeitando o mínimo."""
    if minutes < MIN_TASK_MINUTES:
        return 0
    return int(minutes // 5 * 5)


def build_schedule(
    *,
    calendar: list[DailyCapacity],
    shares: list[SubjectShare],
    exam_date: date | None = None,
    mix: dict[str, float] | None = None,
    max_tasks_per_day: int = MAX_TASKS_PER_DAY,
) -> ScheduleResult:
    """Distribui as disciplinas pelos dias, rotacionando para não repetir o mesmo par.

    O tempo de cada dia é dividido primeiro por tipo de atividade e depois entre as
    disciplinas da vez, sempre em blocos de no mínimo 15 minutos.
    """
    study_days = [day for day in calendar if day.is_study_day]
    if not study_days or not shares:
        return ScheduleResult([], 0, 0, {}, {})

    base_mix = mix or DEFAULT_MIX
    ordered = sorted(shares, key=lambda item: item.share, reverse=True)

    tasks: list[PlannedTask] = []
    minutes_by_subject: dict[str, int] = {share.key: 0 for share in ordered}
    minutes_by_kind: dict[str, int] = {}
    dropped = 0
    rotation = 0

    for capacity in study_days:
        day_mix = mix_for_day(capacity.day, exam_date, base_mix)
        remaining = capacity.minutes
        order_index = 0

        for kind, fraction in day_mix.items():
            kind_minutes = _round_to_block(int(capacity.minutes * fraction))
            if kind_minutes <= 0 or remaining < MIN_TASK_MINUTES:
                continue
            kind_minutes = min(kind_minutes, remaining)

            # Flashcards e revisão não pertencem a uma disciplina específica no
            # baseline: viram tarefas gerais até haver histórico (Fases 6 e 8).
            if kind in {TaskKind.FLASHCARDS, TaskKind.REVIEW}:
                tasks.append(
                    PlannedTask(
                        day=capacity.day,
                        kind=kind,
                        subject_key=None,
                        subject_name=None,
                        minutes=kind_minutes,
                        order_index=order_index,
                        reason={"motivo": "bloco fixo de consolidação do plano"},
                    )
                )
                minutes_by_kind[kind] = minutes_by_kind.get(kind, 0) + kind_minutes
                remaining -= kind_minutes
                order_index += 1
                continue

            slots = min(2, max(1, max_tasks_per_day - order_index))
            per_slot = _round_to_block(kind_minutes // slots)
            if per_slot <= 0:
                per_slot = kind_minutes

            for _ in range(slots):
                if remaining < MIN_TASK_MINUTES or order_index >= max_tasks_per_day:
                    break
                share = ordered[rotation % len(ordered)]
                rotation += 1
                block = min(per_slot, remaining)
                if block < MIN_TASK_MINUTES:
                    break

                tasks.append(
                    PlannedTask(
                        day=capacity.day,
                        kind=kind,
                        subject_key=share.key,
                        subject_name=share.name,
                        minutes=block,
                        order_index=order_index,
                        reason={
                            "participacao_no_plano": round(share.share, 4),
                            **share.breakdown,
                        },
                    )
                )
                minutes_by_subject[share.key] += block
                minutes_by_kind[kind] = minutes_by_kind.get(kind, 0) + block
                remaining -= block
                order_index += 1

        dropped += remaining

    return ScheduleResult(
        tasks=tasks,
        total_minutes=sum(task.minutes for task in tasks),
        study_days=len({task.day for task in tasks}),
        minutes_by_subject=minutes_by_subject,
        minutes_by_kind=minutes_by_kind,
        dropped_minutes=dropped,
    )
