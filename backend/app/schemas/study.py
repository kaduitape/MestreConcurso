"""Schemas do plano de estudo, agenda e sessões."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_READ = ConfigDict(from_attributes=True)

WEEKDAY_LABELS = {
    0: "Segunda",
    1: "Terça",
    2: "Quarta",
    3: "Quinta",
    4: "Sexta",
    5: "Sábado",
    6: "Domingo",
}


class AvailabilityInput(BaseModel):
    """Minutos disponíveis por dia da semana (0 = segunda … 6 = domingo)."""

    minutes_by_weekday: dict[int, int]

    @field_validator("minutes_by_weekday")
    @classmethod
    def _validate(cls, value: dict[int, int]) -> dict[int, int]:
        for weekday, minutes in value.items():
            if weekday not in WEEKDAY_LABELS:
                raise ValueError(f"Dia da semana inválido: {weekday}")
            if minutes < 0 or minutes > 16 * 60:
                raise ValueError("Informe entre 0 e 960 minutos por dia.")
        if not any(value.values()):
            raise ValueError("Informe pelo menos um dia com tempo disponível.")
        return value


class StudyPlanCreate(AvailabilityInput):
    notice_public_id: str | None = None
    position_public_id: str | None = None
    exam_date: date | None = None
    name: str | None = Field(default=None, max_length=200)


class StudyPlanUpdate(BaseModel):
    minutes_by_weekday: dict[int, int] | None = None


class AvailabilityRead(BaseModel):
    model_config = _READ

    weekday: int
    minutes: int
    label: str = ""


class SubjectShareRead(BaseModel):
    key: str
    name: str
    share: float
    minutes: int
    breakdown: dict[str, float] = Field(default_factory=dict)


class StudyPlanRead(BaseModel):
    model_config = _READ

    public_id: str
    name: str
    status: str
    exam_date: date | None = None
    starts_on: date
    weekly_minutes_target: int
    generated_at: datetime | None = None
    recalculated_at: datetime | None = None
    availability: list[AvailabilityRead] = Field(default_factory=list)
    shares: list[SubjectShareRead] = Field(default_factory=list)
    minutes_by_kind: dict[str, int] = Field(default_factory=dict)
    total_planned_minutes: int = 0
    days_until_exam: int | None = None


class StudyTaskRead(BaseModel):
    model_config = _READ

    public_id: str
    scheduled_for: date
    kind: str
    kind_label: str = ""
    subject_key: str | None = None
    subject_label: str | None = None
    color_token: str = "subject-especifica"
    planned_minutes: int
    actual_minutes: int
    status: str
    order_index: int
    source: str
    reschedule_count: int = 0
    rescheduled_from: date | None = None
    # Contribuições que colocaram a tarefa na agenda — o "POR QUÊ?" da interface.
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class TodayMissionRead(BaseModel):
    day: date
    plan_public_id: str
    plan_name: str
    days_until_exam: int | None = None
    planned_minutes: int
    done_minutes: int
    overdue_count: int
    tasks: list[StudyTaskRead] = Field(default_factory=list)


class CalendarDayRead(BaseModel):
    day: date
    planned_minutes: int
    done_minutes: int
    tasks: list[StudyTaskRead] = Field(default_factory=list)


class CalendarRead(BaseModel):
    start: date
    end: date
    days: list[CalendarDayRead] = Field(default_factory=list)
    exam_date: date | None = None


class TaskCompleteInput(BaseModel):
    minutes: int | None = Field(default=None, ge=0, le=960)


class RebalanceRead(BaseModel):
    rescheduled: int
    dropped: int
    dropped_minutes: int
    days_touched: int
    summary: str


class SprintInput(BaseModel):
    minutes: int = Field(ge=15, le=180)
    subject_key: str | None = None


class SessionRead(BaseModel):
    model_config = _READ

    public_id: str
    status: str
    kind: str
    subject_key: str | None = None
    subject_label: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    focus_seconds: int
    pause_seconds: int
    notes: str | None = None
    task_public_id: str | None = None


class SessionStartInput(BaseModel):
    task_public_id: str | None = None


class SessionFinishInput(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class SubjectProgressRead(BaseModel):
    model_config = _READ

    subject_key: str
    subject_label: str
    color_token: str
    planned_minutes: int
    studied_minutes: int
    tasks_done: int
    tasks_skipped: int
    completion: float
    last_studied_at: datetime | None = None
