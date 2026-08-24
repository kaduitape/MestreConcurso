"""Disponibilidade semanal do candidato convertida em capacidade por dia."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

MAX_MINUTES_PER_DAY = 16 * 60
MIN_BLOCK_MINUTES = 15


@dataclass(frozen=True, slots=True)
class WeeklyAvailability:
    """Minutos por dia da semana (0 = segunda … 6 = domingo)."""

    minutes_by_weekday: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for weekday, minutes in self.minutes_by_weekday.items():
            if weekday not in range(7):
                raise ValueError(f"Dia da semana inválido: {weekday}")
            if minutes < 0 or minutes > MAX_MINUTES_PER_DAY:
                raise ValueError(f"Minutos por dia fora do intervalo aceito: {minutes}")

    @property
    def weekly_minutes(self) -> int:
        return sum(self.minutes_by_weekday.values())

    @property
    def study_days(self) -> int:
        return sum(1 for minutes in self.minutes_by_weekday.values() if minutes > 0)

    def minutes_for(self, day: date) -> int:
        return self.minutes_by_weekday.get(day.weekday(), 0)

    @classmethod
    def uniform(cls, minutes_per_day: int, weekdays: tuple[int, ...]) -> WeeklyAvailability:
        return cls(dict.fromkeys(weekdays, minutes_per_day))


@dataclass(frozen=True, slots=True)
class DailyCapacity:
    day: date
    minutes: int

    @property
    def is_study_day(self) -> bool:
        return self.minutes >= MIN_BLOCK_MINUTES


def build_calendar(
    availability: WeeklyAvailability,
    *,
    start: date,
    end: date,
    blocked_days: set[date] | None = None,
) -> list[DailyCapacity]:
    """Capacidade de cada dia entre ``start`` e ``end`` (ambos incluídos)."""
    if end < start:
        raise ValueError("A data final não pode ser anterior à inicial.")

    blocked = blocked_days or set()
    days: list[DailyCapacity] = []
    current = start
    while current <= end:
        minutes = 0 if current in blocked else availability.minutes_for(current)
        days.append(DailyCapacity(day=current, minutes=minutes))
        current += timedelta(days=1)
    return days


def total_available_minutes(calendar: list[DailyCapacity]) -> int:
    return sum(day.minutes for day in calendar if day.is_study_day)
