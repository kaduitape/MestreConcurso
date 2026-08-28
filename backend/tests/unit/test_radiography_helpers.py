"""Cálculos do Raio-X — todos determinísticos, feitos em Python."""

from __future__ import annotations

from datetime import date

from app.models.notice_analysis import EvidenceLevel, NoticeFact
from app.services.radiography import SubjectView, build_attention_points, days_between


def _fact(field_path: str, label: str, level: str, value: object = None) -> NoticeFact:
    return NoticeFact(
        notice_id=1,
        field_path=field_path,
        label=label,
        value={"raw": value},
        evidence_level=level,
    )


def _subject(name: str, topics: int) -> SubjectView:
    return SubjectView(
        public_id="X",
        name=name,
        weight=None,
        questions_count=None,
        topics_count=topics,
        topics=[],
        evidence_level=EvidenceLevel.OFFICIAL,
        page_number=1,
    )


def test_days_between_counts_forward_and_backward() -> None:
    today = date(2026, 3, 1)
    assert days_between(date(2026, 3, 15), today=today) == 14
    assert days_between(date(2026, 2, 25), today=today) == -4
    assert days_between(None, today=today) is None


def test_attention_points_report_missing_and_inferred() -> None:
    points = build_attention_points(
        [
            _fact("exam.date", "Data da prova", EvidenceLevel.NOT_FOUND),
            _fact("position.vacancies", "Vagas", EvidenceLevel.INFERRED, 100),
        ],
        [],
        [],
    )
    kinds = {point["kind"] for point in points}
    assert kinds == {"MISSING_FIELDS", "NEEDS_REVIEW"}


def test_attention_point_for_elimination_rule() -> None:
    points = build_attention_points(
        [
            _fact(
                "elimination.rules",
                "Critérios de eliminação",
                EvidenceLevel.OFFICIAL,
                "Nota inferior a 50% elimina",
            )
        ],
        [],
        [],
    )
    assert any(point["kind"] == "ELIMINATION" for point in points)


def test_attention_point_for_subjects_without_topics() -> None:
    points = build_attention_points([], [_subject("Informática", 0)], [])
    assert any(point["kind"] == "SUBJECTS_WITHOUT_TOPICS" for point in points)


def test_no_attention_points_when_everything_is_proven() -> None:
    points = build_attention_points(
        [_fact("exam.date", "Data da prova", EvidenceLevel.OFFICIAL, "2026-03-15")],
        [_subject("Português", 4)],
        [],
    )
    assert points == []
