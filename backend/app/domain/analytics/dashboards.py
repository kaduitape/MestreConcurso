"""Painéis — e a regra que os define: **todo gráfico carrega uma decisão**.

O critério de aceite da Fase 9 é esse, e ele muda o formato dos dados: uma série
sem ``decision`` não é aceita aqui. Gráfico bonito que não muda o que o candidato
faz amanhã é enfeite caro, e enfeite caro é o que faz um produto de estudo virar
painel de vaidade.

Séries também carregam **amostra** e, quando são proporção, **faixa**. Um ponto
de 100% em duas respostas não pode ter o mesmo peso visual que 78% em trezentas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.domain.analytics.statistics import Confidence, Interval, wilson


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    label: str
    value: float
    #: Nulos quando o ponto não é uma proporção amostral.
    low: float | None = None
    high: float | None = None
    sample: int = 0
    day: date | None = None


@dataclass(frozen=True, slots=True)
class Chart:
    key: str
    title: str
    #: O que este gráfico serve para decidir. Sem isso, ele não entra.
    decision: str
    unit: str
    points: list[SeriesPoint] = field(default_factory=list)
    #: Nulo quando não há dado suficiente para desenhar.
    empty_reason: str | None = None
    note: str = ""


@dataclass(frozen=True, slots=True)
class WeeklyAttempts:
    week_start: date
    correct: int
    total: int


@dataclass(frozen=True, slots=True)
class SubjectCoverage:
    name: str
    covered_minutes: int
    planned_minutes: int


@dataclass(frozen=True, slots=True)
class DayEffort:
    day: date
    minutes: int
    qualified: bool


def accuracy_evolution(weeks: list[WeeklyAttempts]) -> Chart:
    """Acerto semanal, com a faixa de cada semana — não só a linha central."""
    if len(weeks) < 2:
        return Chart(
            key="acerto",
            title="Evolução do acerto",
            decision=(
                "Mostra se o desempenho está subindo ou escorregando. Queda por duas "
                "semanas seguidas pede revisão do que mudou na rotina."
            ),
            unit="%",
            empty_reason="A evolução aparece a partir da segunda semana com respostas.",
        )

    points: list[SeriesPoint] = []
    for week in sorted(weeks, key=lambda item: item.week_start):
        interval: Interval = wilson(week.correct, week.total)
        points.append(
            SeriesPoint(
                label=week.week_start.strftime("%d/%m"),
                value=interval.value,
                low=interval.low,
                high=interval.high,
                sample=week.total,
                day=week.week_start,
            )
        )

    return Chart(
        key="acerto",
        title="Evolução do acerto",
        decision=(
            "Mostra se o desempenho está subindo ou escorregando. Queda por duas semanas "
            "seguidas pede revisão do que mudou na rotina."
        ),
        unit="%",
        points=points,
        note="Cada semana traz a própria faixa: poucas respostas produzem faixa larga.",
    )


def coverage_by_subject(subjects: list[SubjectCoverage]) -> Chart:
    """Cobertura por disciplina — a decisão é onde alocar as próximas horas."""
    if not subjects:
        return Chart(
            key="cobertura",
            title="Cobertura por disciplina",
            decision="Aponta onde alocar as próximas horas de estudo.",
            unit="%",
            empty_reason="A cobertura é medida sobre o plano. Monte o plano para vê-la.",
        )

    points = [
        SeriesPoint(
            label=item.name,
            value=round(min(1.0, item.covered_minutes / item.planned_minutes), 4)
            if item.planned_minutes
            else 0.0,
            sample=item.planned_minutes,
        )
        for item in sorted(subjects, key=lambda item: item.name)
    ]
    return Chart(
        key="cobertura",
        title="Cobertura por disciplina",
        decision=(
            "Aponta onde alocar as próximas horas: a barra mais curta é a disciplina "
            "com mais tempo planejado ainda não cumprido."
        ),
        unit="%",
        points=points,
        note="Cobertura é tempo cumprido sobre tempo planejado — não é domínio.",
    )


def consistency(days: list[DayEffort]) -> Chart:
    """Minutos por dia. A decisão é sobre a rotina, não sobre o conteúdo."""
    if not days:
        return Chart(
            key="consistencia",
            title="Consistência",
            decision="Mostra se a rotina se sustenta ou depende de maratonas.",
            unit="min",
            empty_reason="Ainda não há dias de estudo registrados.",
        )

    points = [
        SeriesPoint(
            label=item.day.strftime("%d/%m"),
            value=float(item.minutes),
            sample=1 if item.qualified else 0,
            day=item.day,
        )
        for item in sorted(days, key=lambda item: item.day)
    ]
    return Chart(
        key="consistencia",
        title="Consistência",
        decision=(
            "Mostra se a rotina se sustenta. Picos isolados seguidos de dias vazios "
            "rendem menos que uma carga menor e diária."
        ),
        unit="min",
        points=points,
    )


def retention(weeks: list[WeeklyAttempts]) -> Chart:
    """Retenção semanal na revisão, com faixa por semana."""
    if not weeks:
        return Chart(
            key="retencao",
            title="Retenção na revisão",
            decision="Diz se o que foi estudado está sendo mantido ou esquecido.",
            unit="%",
            empty_reason="A retenção aparece depois das primeiras revisões.",
        )

    points: list[SeriesPoint] = []
    for week in sorted(weeks, key=lambda item: item.week_start):
        interval = wilson(week.correct, week.total)
        points.append(
            SeriesPoint(
                label=week.week_start.strftime("%d/%m"),
                value=interval.value,
                low=interval.low,
                high=interval.high,
                sample=week.total,
                day=week.week_start,
            )
        )

    return Chart(
        key="retencao",
        title="Retenção na revisão",
        decision=(
            "Diz se o conteúdo está sendo mantido. Retenção caindo com cobertura "
            "subindo significa avançar rápido demais."
        ),
        unit="%",
        points=points,
    )


@dataclass(frozen=True, slots=True)
class Dashboard:
    charts: list[Chart] = field(default_factory=list)
    confidence: str = Confidence.NONE
