"""Schemas de Analytics.

Duas coisas aparecem em quase todo objeto aqui, e não por acaso: **a faixa** e
**a amostra**. São elas que separam um número medido de um número afirmado.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class ScoreComponentRead(BaseModel):
    key: str
    label: str
    weight: float
    #: Pontos na escala 0–1000. As parcelas somam exatamente o score exibido.
    points: int
    value: float | None = None
    low: float | None = None
    high: float | None = None
    sample: int
    available: bool
    confidence: str
    detail: str


class MasterScoreRead(BaseModel):
    value: int
    #: A faixa aparece na tela junto do valor, sempre.
    low: int
    high: int
    band: str
    band_note: str
    confidence: str
    available_weight: float
    components: list[ScoreComponentRead] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    #: O que a faixa é, em uma frase.
    interval_note: str
    empty_reason: str | None = None


class ScorePointRead(BaseModel):
    day: date
    value: int
    low: int
    high: int
    band: str
    confidence: str


class ScoreHistoryRead(BaseModel):
    points: list[ScorePointRead] = Field(default_factory=list)
    #: Nulo com menos de duas medições: uma medição não é tendência.
    delta: int | None = None
    empty_reason: str | None = None


class SubjectProjectionRead(BaseModel):
    subject_id: int | None = None
    name: str
    questions: int
    weight: float
    is_eliminatory: bool
    accuracy: float | None = None
    low: float | None = None
    high: float | None = None
    expected: float | None = None
    expected_low: float | None = None
    expected_high: float | None = None
    sample: int
    included: bool
    confidence: str
    detail: str
    #: Alerta do edital (nota mínima, disciplina eliminatória).
    risk_note: str | None = None


class ProjectionRead(BaseModel):
    total_questions: int
    covered_questions: int
    #: Fatia da prova que a estimativa cobre. Sempre exibida.
    coverage: float
    expected: float | None = None
    expected_low: float | None = None
    expected_high: float | None = None
    expected_percent: float | None = None
    subjects: list[SubjectProjectionRead] = Field(default_factory=list)
    confidence: str
    is_reliable: bool
    #: A plataforma não estima chance de aprovação — e diz isso aqui.
    disclaimer: str
    empty_reason: str | None = None


class PathStepRead(BaseModel):
    subject_id: int | None = None
    subject_name: str
    kind: str
    label: str
    action: str
    #: O número real que gerou a recomendação.
    evidence: str
    questions_at_stake: float
    is_eliminatory: bool
    risk_note: str | None = None


class PathRead(BaseModel):
    steps: list[PathStepRead] = Field(default_factory=list)
    disclaimer: str
    empty_reason: str | None = None


class SeriesPointRead(BaseModel):
    label: str
    value: float
    low: float | None = None
    high: float | None = None
    sample: int = 0
    day: date | None = None


class ChartRead(BaseModel):
    key: str
    title: str
    #: Para que serve decidir. Nenhum gráfico entra sem isto.
    decision: str
    unit: str
    points: list[SeriesPointRead] = Field(default_factory=list)
    empty_reason: str | None = None
    note: str = ""


class DashboardRead(BaseModel):
    charts: list[ChartRead] = Field(default_factory=list)


class AnalyticsOverviewRead(BaseModel):
    master_score: MasterScoreRead
    projection: ProjectionRead
    path: PathRead
    charts: list[ChartRead] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
