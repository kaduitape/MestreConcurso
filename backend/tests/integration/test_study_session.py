"""Cronômetro de estudo: tempo real, pausa e efeito no progresso."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.study import StudySession
from tests.conftest import CapturingDispatcher
from tests.factories import (
    WEEKDAY_AVAILABILITY,
    RegisteredUser,
    create_admin,
    create_position_with_subjects,
    create_user,
)


async def _student_with_plan(
    client: AsyncClient, emails: CapturingDispatcher, email: str
) -> RegisteredUser:
    admin = await create_admin(client, emails, email=f"gestor.{email}")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email=email)
    created = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    assert created.status_code == 201, created.text
    return student


async def _first_task(client: AsyncClient, student: RegisteredUser) -> dict:
    mission = (await client.get("/api/v1/study/today", headers=student.auth_header)).json()
    assert mission["tasks"], "o plano deveria ter tarefas para hoje"
    return mission["tasks"][0]


async def test_session_lifecycle_counts_only_focus_time(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await _student_with_plan(client, emails, "sessao1@exemplo.com.br")
    task = await _first_task(client, student)

    started = await client.post(
        "/api/v1/study/sessions",
        headers=student.auth_header,
        json={"task_public_id": task["public_id"]},
    )
    assert started.status_code == 201
    session_id = started.json()["public_id"]
    assert started.json()["status"] == "RUNNING"
    assert started.json()["subject_label"] == task["subject_label"]

    # Simula 20 minutos de foco recuando o início da sessão.
    factory = get_session_factory()
    async with factory() as db:
        record = (
            await db.execute(select(StudySession).where(StudySession.public_id == session_id))
        ).scalar_one()
        record.started_at = datetime.now(UTC) - timedelta(minutes=20)
        await db.commit()

    paused = await client.post(
        f"/api/v1/study/sessions/{session_id}/pause", headers=student.auth_header
    )
    assert paused.status_code == 200
    assert paused.json()["status"] == "PAUSED"
    assert 19 * 60 <= paused.json()["focus_seconds"] <= 21 * 60

    resumed = await client.post(
        f"/api/v1/study/sessions/{session_id}/resume", headers=student.auth_header
    )
    assert resumed.json()["status"] == "RUNNING"

    finished = await client.post(
        f"/api/v1/study/sessions/{session_id}/finish",
        headers=student.auth_header,
        json={"notes": "Revisei crase"},
    )
    assert finished.status_code == 200
    assert finished.json()["status"] == "FINISHED"
    assert finished.json()["notes"] == "Revisei crase"
    # O tempo pausado não entra no foco.
    assert 19 * 60 <= finished.json()["focus_seconds"] <= 21 * 60


async def test_finished_session_feeds_task_and_progress(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await _student_with_plan(client, emails, "sessao2@exemplo.com.br")
    task = await _first_task(client, student)

    started = await client.post(
        "/api/v1/study/sessions",
        headers=student.auth_header,
        json={"task_public_id": task["public_id"]},
    )
    session_id = started.json()["public_id"]

    factory = get_session_factory()
    async with factory() as db:
        record = (
            await db.execute(select(StudySession).where(StudySession.public_id == session_id))
        ).scalar_one()
        record.started_at = datetime.now(UTC) - timedelta(minutes=task["planned_minutes"] + 5)
        await db.commit()

    await client.post(
        f"/api/v1/study/sessions/{session_id}/finish",
        headers=student.auth_header,
        json={},
    )

    mission = (await client.get("/api/v1/study/today", headers=student.auth_header)).json()
    updated = next(item for item in mission["tasks"] if item["public_id"] == task["public_id"])
    # Cumprido o tempo planejado, a tarefa é dada como concluída.
    assert updated["status"] == "DONE"
    assert updated["actual_minutes"] >= task["planned_minutes"]

    if task["subject_key"]:
        progress = (await client.get("/api/v1/study/progress", headers=student.auth_header)).json()
        row = next(item for item in progress if item["subject_key"] == task["subject_key"])
        assert row["studied_minutes"] >= task["planned_minutes"]
        assert row["last_studied_at"] is not None


async def test_only_one_session_at_a_time(client: AsyncClient, emails: CapturingDispatcher) -> None:
    student = await _student_with_plan(client, emails, "sessao3@exemplo.com.br")

    first = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    assert first.status_code == 201

    second = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "session_already_running"
    assert second.json()["error"]["details"]["session_public_id"] == first.json()["public_id"]


async def test_current_session_is_reported(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await _student_with_plan(client, emails, "sessao4@exemplo.com.br")

    empty = await client.get("/api/v1/study/sessions/current", headers=student.auth_header)
    assert empty.status_code == 200
    assert empty.json() is None

    started = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    current = await client.get("/api/v1/study/sessions/current", headers=student.auth_header)
    assert current.json()["public_id"] == started.json()["public_id"]


async def test_pause_requires_running_session(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await _student_with_plan(client, emails, "sessao5@exemplo.com.br")
    started = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    session_id = started.json()["public_id"]

    await client.post(f"/api/v1/study/sessions/{session_id}/pause", headers=student.auth_header)
    again = await client.post(
        f"/api/v1/study/sessions/{session_id}/pause", headers=student.auth_header
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "session_not_running"


async def test_absurdly_long_session_is_capped(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await _student_with_plan(client, emails, "sessao6@exemplo.com.br")
    started = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    session_id = started.json()["public_id"]

    # Cronômetro esquecido aberto por dois dias não vira 48 horas de estudo.
    factory = get_session_factory()
    async with factory() as db:
        record = (
            await db.execute(select(StudySession).where(StudySession.public_id == session_id))
        ).scalar_one()
        record.started_at = datetime.now(UTC) - timedelta(days=2)
        await db.commit()

    finished = await client.post(
        f"/api/v1/study/sessions/{session_id}/finish",
        headers=student.auth_header,
        json={},
    )
    assert finished.json()["focus_seconds"] == 6 * 3600


async def test_week_minutes_counts_real_focus(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await _student_with_plan(client, emails, "sessao7@exemplo.com.br")
    started = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    session_id = started.json()["public_id"]

    factory = get_session_factory()
    async with factory() as db:
        record = (
            await db.execute(select(StudySession).where(StudySession.public_id == session_id))
        ).scalar_one()
        record.started_at = datetime.now(UTC) - timedelta(minutes=45)
        await db.commit()

    await client.post(
        f"/api/v1/study/sessions/{session_id}/finish", headers=student.auth_header, json={}
    )
    response = await client.get("/api/v1/study/sessions/week-minutes", headers=student.auth_header)
    assert 44 <= response.json()["minutes"] <= 46
