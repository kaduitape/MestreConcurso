"""Esquemas das saídas estruturadas da IA.

A resposta do modelo é validada aqui antes de encostar no banco. Campo fora do
formato é descartado — nunca "corrigido" em silêncio.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtractedField(BaseModel):
    """Um campo com o trecho que o comprova."""

    model_config = ConfigDict(extra="ignore")

    value: Any = None
    quote: str | None = None
    page: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("quote")
    @classmethod
    def _clean_quote(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class ExtractedSubject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=2, max_length=255)
    weight: float | None = Field(default=None, ge=0, le=99)
    questions_count: int | None = Field(default=None, ge=0, le=500)
    topics: list[str] = Field(default_factory=list)
    quote: str | None = None
    page: int | None = Field(default=None, ge=1)

    @field_validator("topics")
    @classmethod
    def _clean_topics(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(item.split())[:500] for item in value if item and item.strip()]
        return cleaned[:200]


class ExtractedEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str = Field(default="OTHER", max_length=30)
    title: str = Field(min_length=2, max_length=255)
    date_start: str | None = None
    date_end: str | None = None
    is_critical: bool = False
    quote: str | None = None
    page: int | None = Field(default=None, ge=1)


class NoticeExtraction(BaseModel):
    """Resposta completa da extração de um edital."""

    model_config = ConfigDict(extra="ignore")

    fields: dict[str, ExtractedField] = Field(default_factory=dict)
    subjects: list[ExtractedSubject] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)


# Campos que a plataforma espera do edital, com o rótulo exibido na interface.
EXPECTED_FIELDS: dict[str, str] = {
    "competition.name": "Nome do concurso",
    "organization.name": "Órgão",
    "exam_board.name": "Banca organizadora",
    "position.name": "Cargo",
    "position.education_level": "Escolaridade exigida",
    "position.salary_cents": "Remuneração inicial",
    "position.vacancies": "Vagas",
    "registration.start_date": "Início das inscrições",
    "registration.end_date": "Fim das inscrições",
    "registration.fee_cents": "Taxa de inscrição",
    "exam.date": "Data da prova",
    "exam.duration_minutes": "Duração da prova",
    "exam.questions_count": "Número de questões",
    "exam.min_score_rule": "Nota mínima",
    "elimination.rules": "Critérios de eliminação",
}
