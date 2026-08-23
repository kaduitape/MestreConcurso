"""Schemas do catálogo de concursos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------- #
# Bancas
# --------------------------------------------------------------------------- #
class ExamBoardRead(BaseModel):
    model_config = _READ

    public_id: str
    slug: str
    name: str
    short_name: str
    aliases: list[str] = Field(default_factory=list)
    website: str | None = None
    logo_url: str | None = None
    description: str | None = None
    is_active: bool = True


class ExamBoardCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    short_name: str = Field(min_length=2, max_length=60)
    slug: str | None = Field(default=None, max_length=60)
    aliases: list[str] = Field(default_factory=list)
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    description: str | None = None
    is_active: bool = True


class ExamBoardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    short_name: str | None = Field(default=None, min_length=2, max_length=60)
    aliases: list[str] | None = None
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    description: str | None = None
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Órgãos
# --------------------------------------------------------------------------- #
class OrganizationRead(BaseModel):
    model_config = _READ

    public_id: str
    slug: str
    name: str
    short_name: str
    sphere: str
    uf: str | None = None
    website: str | None = None
    logo_url: str | None = None
    is_active: bool = True


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    short_name: str = Field(min_length=2, max_length=60)
    slug: str | None = Field(default=None, max_length=80)
    sphere: str = Field(default="FEDERAL", pattern="^(FEDERAL|ESTADUAL|MUNICIPAL|DISTRITAL)$")
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    short_name: str | None = Field(default=None, min_length=2, max_length=60)
    sphere: str | None = Field(default=None, pattern="^(FEDERAL|ESTADUAL|MUNICIPAL|DISTRITAL)$")
    uf: str | None = Field(default=None, min_length=2, max_length=2)
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


# --------------------------------------------------------------------------- #
# Disciplinas e assuntos
# --------------------------------------------------------------------------- #
class SubjectRead(BaseModel):
    model_config = _READ

    public_id: str
    slug: str
    name: str
    area: str | None = None
    color_token: str
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class SubjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    slug: str | None = Field(default=None, max_length=80)
    area: str | None = Field(default=None, max_length=80)
    color_token: str = Field(default="subject-especifica", max_length=40)
    description: str | None = None
    is_active: bool = True
    sort_order: int = 0


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=140)
    area: str | None = Field(default=None, max_length=80)
    color_token: str | None = Field(default=None, max_length=40)
    description: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class TopicRead(BaseModel):
    model_config = _READ

    public_id: str
    name: str
    slug: str
    depth: int
    path: str
    sort_order: int
    description: str | None = None
    parent_public_id: str | None = None


class TopicCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    parent_public_id: str | None = None
    sort_order: int = 0
    description: str | None = None


class TopicImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Concursos e cargos
# --------------------------------------------------------------------------- #
class PositionSubjectRead(BaseModel):
    model_config = _READ

    subject: SubjectRead
    weight: Decimal
    questions_count: int | None = None
    min_score: Decimal | None = None
    is_eliminatory: bool = False
    source: str = "MANUAL"


class PositionSubjectInput(BaseModel):
    subject_public_id: str
    weight: Decimal = Field(default=Decimal("1.00"), ge=0, le=99)
    questions_count: int | None = Field(default=None, ge=0, le=500)
    min_score: Decimal | None = Field(default=None, ge=0)
    is_eliminatory: bool = False


class PositionRead(BaseModel):
    model_config = _READ

    public_id: str
    name: str
    education_level: str | None = None
    salary_cents: int | None = None
    vacancies: int | None = None
    cr_vacancies: int | None = None
    workload_hours: int | None = None
    requirements: str | None = None
    questions_count: int | None = None
    exam_duration_minutes: int | None = None
    subjects: list[PositionSubjectRead] = Field(default_factory=list)


class PositionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    education_level: str | None = Field(
        default=None, pattern="^(FUNDAMENTAL|MEDIO|TECNICO|SUPERIOR)$"
    )
    salary_cents: int | None = Field(default=None, ge=0)
    vacancies: int | None = Field(default=None, ge=0)
    cr_vacancies: int | None = Field(default=None, ge=0)
    workload_hours: int | None = Field(default=None, ge=0, le=80)
    requirements: str | None = None
    questions_count: int | None = Field(default=None, ge=0, le=500)
    exam_duration_minutes: int | None = Field(default=None, ge=0, le=1440)


class PositionUpdate(BaseModel):
    """Todos os campos opcionais: só o que vier é alterado."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    education_level: str | None = Field(
        default=None, pattern="^(FUNDAMENTAL|MEDIO|TECNICO|SUPERIOR)$"
    )
    salary_cents: int | None = Field(default=None, ge=0)
    vacancies: int | None = Field(default=None, ge=0)
    cr_vacancies: int | None = Field(default=None, ge=0)
    workload_hours: int | None = Field(default=None, ge=0, le=80)
    requirements: str | None = None
    questions_count: int | None = Field(default=None, ge=0, le=500)
    exam_duration_minutes: int | None = Field(default=None, ge=0, le=1440)


class CompetitionRead(BaseModel):
    model_config = _READ

    public_id: str
    slug: str
    name: str
    year: int
    status: str
    education_level: str | None = None
    vacancies_total: int | None = None
    salary_max_cents: int | None = None
    registration_start: date | None = None
    registration_end: date | None = None
    exam_date: date | None = None
    source_url: str | None = None
    notes: str | None = None
    is_published: bool = False
    organization: OrganizationRead
    exam_board: ExamBoardRead | None = None
    positions: list[PositionRead] = Field(default_factory=list)


class CompetitionSummary(BaseModel):
    """Versão enxuta para listagens."""

    model_config = _READ

    public_id: str
    slug: str
    name: str
    year: int
    status: str
    exam_date: date | None = None
    vacancies_total: int | None = None
    salary_max_cents: int | None = None
    is_published: bool = False
    organization: OrganizationRead
    exam_board: ExamBoardRead | None = None


class CompetitionCreate(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    year: int = Field(ge=1990, le=2100)
    organization_public_id: str
    exam_board_public_id: str | None = None
    slug: str | None = Field(default=None, max_length=140)
    status: str = Field(
        default="ANNOUNCED", pattern="^(ANNOUNCED|OPEN|IN_PROGRESS|CONCLUDED|CANCELED)$"
    )
    education_level: str | None = Field(
        default=None, pattern="^(FUNDAMENTAL|MEDIO|TECNICO|SUPERIOR)$"
    )
    vacancies_total: int | None = Field(default=None, ge=0)
    salary_max_cents: int | None = Field(default=None, ge=0)
    registration_start: date | None = None
    registration_end: date | None = None
    exam_date: date | None = None
    source_url: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    is_published: bool = False


class CompetitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    year: int | None = Field(default=None, ge=1990, le=2100)
    organization_public_id: str | None = None
    exam_board_public_id: str | None = None
    status: str | None = Field(
        default=None, pattern="^(ANNOUNCED|OPEN|IN_PROGRESS|CONCLUDED|CANCELED)$"
    )
    education_level: str | None = Field(
        default=None, pattern="^(FUNDAMENTAL|MEDIO|TECNICO|SUPERIOR)$"
    )
    vacancies_total: int | None = Field(default=None, ge=0)
    salary_max_cents: int | None = Field(default=None, ge=0)
    registration_start: date | None = None
    registration_end: date | None = None
    exam_date: date | None = None
    source_url: str | None = Field(default=None, max_length=500)
    notes: str | None = None
    is_published: bool | None = None
