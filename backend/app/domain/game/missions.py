"""Geração das missões do dia.

Cada missão nasce de um **sinal real** do candidato e carrega o número que a
gerou. Missão sem porquê é tarefa arbitrária: o candidato cumpre por obediência,
não porque aquilo o aproxima da aprovação — e no dia em que perceber isso, para
de cumprir.

A ordem de prioridade não é estética. Ela reflete o que se perde primeiro:
memória vencida se perde hoje; erro sem causa nunca vira aprendizado; disciplina
de alta prioridade é onde o tempo rende mais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

MAX_DAILY_MISSIONS = 4


class MissionKind(StrEnum):
    REVIEW_CARDS = "REVIEW_CARDS"
    CLASSIFY_ERRORS = "CLASSIFY_ERRORS"
    STUDY_SUBJECT = "STUDY_SUBJECT"
    COMPLETE_TASKS = "COMPLETE_TASKS"
    ANSWER_QUESTIONS = "ANSWER_QUESTIONS"


class MissionPriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass(frozen=True, slots=True)
class MissionSignals:
    """O que se sabe do candidato hoje. Tudo já calculado em Python."""

    due_cards: int = 0
    unclassified_errors: int = 0
    top_subject: str | None = None
    top_subject_score: int = 0
    planned_minutes: int = 0
    pending_tasks: int = 0
    has_plan: bool = False


@dataclass(frozen=True, slots=True)
class MissionBlueprint:
    kind: str
    title: str
    description: str
    target_metric: str
    target_value: int
    xp_reward: int
    priority: str
    difficulty: str
    estimated_minutes: int
    # O número real que justificou a missão — exibido como "por quê?".
    rationale: str
    source: dict[str, object] = field(default_factory=dict)


def _cards_mission(signals: MissionSignals) -> MissionBlueprint | None:
    if signals.due_cards <= 0:
        return None
    target = min(signals.due_cards, 40)
    return MissionBlueprint(
        kind=MissionKind.REVIEW_CARDS,
        title=f"Revisar {target} cartões vencidos",
        description="Memória vencida se perde hoje; revisada, volta a render.",
        target_metric="cards_reviewed",
        target_value=target,
        xp_reward=80,
        priority=MissionPriority.HIGH,
        difficulty="MEDIA",
        estimated_minutes=max(5, round(target * 0.5)),
        rationale=(
            f"{signals.due_cards} cartão(ões) venceram. Adiar hoje empurra todos para amanhã."
        ),
        source={"due_cards": signals.due_cards},
    )


def _errors_mission(signals: MissionSignals) -> MissionBlueprint | None:
    if signals.unclassified_errors <= 0:
        return None
    target = min(signals.unclassified_errors, 5)
    return MissionBlueprint(
        kind=MissionKind.CLASSIFY_ERRORS,
        title=f"Classificar {target} erros",
        description="Erro sem causa registrada não vira aprendizado.",
        target_metric="errors_classified",
        target_value=target,
        xp_reward=100,
        priority=MissionPriority.HIGH,
        difficulty="FACIL",
        estimated_minutes=max(4, target * 2),
        rationale=f"{signals.unclassified_errors} erro(s) ainda sem causa registrada.",
        source={"unclassified_errors": signals.unclassified_errors},
    )


def _subject_mission(signals: MissionSignals) -> MissionBlueprint | None:
    if not signals.top_subject:
        return None
    return MissionBlueprint(
        kind=MissionKind.STUDY_SUBJECT,
        title=f"Estudar {signals.top_subject} por 30 minutos",
        description="A disciplina onde o seu tempo rende mais agora.",
        target_metric="focus_minutes",
        target_value=30,
        xp_reward=120,
        priority=MissionPriority.MEDIUM,
        difficulty="MEDIA",
        estimated_minutes=30,
        rationale=(
            f"{signals.top_subject} está com Priority Score {signals.top_subject_score}, "
            "o mais alto do seu plano."
        ),
        source={"subject": signals.top_subject, "priority_score": signals.top_subject_score},
    )


def _tasks_mission(signals: MissionSignals) -> MissionBlueprint | None:
    if signals.pending_tasks <= 0:
        return None
    target = min(signals.pending_tasks, 3)
    return MissionBlueprint(
        kind=MissionKind.COMPLETE_TASKS,
        title=f"Concluir {target} tarefas do plano",
        description="O plano já sabe o que fazer hoje; falta fazer.",
        target_metric="tasks_done",
        target_value=target,
        xp_reward=110,
        priority=MissionPriority.MEDIUM,
        difficulty="MEDIA",
        estimated_minutes=signals.planned_minutes or 45,
        rationale=f"{signals.pending_tasks} tarefa(s) pendentes na sua agenda de hoje.",
        source={"pending_tasks": signals.pending_tasks},
    )


def _questions_mission(_: MissionSignals) -> MissionBlueprint:
    return MissionBlueprint(
        kind=MissionKind.ANSWER_QUESTIONS,
        title="Resolver 20 questões",
        description="Volume com correção comentada, para calibrar o que já foi estudado.",
        target_metric="questions_answered",
        target_value=20,
        xp_reward=120,
        priority=MissionPriority.LOW,
        difficulty="MEDIA",
        estimated_minutes=25,
        rationale="Nenhum sinal mais urgente hoje: hora de treinar volume.",
        source={},
    )


def generate_daily(signals: MissionSignals) -> list[MissionBlueprint]:
    """Monta as missões do dia, do sinal mais urgente ao menos.

    Sem plano ativo devolve vazio: a Central mostra o convite a montar o plano em
    vez de inventar tarefas que não levam a lugar nenhum.
    """
    if not signals.has_plan:
        return []

    candidates = [
        _cards_mission(signals),
        _errors_mission(signals),
        _subject_mission(signals),
        _tasks_mission(signals),
    ]
    missions = [item for item in candidates if item is not None]

    if not missions:
        missions.append(_questions_mission(signals))

    return missions[:MAX_DAILY_MISSIONS]


def daily_bonus_xp() -> int:
    """Bônus por concluir todas as missões do dia."""
    return 250
