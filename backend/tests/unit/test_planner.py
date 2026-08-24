"""Planejador: as contas que decidem o que o candidato estuda."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.planner import (
    SubjectInput,
    WeeklyAvailability,
    allocate_subject_shares,
    build_calendar,
    build_schedule,
    build_sprint,
)
from app.domain.planner.availability import total_available_minutes
from app.domain.planner.rebalance import PendingTask, rebalance
from app.domain.planner.scheduler import FINAL_STRETCH_MIX, TaskKind, mix_for_day

SUBJECTS = [
    SubjectInput(
        key="portugues", name="Português", weight=Decimal("2"), questions_count=20, topics_count=30
    ),
    SubjectInput(
        key="penal", name="Direito Penal", weight=Decimal("3"), questions_count=20, topics_count=40
    ),
    SubjectInput(
        key="informatica",
        name="Informática",
        weight=Decimal("1"),
        questions_count=8,
        topics_count=10,
    ),
]


# --------------------------------------------------------------------------- #
# Disponibilidade
# --------------------------------------------------------------------------- #
def test_weekly_availability_totals() -> None:
    availability = WeeklyAvailability({0: 120, 2: 120, 4: 120, 5: 240})
    assert availability.weekly_minutes == 600
    assert availability.study_days == 4


def test_availability_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Dia da semana"):
        WeeklyAvailability({9: 60})
    with pytest.raises(ValueError, match="Minutos"):
        WeeklyAvailability({0: 60 * 20})


def test_calendar_respects_weekdays_and_blocked_days() -> None:
    availability = WeeklyAvailability.uniform(120, (0, 1, 2, 3, 4))
    calendar = build_calendar(
        availability,
        start=date(2026, 3, 2),  # segunda
        end=date(2026, 3, 8),  # domingo
        blocked_days={date(2026, 3, 4)},
    )

    assert len(calendar) == 7
    minutes = {day.day.weekday(): day.minutes for day in calendar}
    assert minutes[5] == 0 and minutes[6] == 0  # fim de semana sem estudo
    assert minutes[2] == 0  # dia bloqueado pelo candidato
    assert total_available_minutes(calendar) == 120 * 4


def test_calendar_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="anterior"):
        build_calendar(
            WeeklyAvailability.uniform(60, (0,)), start=date(2026, 3, 10), end=date(2026, 3, 1)
        )


# --------------------------------------------------------------------------- #
# Distribuição entre disciplinas
# --------------------------------------------------------------------------- #
def test_shares_sum_to_the_available_time() -> None:
    shares = allocate_subject_shares(SUBJECTS, 1000)
    assert sum(share.minutes for share in shares) == pytest.approx(1000, abs=2)
    assert sum(share.share for share in shares) == pytest.approx(1.0, abs=0.001)


def test_heavier_subject_receives_more_time() -> None:
    shares = {share.key: share for share in allocate_subject_shares(SUBJECTS, 1000)}
    assert shares["penal"].minutes > shares["portugues"].minutes > shares["informatica"].minutes


def test_every_subject_gets_a_minimum_slice() -> None:
    subjects = [
        SubjectInput(
            key="gigante", name="Gigante", weight=10, questions_count=100, topics_count=200
        ),
        SubjectInput(
            key="minima", name="Mínima", weight=None, questions_count=None, topics_count=0
        ),
    ]
    shares = {share.key: share for share in allocate_subject_shares(subjects, 1000)}
    # Disciplina do edital nunca fica com zero minuto.
    assert shares["minima"].minutes > 0


def test_breakdown_explains_the_share() -> None:
    share = allocate_subject_shares(SUBJECTS, 1000)[0]
    assert set(share.breakdown) == {
        "peso_no_edital",
        "questoes_na_prova",
        "extensao_do_conteudo",
    }
    assert all(value >= 0 for value in share.breakdown.values())


def test_no_subjects_produces_no_shares() -> None:
    assert allocate_subject_shares([], 1000) == []


# --------------------------------------------------------------------------- #
# Agenda
# --------------------------------------------------------------------------- #
def _schedule(days: int = 14, minutes_per_day: int = 120, exam: date | None = None):
    availability = WeeklyAvailability.uniform(minutes_per_day, (0, 1, 2, 3, 4))
    calendar = build_calendar(availability, start=date(2026, 3, 2), end=date(2026, 3, 2 + days - 1))
    shares = allocate_subject_shares(SUBJECTS, total_available_minutes(calendar))
    return build_schedule(calendar=calendar, shares=shares, exam_date=exam)


def test_schedule_only_uses_available_days() -> None:
    result = _schedule()
    weekdays = {task.day.weekday() for task in result.tasks}
    assert weekdays <= {0, 1, 2, 3, 4}


def test_schedule_never_exceeds_daily_capacity() -> None:
    result = _schedule(minutes_per_day=120)
    per_day: dict[date, int] = {}
    for task in result.tasks:
        per_day[task.day] = per_day.get(task.day, 0) + task.minutes
    assert all(total <= 120 for total in per_day.values())


def test_schedule_mixes_activity_types() -> None:
    result = _schedule()
    kinds = set(result.minutes_by_kind)
    assert TaskKind.THEORY in kinds
    assert TaskKind.QUESTIONS in kinds
    assert TaskKind.REVIEW in kinds


def test_every_task_carries_its_reason() -> None:
    result = _schedule()
    assert all(task.reason for task in result.tasks)
    subject_task = next(task for task in result.tasks if task.subject_key)
    assert "participacao_no_plano" in subject_task.reason


def test_final_stretch_reduces_new_content() -> None:
    exam = date(2026, 3, 20)
    assert mix_for_day(date(2026, 3, 10), exam, {TaskKind.THEORY: 0.45}) == FINAL_STRETCH_MIX
    # Longe da prova, a composição padrão continua valendo.
    base = {TaskKind.THEORY: 0.45}
    assert mix_for_day(date(2026, 1, 1), exam, base) == base


def test_schedule_without_days_or_subjects_is_empty() -> None:
    empty = build_schedule(calendar=[], shares=[], exam_date=None)
    assert empty.tasks == []
    assert empty.total_minutes == 0


def test_short_days_do_not_create_micro_tasks() -> None:
    availability = WeeklyAvailability.uniform(20, (0, 1, 2, 3, 4))
    calendar = build_calendar(availability, start=date(2026, 3, 2), end=date(2026, 3, 6))
    shares = allocate_subject_shares(SUBJECTS, total_available_minutes(calendar))
    result = build_schedule(calendar=calendar, shares=shares)
    # Nada abaixo de 15 minutos: bloco curto demais não vira tarefa.
    assert all(task.minutes >= 15 for task in result.tasks)


# --------------------------------------------------------------------------- #
# Sprint
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("minutes", [15, 30, 45, 60])
def test_sprint_uses_all_the_available_time(minutes: int) -> None:
    plan = build_sprint(minutes)
    assert plan.planned_minutes == minutes
    assert all(block.minutes >= 5 for block in plan.blocks)


def test_short_sprint_skips_new_content() -> None:
    kinds = {block.kind for block in build_sprint(15).blocks}
    # Em 15 minutos não se abre matéria nova.
    assert TaskKind.THEORY not in kinds


def test_long_sprint_prioritizes_questions() -> None:
    blocks = {block.kind: block.minutes for block in build_sprint(60).blocks}
    assert blocks[TaskKind.QUESTIONS] == max(blocks.values())


def test_sprint_rejects_too_short_duration() -> None:
    with pytest.raises(ValueError, match="mínimo"):
        build_sprint(5)


def test_sprint_can_focus_on_one_subject() -> None:
    plan = build_sprint(30, focus_subject_key="penal", focus_subject_name="Direito Penal")
    assert all(block.subject_name == "Direito Penal" for block in plan.blocks)


# --------------------------------------------------------------------------- #
# Replanejamento
# --------------------------------------------------------------------------- #
def _pending(days_ago: int, minutes: int = 60, count: int = 0) -> PendingTask:
    return PendingTask(
        kind=TaskKind.THEORY,
        subject_key="penal",
        subject_name="Direito Penal",
        minutes=minutes,
        original_day=date(2026, 3, 2) - timedelta(days=days_ago),
        reschedule_count=count,
    )


def _future_calendar(days: int = 10, minutes_per_day: int = 120):
    return build_calendar(
        WeeklyAvailability.uniform(minutes_per_day, (0, 1, 2, 3, 4)),
        start=date(2026, 3, 2),
        end=date(2026, 3, 2) + timedelta(days=days),
    )


def test_missed_tasks_are_moved_to_future_days() -> None:
    result = rebalance(
        pending=[_pending(1), _pending(2)],
        calendar=_future_calendar(),
        committed_minutes={},
        today=date(2026, 3, 2),
    )
    assert len(result.rescheduled) == 2
    assert all(task.day > date(2026, 3, 2) for task in result.rescheduled)
    assert result.dropped == []


def test_rescheduled_task_keeps_the_trail() -> None:
    result = rebalance(
        pending=[_pending(1)],
        calendar=_future_calendar(),
        committed_minutes={},
        today=date(2026, 3, 2),
    )
    reason = result.rescheduled[0].reason
    assert reason["remarcada_de"] == "2026-03-01"
    assert reason["tentativa"] == 1


def test_daily_overload_is_capped() -> None:
    calendar = _future_calendar(days=2, minutes_per_day=60)
    # Cada dia já tem 60 minutos comprometidos; a tolerância é de 20%.
    committed = {day.day: 60 for day in calendar}
    result = rebalance(
        pending=[_pending(1, minutes=60) for _ in range(4)],
        calendar=calendar,
        committed_minutes=committed,
        today=date(2026, 3, 2),
    )
    assert result.rescheduled == []
    assert len(result.dropped) == 4


def test_debt_does_not_accumulate_forever() -> None:
    # Tarefa já adiada duas vezes sai do plano em vez de rolar indefinidamente.
    result = rebalance(
        pending=[_pending(5, count=2)],
        calendar=_future_calendar(),
        committed_minutes={},
        today=date(2026, 3, 2),
    )
    assert result.rescheduled == []
    assert len(result.dropped) == 1
    assert "removida(s) do plano" in result.summary


def test_reschedule_shortens_the_task() -> None:
    result = rebalance(
        pending=[_pending(1, minutes=60, count=1)],
        calendar=_future_calendar(),
        committed_minutes={},
        today=date(2026, 3, 2),
    )
    # 60 minutos com um adiamento viram 40: repetir do mesmo tamanho não ajuda.
    assert result.rescheduled[0].minutes == 40


def test_without_future_days_everything_is_dropped() -> None:
    calendar = build_calendar(
        WeeklyAvailability.uniform(120, (0, 1, 2, 3, 4)),
        start=date(2026, 3, 2),
        end=date(2026, 3, 2),
    )
    result = rebalance(
        pending=[_pending(1)],
        calendar=calendar,
        committed_minutes={},
        today=date(2026, 3, 2),
    )
    assert result.rescheduled == []
    assert result.dropped_minutes == 60


def test_oldest_tasks_are_placed_first() -> None:
    result = rebalance(
        pending=[_pending(1, minutes=60), _pending(5, minutes=60)],
        calendar=_future_calendar(days=1, minutes_per_day=70),
        committed_minutes={},
        today=date(2026, 3, 2),
    )
    assert len(result.rescheduled) == 1
    assert result.rescheduled[0].reason["remarcada_de"] == "2026-02-25"
