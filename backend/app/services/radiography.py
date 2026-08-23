"""Raio-X do edital: leitura consolidada do que foi extraído.

Tudo aqui é cálculo em Python sobre o que está no banco — contagens, ordenações,
dias restantes, cobertura da extração. Nenhum número é pedido a um modelo, e todo
valor exibido carrega o nível de prova de onde veio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError
from app.models.document import Document
from app.models.notice import Notice, NoticeStatus
from app.models.notice_analysis import (
    EvidenceLevel,
    NoticeEvent,
    NoticeFact,
    NoticeSubject,
)
from app.services.evidence import coverage_summary


@dataclass(frozen=True, slots=True)
class FactView:
    id: int
    field_path: str
    label: str
    value: Any
    evidence_level: str
    page_number: int | None
    quote: str | None
    confidence: float | None
    extracted_by: str
    model_slug: str | None = None
    prompt_version: str | None = None


@dataclass(frozen=True, slots=True)
class SubjectView:
    public_id: str
    name: str
    weight: float | None
    questions_count: int | None
    topics_count: int
    topics: list[str]
    evidence_level: str
    page_number: int | None


@dataclass(frozen=True, slots=True)
class EventView:
    kind: str
    title: str
    date_start: date | None
    date_end: date | None
    is_critical: bool
    days_until: int | None
    evidence_level: str
    page_number: int | None


@dataclass(frozen=True, slots=True)
class Radiography:
    notice_public_id: str
    title: str
    status: str
    exam_date: date | None
    days_until_exam: int | None
    page_count: int | None
    subjects_count: int
    topics_count: int
    questions_count: int | None
    vacancies: int | None
    salary_cents: int | None
    facts: list[FactView] = field(default_factory=list)
    subjects: list[SubjectView] = field(default_factory=list)
    events: list[EventView] = field(default_factory=list)
    critical_events: list[EventView] = field(default_factory=list)
    largest_subjects: list[SubjectView] = field(default_factory=list)
    attention_points: list[dict[str, str]] = field(default_factory=list)
    coverage: dict[str, float | int] = field(default_factory=dict)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        digits = "".join(char for char in value if char.isdigit())
        return int(digits) if digits else None
    if isinstance(value, float):
        return int(value)
    return None


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def days_between(target: date | None, *, today: date | None = None) -> int | None:
    """Dias restantes até a data. Cálculo determinístico, nunca estimado por IA."""
    if target is None:
        return None
    reference = today or datetime.now(UTC).date()
    return (target - reference).days


class RadiographyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def build(self, notice: Notice, *, today: date | None = None) -> Radiography:
        if notice.status in {NoticeStatus.DRAFT, NoticeStatus.QUEUED}:
            raise ConflictError("Este edital ainda não foi analisado.", code="notice_not_analyzed")

        facts = list(
            (
                await self.session.execute(
                    select(NoticeFact)
                    .where(NoticeFact.notice_id == notice.id)
                    .order_by(NoticeFact.field_path)
                )
            )
            .scalars()
            .all()
        )
        subjects = list(
            (
                await self.session.execute(
                    select(NoticeSubject)
                    .where(NoticeSubject.notice_id == notice.id)
                    .options(selectinload(NoticeSubject.topics))
                    .order_by(NoticeSubject.order_index)
                )
            )
            .scalars()
            .all()
        )
        events = list(
            (
                await self.session.execute(
                    select(NoticeEvent)
                    .where(NoticeEvent.notice_id == notice.id)
                    .order_by(NoticeEvent.date_start)
                )
            )
            .scalars()
            .all()
        )
        document = (
            (
                await self.session.execute(
                    select(Document).where(
                        Document.owner_type == "notice", Document.owner_id == notice.id
                    )
                )
            )
            .scalars()
            .first()
        )

        by_path = {fact.field_path: fact for fact in facts}

        def value_of(path: str) -> Any:
            fact = by_path.get(path)
            if fact is None or fact.evidence_level == EvidenceLevel.NOT_FOUND:
                return None
            return (fact.value or {}).get("raw")

        exam_date = _as_date(value_of("exam.date"))
        subject_views = [
            SubjectView(
                public_id=subject.public_id,
                name=subject.raw_label,
                weight=float(subject.weight) if subject.weight is not None else None,
                questions_count=subject.questions_count,
                topics_count=len(subject.topics),
                topics=[topic.raw_label for topic in subject.topics],
                evidence_level=subject.evidence_level,
                page_number=subject.page_number,
            )
            for subject in subjects
        ]
        event_views = [
            EventView(
                kind=event.kind,
                title=event.title,
                date_start=event.date_start,
                date_end=event.date_end,
                is_critical=event.is_critical,
                days_until=days_between(event.date_start, today=today),
                evidence_level=event.evidence_level,
                page_number=event.page_number,
            )
            for event in events
        ]

        return Radiography(
            notice_public_id=notice.public_id,
            title=notice.title,
            status=notice.status,
            exam_date=exam_date,
            days_until_exam=days_between(exam_date, today=today),
            page_count=document.page_count if document else None,
            subjects_count=len(subject_views),
            topics_count=sum(view.topics_count for view in subject_views),
            questions_count=_as_int(value_of("exam.questions_count")),
            vacancies=_as_int(value_of("position.vacancies")),
            salary_cents=_as_int(value_of("position.salary_cents")),
            facts=[
                FactView(
                    id=fact.id,
                    field_path=fact.field_path,
                    label=fact.label,
                    value=(fact.value or {}).get("raw"),
                    evidence_level=fact.evidence_level,
                    page_number=fact.page_number,
                    quote=fact.quote,
                    confidence=float(fact.confidence) if fact.confidence else None,
                    extracted_by=fact.extracted_by,
                    model_slug=fact.model_slug,
                    prompt_version=fact.prompt_version,
                )
                for fact in facts
            ],
            subjects=subject_views,
            events=event_views,
            critical_events=[view for view in event_views if view.is_critical],
            largest_subjects=sorted(
                subject_views,
                key=lambda view: (view.topics_count, view.questions_count or 0),
                reverse=True,
            )[:5],
            attention_points=build_attention_points(facts, subject_views, event_views),
            coverage=coverage_summary([fact.evidence_level for fact in facts]),
        )


def build_attention_points(
    facts: list[NoticeFact],
    subjects: list[SubjectView],
    events: list[EventView],
) -> list[dict[str, str]]:
    """Alertas derivados do que foi (ou não foi) encontrado — sem opinião de modelo."""
    points: list[dict[str, str]] = []

    missing = [fact.label for fact in facts if fact.evidence_level == EvidenceLevel.NOT_FOUND]
    if missing:
        points.append(
            {
                "kind": "MISSING_FIELDS",
                "title": f"{len(missing)} campo(s) não localizados no edital",
                "detail": ", ".join(missing[:6]),
            }
        )

    inferred = [fact.label for fact in facts if fact.evidence_level == EvidenceLevel.INFERRED]
    if inferred:
        points.append(
            {
                "kind": "NEEDS_REVIEW",
                "title": f"{len(inferred)} campo(s) inferidos precisam de conferência",
                "detail": ", ".join(inferred[:6]),
            }
        )

    elimination = next((fact for fact in facts if fact.field_path == "elimination.rules"), None)
    if elimination and elimination.evidence_level in {
        EvidenceLevel.OFFICIAL,
        EvidenceLevel.CONFIRMED,
    }:
        points.append(
            {
                "kind": "ELIMINATION",
                "title": "Há regra eliminatória no edital",
                "detail": str((elimination.value or {}).get("raw") or "")[:220],
            }
        )

    physical = [event for event in events if event.kind == "PHYSICAL_TEST"]
    if physical:
        points.append(
            {
                "kind": "PHYSICAL_TEST",
                "title": "Teste de aptidão física previsto",
                "detail": physical[0].title,
            }
        )

    without_topics = [view.name for view in subjects if view.topics_count == 0]
    if without_topics:
        points.append(
            {
                "kind": "SUBJECTS_WITHOUT_TOPICS",
                "title": f"{len(without_topics)} disciplina(s) sem conteúdo programático extraído",
                "detail": ", ".join(without_topics[:6]),
            }
        )

    return points
