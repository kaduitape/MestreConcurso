"""Modo Guerra: um período intenso declarado pelo próprio candidato.

Não é um modo que a plataforma impõe nem uma promessa de resultado. É uma meta
diária que o candidato escolhe, por um número de dias que ele escolhe, e um
acompanhamento **honesto** do que aconteceu — inclusive quando não aconteceu.

Duas decisões que importam:

*A meta é confrontada com o histórico na hora de criar.* Se o candidato estuda
40 minutos por dia e pede 240, a plataforma diz isso — sem bloquear. Meta
irrealista não motiva; frustra e faz abandonar.

*Dia perdido é dito como fato, não como acusação.* Nada de "você falhou" ou
contagem regressiva ameaçadora (item 40). A frase descreve, não julga.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum

MIN_DAYS = 3
MAX_DAYS = 30
MIN_DAILY_MINUTES = 30
MAX_DAILY_MINUTES = 720
MAX_DAILY_QUESTIONS = 300

# Acima disto a meta é bem mais alta que o próprio histórico — vale avisar.
STRETCH_FACTOR = 2.0


class WarStatus(StrEnum):
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True, slots=True)
class WarPlan:
    days: int
    daily_minutes: int
    daily_questions: int


@dataclass(frozen=True, slots=True)
class DayActivity:
    day: date
    minutes: int = 0
    questions: int = 0


@dataclass(frozen=True, slots=True)
class WarDay:
    day: date
    minutes: int
    questions: int
    met: bool
    is_future: bool


@dataclass(frozen=True, slots=True)
class WarProgress:
    plan: WarPlan
    days: list[WarDay] = field(default_factory=list)
    days_met: int = 0
    days_missed: int = 0
    days_left: int = 0
    ratio: float = 0.0
    is_over: bool = False
    succeeded: bool = False
    #: Texto factual. Descreve, não julga.
    message: str = ""


@dataclass(frozen=True, slots=True)
class PlanWarning:
    field_name: str
    message: str


def validate_plan(plan: WarPlan) -> list[str]:
    """Erros que impedem a criação. Lista vazia significa plano aceitável."""
    errors: list[str] = []
    if not MIN_DAYS <= plan.days <= MAX_DAYS:
        errors.append(f"O período precisa ficar entre {MIN_DAYS} e {MAX_DAYS} dias.")
    if not MIN_DAILY_MINUTES <= plan.daily_minutes <= MAX_DAILY_MINUTES:
        errors.append(
            f"A meta diária de estudo precisa ficar entre {MIN_DAILY_MINUTES} e "
            f"{MAX_DAILY_MINUTES} minutos."
        )
    if not 0 <= plan.daily_questions <= MAX_DAILY_QUESTIONS:
        errors.append(f"A meta de questões precisa ficar entre 0 e {MAX_DAILY_QUESTIONS}.")
    return errors


def review_plan(plan: WarPlan, *, average_minutes: float | None) -> list[PlanWarning]:
    """Compara a meta com o histórico real. Avisa; não bloqueia.

    Sem histórico não há aviso — inventar uma média para poder alertar seria
    exatamente o tipo de número fabricado que esta plataforma não usa.
    """
    warnings: list[PlanWarning] = []
    if average_minutes is None or average_minutes <= 0:
        return warnings

    if plan.daily_minutes >= average_minutes * STRETCH_FACTOR:
        warnings.append(
            PlanWarning(
                field_name="daily_minutes",
                message=(
                    f"Sua média recente é de {round(average_minutes)} minutos por dia, e a "
                    f"meta pede {plan.daily_minutes}. Dá para tentar, mas vale saber a "
                    "distância antes de começar."
                ),
            )
        )
    return warnings


def _days(count: int) -> str:
    return "1 dia" if count == 1 else f"{count} dias"


def _message(met: int, missed: int, left: int, *, over: bool, total: int) -> str:
    if over:
        if missed == 0:
            return f"{_days(total)}, todos cumpridos. Período concluído inteiro."
        return (
            f"Período encerrado: {met} de {_days(total)} cumpridos, {missed} abaixo da meta. "
            "O que foi estudado continua valendo."
        )
    if met == 0 and missed == 0:
        return "O período começou. Ainda não há dia fechado."
    if missed == 0:
        return f"{met} de {_days(total)} cumpridos até agora. Faltam {_days(left)}."
    cumpridos = "1 dia cumprido" if met == 1 else f"{met} dias cumpridos"
    return f"{cumpridos}, {missed} abaixo da meta. {_days(left)} restantes no período."


def build_progress(
    plan: WarPlan,
    activity: list[DayActivity],
    *,
    starts_on: date,
    today: date,
    status: str = WarStatus.RUNNING,
) -> WarProgress:
    """Monta o acompanhamento dia a dia a partir da atividade real."""
    by_day = {item.day: item for item in activity}
    days: list[WarDay] = []
    met = 0
    missed = 0

    for offset in range(plan.days):
        current = starts_on + timedelta(days=offset)
        record = by_day.get(current, DayActivity(current))
        is_future = current > today
        reached = record.minutes >= plan.daily_minutes and record.questions >= plan.daily_questions
        # O dia de hoje ainda pode ser cumprido: não conta como perdido.
        if not is_future and current < today and not reached:
            missed += 1
        if reached:
            met += 1
        days.append(
            WarDay(
                day=current,
                minutes=record.minutes,
                questions=record.questions,
                met=reached,
                is_future=is_future,
            )
        )

    ends_on = starts_on + timedelta(days=plan.days - 1)
    over = status != WarStatus.RUNNING or today > ends_on
    days_left = max(0, (ends_on - today).days + (0 if over else 1))

    return WarProgress(
        plan=plan,
        days=days,
        days_met=met,
        days_missed=missed,
        days_left=days_left,
        ratio=round(met / plan.days, 4) if plan.days else 0.0,
        is_over=over,
        succeeded=over and met == plan.days,
        message=_message(met, missed, days_left, over=over, total=plan.days),
    )
