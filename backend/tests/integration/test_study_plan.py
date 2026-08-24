"""Plano de estudo: geração, missão do dia, replanejamento e sprint."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.study import StudyTask, StudyTaskStatus
from tests.conftest import CapturingDispatcher
from tests.factories import (
    WEEKDAY_AVAILABILITY,
    create_admin,
    create_position_with_subjects,
    create_user,
)


async def _plan_from_position(
    client: AsyncClient, emails: CapturingDispatcher, *, student_email: str
) -> tuple[dict, dict]:
    admin = await create_admin(client, emails, email=f"gestor.{student_email}")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email=student_email)

    response = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), {"student": student, "position": position}


async def test_plan_is_generated_from_the_position_subjects(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    plan, _ = await _plan_from_position(client, emails, student_email="plano1@exemplo.com.br")

    assert plan["weekly_minutes_target"] == 840
    assert plan["total_planned_minutes"] > 0
    assert len(plan["availability"]) == 6
    assert plan["availability"][0]["label"] == "Segunda"

    shares = {share["name"]: share for share in plan["shares"]}
    assert set(shares) == {"Direito Penal", "Português", "Informática"}
    # Peso maior no edital resulta em mais tempo no plano.
    assert shares["Direito Penal"]["minutes"] > shares["Informática"]["minutes"]
    # E cada fatia explica de onde veio.
    assert set(shares["Direito Penal"]["breakdown"]) == {
        "peso_no_edital",
        "questoes_na_prova",
        "extensao_do_conteudo",
    }


async def test_today_mission_lists_the_day_tasks(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano2@exemplo.com.br")
    student = ctx["student"]

    response = await client.get("/api/v1/study/today", headers=student.auth_header)
    assert response.status_code == 200
    mission = response.json()

    assert mission["day"] == datetime.now(UTC).date().isoformat()
    assert mission["overdue_count"] == 0
    if mission["tasks"]:
        task = mission["tasks"][0]
        assert task["planned_minutes"] >= 15
        assert task["kind_label"]
        # Toda tarefa carrega o porquê de estar ali.
        assert task["score_breakdown"]


async def test_plan_requires_a_source(client: AsyncClient, emails: CapturingDispatcher) -> None:
    student = await create_user(client, emails, email="plano3@exemplo.com.br")
    response = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={"minutes_by_weekday": WEEKDAY_AVAILABILITY},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "plan_source_required"


async def test_plan_requires_available_time(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="gestor.plano4@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="plano4@exemplo.com.br")

    response = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": {"0": 0, "1": 0},
        },
    )
    assert response.status_code == 422


async def test_without_plan_endpoints_explain_instead_of_failing_silently(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="plano5@exemplo.com.br")
    response = await client.get("/api/v1/study/today", headers=student.auth_header)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_active_plan"


async def test_completing_a_task_updates_progress(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano6@exemplo.com.br")
    student = ctx["student"]

    mission = (await client.get("/api/v1/study/today", headers=student.auth_header)).json()
    task = next(item for item in mission["tasks"] if item["subject_key"])

    done = await client.post(
        f"/api/v1/study/tasks/{task['public_id']}/complete",
        headers=student.auth_header,
        json={"minutes": 25},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "DONE"
    assert done.json()["actual_minutes"] == 25

    progress = (await client.get("/api/v1/study/progress", headers=student.auth_header)).json()
    row = next(item for item in progress if item["subject_key"] == task["subject_key"])
    assert row["studied_minutes"] == 25
    assert row["tasks_done"] == 1
    assert 0 < row["completion"] <= 1


async def test_task_can_be_skipped_and_reopened(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano7@exemplo.com.br")
    student = ctx["student"]
    mission = (await client.get("/api/v1/study/today", headers=student.auth_header)).json()
    task_id = mission["tasks"][0]["public_id"]

    skipped = await client.post(f"/api/v1/study/tasks/{task_id}/skip", headers=student.auth_header)
    assert skipped.json()["status"] == "SKIPPED"

    reopened = await client.post(
        f"/api/v1/study/tasks/{task_id}/reopen", headers=student.auth_header
    )
    assert reopened.json()["status"] == "PENDING"
    assert reopened.json()["actual_minutes"] == 0


async def test_overdue_tasks_are_rescheduled_without_infinite_debt(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano8@exemplo.com.br")
    student = ctx["student"]
    today = datetime.now(UTC).date()

    # Simula uma semana perdida: as tarefas ficam para trás, pendentes.
    factory = get_session_factory()
    async with factory() as session:
        tasks = (await session.execute(select(StudyTask).limit(8))).scalars().all()
        for index, task in enumerate(tasks):
            task.scheduled_for = today - timedelta(days=(index % 7) + 1)
        await session.commit()

    response = await client.post("/api/v1/study/rebalance", headers=student.auth_header)
    assert response.status_code == 200
    result = response.json()

    assert result["rescheduled"] + result["dropped"] == 8
    assert result["summary"]

    async with factory() as session:
        remaining = (
            (
                await session.execute(
                    select(StudyTask).where(
                        StudyTask.scheduled_for < today,
                        StudyTask.status == StudyTaskStatus.PENDING,
                    )
                )
            )
            .scalars()
            .all()
        )
    # Nada continua "pendente no passado": ou foi remarcado ou saiu do plano.
    assert remaining == []


async def test_rebalance_without_overdue_is_a_noop(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano9@exemplo.com.br")
    response = await client.post("/api/v1/study/rebalance", headers=ctx["student"].auth_header)
    assert response.json()["rescheduled"] == 0
    assert response.json()["dropped"] == 0


async def test_sprint_creates_tasks_for_today(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano10@exemplo.com.br")
    student = ctx["student"]

    response = await client.post(
        "/api/v1/study/sprint", headers=student.auth_header, json={"minutes": 30}
    )
    assert response.status_code == 201
    blocks = response.json()

    assert sum(block["planned_minutes"] for block in blocks) == 30
    assert all(block["source"] == "SPRINT" for block in blocks)
    assert all(block["scheduled_for"] == datetime.now(UTC).date().isoformat() for block in blocks)


async def test_sprint_rejects_impossible_duration(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano11@exemplo.com.br")
    response = await client.post(
        "/api/v1/study/sprint", headers=ctx["student"].auth_header, json={"minutes": 5}
    )
    assert response.status_code == 422


async def test_calendar_groups_tasks_by_day(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano12@exemplo.com.br")
    student = ctx["student"]
    today = datetime.now(UTC).date()

    response = await client.get(
        f"/api/v1/study/calendar?start={today}&end={today + timedelta(days=14)}",
        headers=student.auth_header,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["start"] == today.isoformat()
    assert len(body["days"]) > 0
    for day in body["days"]:
        assert day["planned_minutes"] == sum(
            task["planned_minutes"] for task in day["tasks"] if task["status"] != "DROPPED"
        )


async def test_updating_availability_regenerates_the_future(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, ctx = await _plan_from_position(client, emails, student_email="plano13@exemplo.com.br")
    student = ctx["student"]

    updated = await client.patch(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={"minutes_by_weekday": {"5": 300, "6": 300}},
    )
    assert updated.status_code == 200
    body = updated.json()

    assert body["weekly_minutes_target"] == 600
    assert {item["weekday"] for item in body["availability"]} == {5, 6}
    assert body["recalculated_at"] is not None

    calendar = (await client.get("/api/v1/study/calendar", headers=student.auth_header)).json()
    future_weekdays = {
        date.fromisoformat(day["day"]).weekday()
        for day in calendar["days"]
        if date.fromisoformat(day["day"]) > datetime.now(UTC).date()
    }
    # A agenda futura passa a respeitar a nova disponibilidade.
    assert future_weekdays <= {5, 6}
