"""Sequência de estudo — sem transformar constância em ansiedade.

Duas decisões deliberadas:

* **o dia só conta com estudo útil.** Abrir o aplicativo não é estudar, e uma
  sequência que sobe por login mede presença, não preparação;
* **existem proteções.** Perder a sequência de 40 dias por um imprevisto faz a
  pessoa desistir do hábito inteiro. Duas proteções por mês absorvem a vida real
  sem tornar o número decorativo.

A linguagem em volta disso importa: quando a sequência quebra, o texto é factual
e o recorde continua registrado. Streak que ameaça faz estudar por medo de perder
um número — o oposto do que a constância deveria construir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import pairwise

# O que qualifica um dia. Basta **um** destes.
MIN_FOCUS_MINUTES = 20
MIN_TASKS_DONE = 3

SHIELDS_PER_MONTH = 2


@dataclass(frozen=True, slots=True)
class DayRecord:
    day: date
    minutes: int = 0
    tasks_done: int = 0
    mission_completed: bool = False
    shield_used: bool = False

    @property
    def qualified(self) -> bool:
        return (
            self.minutes >= MIN_FOCUS_MINUTES
            or self.tasks_done >= MIN_TASKS_DONE
            or self.mission_completed
        )


@dataclass(frozen=True, slots=True)
class StreakState:
    current: int
    longest: int
    average: float
    active_days: int
    shields_left: int
    last_qualified_on: date | None = None
    # Dias em que a proteção segurou a sequência.
    shielded_days: list[date] = field(default_factory=list)
    history: list[dict[str, object]] = field(default_factory=list)
    message: str = ""


def qualifies(minutes: int, tasks_done: int, mission_completed: bool) -> bool:
    """Este dia conta como estudo útil?"""
    return minutes >= MIN_FOCUS_MINUTES or tasks_done >= MIN_TASKS_DONE or mission_completed


def build_streak(
    records: list[DayRecord],
    *,
    today: date,
    shields_left: int = SHIELDS_PER_MONTH,
    window: int = 30,
) -> StreakState:
    """Reconstrói a sequência a partir do histórico dia a dia.

    A proteção é consumida para **um** dia vazio isolado entre dias válidos, e o
    consumo é reportado — o candidato precisa saber que gastou uma.
    """
    by_day = {record.day: record for record in records}
    qualified_days = {day for day, record in by_day.items() if record.qualified}

    current = 0
    shields = shields_left
    shielded: list[date] = []

    # Se hoje ainda não foi cumprido, a contagem começa em ontem: o dia corrente
    # ainda está aberto, e cobrar por ele seria contar um dia que não terminou.
    cursor = today if today in qualified_days else today - timedelta(days=1)

    while True:
        if cursor in qualified_days:
            current += 1
            cursor -= timedelta(days=1)
            continue
        # Dia vazio: a proteção segura, desde que o dia anterior tenha valido.
        previous = cursor - timedelta(days=1)
        if shields > 0 and previous in qualified_days:
            shields -= 1
            shielded.append(cursor)
            cursor = previous
            continue
        break

    longest = _longest_run(sorted(qualified_days))
    recent = [day for day in qualified_days if (today - day).days < window]
    average = round(len(recent) / (window / 7), 2) if recent else 0.0

    return StreakState(
        current=current,
        longest=max(longest, current),
        average=average,
        active_days=len(recent),
        shields_left=shields,
        last_qualified_on=max(qualified_days) if qualified_days else None,
        shielded_days=shielded,
        history=[
            {
                "day": (today - timedelta(days=offset)).isoformat(),
                "qualified": (today - timedelta(days=offset)) in qualified_days,
                "shielded": (today - timedelta(days=offset)) in shielded,
            }
            for offset in range(13, -1, -1)
        ],
        message=_message(current, longest, shielded),
    )


def _longest_run(days: list[date]) -> int:
    if not days:
        return 0
    longest = run = 1
    for previous, current in pairwise(days):
        run = run + 1 if (current - previous).days == 1 else 1
        longest = max(longest, run)
    return longest


def _message(current: int, longest: int, shielded: list[date]) -> str:
    if current == 0:
        return (
            "Sua sequência está zerada. Vinte minutos de foco hoje já recomeçam a contagem — "
            f"e o seu recorde de {longest} dias continua registrado."
            if longest
            else "Vinte minutos de foco hoje começam a sua sequência."
        )
    if shielded:
        return (
            f"{current} dias seguidos. Uma proteção cobriu um dia sem estudo — "
            "a sequência seguiu de pé."
        )
    if current == longest and current > 1:
        return f"{current} dias seguidos: é o seu recorde."
    return f"{current} dias seguidos."
