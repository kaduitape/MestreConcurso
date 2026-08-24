"""Planejador de estudos — regras puras, sem banco e sem IA.

Este pacote decide *o que* estudar e *quando*, a partir de números: peso da
disciplina no edital, quantidade de questões, extensão do conteúdo, tempo
disponível e dias restantes. A IA não participa dessas contas — ela entra nas
fases seguintes para explicar e personalizar o que já foi decidido aqui.
"""

from app.domain.planner.allocation import (
    SubjectInput,
    SubjectShare,
    allocate_subject_shares,
)
from app.domain.planner.availability import (
    DailyCapacity,
    WeeklyAvailability,
    build_calendar,
)
from app.domain.planner.rebalance import RebalanceResult, rebalance
from app.domain.planner.scheduler import PlannedTask, ScheduleResult, build_schedule
from app.domain.planner.sprint import SprintBlock, SprintPlan, build_sprint

__all__ = [
    "DailyCapacity",
    "PlannedTask",
    "RebalanceResult",
    "ScheduleResult",
    "SprintBlock",
    "SprintPlan",
    "SubjectInput",
    "SubjectShare",
    "WeeklyAvailability",
    "allocate_subject_shares",
    "build_calendar",
    "build_schedule",
    "build_sprint",
    "rebalance",
]
