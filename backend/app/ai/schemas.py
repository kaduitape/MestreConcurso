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


class ExtractedPosition(BaseModel):
    """Um cargo do edital, com o trecho que o comprova.

    Edital de concurso raramente tem um cargo só: tem vinte, cada um com sua
    escolaridade, suas vagas, seu salário e às vezes sua própria grade de
    disciplinas. Por isso cargo é **lista**, como disciplina e evento — e não
    campo escalar.

    Os campos ``position.*`` de ``EXPECTED_FIELDS`` continuam existindo e
    descrevem o **cargo principal** (ou o único, quando o edital tem um). Eles
    não foram transformados em lista porque o Raio-X e a comparação de
    retificação os leem como valor único desde a Fase 3, e porque "o cargo
    principal deste edital" continua sendo uma pergunta legítima.
    """

    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=2, max_length=160)
    education_level: str | None = Field(default=None, max_length=20)
    salary_cents: int | None = Field(default=None, ge=0)
    vacancies: int | None = Field(default=None, ge=0, le=1_000_000)
    #: Cadastro de reserva. Vaga de CR não é vaga imediata, e misturar as duas
    #: inflaria o número que o candidato usa para decidir se vale estudar.
    cr_vacancies: int | None = Field(default=None, ge=0, le=1_000_000)
    workload_hours: int | None = Field(default=None, ge=0, le=744)
    requirements: str | None = None
    questions_count: int | None = Field(default=None, ge=0, le=500)
    exam_duration_minutes: int | None = Field(default=None, ge=0, le=2880)
    quote: str | None = None
    page: int | None = Field(default=None, ge=1)

    @field_validator("name", "requirements")
    @classmethod
    def _clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split()) or None

    @field_validator("education_level")
    @classmethod
    def _clean_level(cls, value: str | None) -> str | None:
        """Escolaridade fora da lista conhecida vira nada, não vira palpite."""
        if value is None:
            return None
        nivel = value.strip().upper()
        return nivel if nivel in EDUCATION_LEVELS else None


class ExtractedSubject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=2, max_length=255)
    #: De qual cargo é esta disciplina, como o edital o nomeia. Nulo quando a
    #: grade é comum a todos os cargos — que é o caso mais frequente.
    position_label: str | None = Field(default=None, max_length=200)
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
    positions: list[ExtractedPosition] = Field(default_factory=list)
    subjects: list[ExtractedSubject] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)


#: Escolaridades que o catálogo conhece. O modelo escreve o que quiser, e o que
#: não está aqui é **descartado** em vez de virar coluna com valor inventado.
#:
#: A fonte de verdade é ``app.models.catalog.EducationLevel``. A lista está
#: repetida porque a camada de IA não importa modelos — e um teste confere que
#: as duas continuam iguais, que é o que mantém a cópia honesta.
EDUCATION_LEVELS: frozenset[str] = frozenset({"FUNDAMENTAL", "MEDIO", "TECNICO", "SUPERIOR"})


# Campos que a plataforma espera do edital, com o rótulo exibido na interface.
EXPECTED_FIELDS: dict[str, str] = {
    "competition.name": "Nome do concurso",
    "organization.name": "Órgão",
    "exam_board.name": "Banca organizadora",
    "position.name": "Cargo principal",
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
