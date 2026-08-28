"""Fase 2 da gamificação: histórico de rank, Você vs Banca, jornada e mapa.

Estas telas são comparativas, e é aí que mora o risco: comparar com amostra
pequena produz afirmação falsa com cara de gráfico. Os testes abaixo cobram o
contrário — sem amostra, a tela diz que não sabe.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    WEEKDAY_AVAILABILITY,
    RegisteredUser,
    create_admin,
    create_position_with_subjects,
    create_question,
    create_user,
)


async def _plan(client: AsyncClient, student: RegisteredUser, position: dict[str, Any]) -> None:
    response = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    assert response.status_code in (200, 201), response.text


async def _answer(
    client: AsyncClient, student: RegisteredUser, question: dict[str, Any], *, correct: bool
) -> None:
    letter = next(
        item["letter"] for item in question["alternatives"] if item["is_correct"] is correct
    )
    response = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": letter, "time_seconds": 40},
    )
    assert response.status_code == 200, response.text


async def _answer_batch(
    client: AsyncClient,
    admin: RegisteredUser,
    student: RegisteredUser,
    *,
    prefix: str,
    total: int,
    correct: int,
    board_slug: str | None = None,
    subject_public_id: str | None = None,
) -> None:
    """Cria e responde ``total`` questões distintas, acertando ``correct`` delas."""
    for index in range(total):
        extra: dict[str, Any] = {}
        if board_slug is not None:
            extra["board_slug"] = board_slug
        if subject_public_id is not None:
            extra["subject_public_id"] = subject_public_id
        question = await create_question(
            client,
            admin,
            statement=f"{prefix} — enunciado número {index} com texto suficiente.",
            **extra,
        )
        await _answer(client, student, question, correct=index < correct)


# --------------------------------------------------------------------------- #
# Histórico de rank
# --------------------------------------------------------------------------- #
async def test_rank_history_declares_that_one_measurement_is_not_a_trend(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="prog1@exemplo.com.br")

    response = await client.get("/api/v1/game/rank/history", headers=student.auth_header)
    assert response.status_code == 200, response.text
    body = response.json()

    # A foto de hoje é gravada, mas uma foto não é evolução.
    assert len(body["points"]) == 1
    assert body["delta"] is None
    assert body["empty_reason"]
    assert body["points"][0]["rank_slug"] == "FERRO"


async def test_rank_history_keeps_one_snapshot_per_day(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="prog2@exemplo.com.br")

    for _ in range(3):
        assert (
            await client.get("/api/v1/game/rank/history", headers=student.auth_header)
        ).status_code == 200

    body = (await client.get("/api/v1/game/rank/history", headers=student.auth_header)).json()
    assert len(body["points"]) == 1


async def test_rank_history_shows_xp_and_rank_side_by_side(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """XP acumula com o estudo; o rank só se move com desempenho."""
    admin = await create_admin(client, emails, email="prog3@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.prog3@exemplo.com.br")

    await _answer_batch(client, admin, student, prefix="XP sem rank", total=6, correct=3)

    body = (await client.get("/api/v1/game/rank/history", headers=student.auth_header)).json()
    point = body["points"][-1]

    assert point["xp_total"] > 0, "responder questões rende XP"
    # 6 respostas estão longe da amostra mínima do rank: o score continua zerado.
    assert point["rank_score"] == 0
    assert point["rank_slug"] == "FERRO"


# --------------------------------------------------------------------------- #
# Você vs Banca
# --------------------------------------------------------------------------- #
async def test_board_battle_requires_a_target_competition(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="prog4@exemplo.com.br")

    body = (await client.get("/api/v1/game/board-battle", headers=student.auth_header)).json()

    assert body["is_sufficient"] is False
    assert body["is_winning"] is False
    assert body["you"] == 0 and body["board"] == 0
    assert "concurso-alvo" in body["empty_reason"]


async def test_board_battle_refuses_to_declare_a_score_without_sample(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog5@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog5@exemplo.com.br")
    await _plan(client, student, position)

    await _answer_batch(
        client, admin, student, prefix="Amostra curta", total=5, correct=5, board_slug="cespe"
    )

    body = (await client.get("/api/v1/game/board-battle", headers=student.auth_header)).json()

    assert body["board_name"] == "Cebraspe"
    assert body["answers"] == 5
    assert body["is_sufficient"] is False
    assert body["is_winning"] is False, "5 acertos não fazem ninguém ganhar da banca"
    assert body["empty_reason"]


async def test_board_battle_score_is_real_accuracy_and_sums_one_hundred(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog6@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog6@exemplo.com.br")
    await _plan(client, student, position)

    await _answer_batch(
        client, admin, student, prefix="Placar real", total=40, correct=26, board_slug="cespe"
    )

    body = (await client.get("/api/v1/game/board-battle", headers=student.auth_header)).json()

    assert body["is_sufficient"] is True
    assert body["answers"] == 40 and body["correct"] == 26
    assert body["you"] == 65
    assert body["you"] + body["board"] == 100
    # Os pontos da banca são exatamente os erros — nada de adversário simulado.
    assert body["board"] == round((40 - 26) / 40 * 100)
    assert body["is_winning"] is True
    assert body["evolution"], "a evolução semanal acompanha o placar"


async def test_board_battle_ignores_questions_from_other_boards(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog7@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog7@exemplo.com.br")
    await _plan(client, student, position)

    outra = await client.post(
        "/api/v1/admin/catalog/boards",
        headers=admin.auth_header,
        json={"name": "Fundação Getúlio Vargas", "short_name": "FGV"},
    )
    assert outra.status_code == 201, outra.text

    await _answer_batch(
        client, admin, student, prefix="Da banca alvo", total=30, correct=30, board_slug="cespe"
    )
    await _answer_batch(
        client,
        admin,
        student,
        prefix="De outra banca",
        total=20,
        correct=0,
        board_slug="fgv",
    )

    body = (await client.get("/api/v1/game/board-battle", headers=student.auth_header)).json()

    assert body["answers"] == 30, "só entram as questões da banca do concurso-alvo"
    assert body["you"] == 100


# --------------------------------------------------------------------------- #
# Jornada da aprovação
# --------------------------------------------------------------------------- #
async def test_journey_without_a_plan_invents_nothing(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="prog8@exemplo.com.br")

    body = (await client.get("/api/v1/game/journey", headers=student.auth_header)).json()

    assert body["milestones"] == []
    assert body["completed"] == 0
    assert body["empty_reason"]


async def test_journey_never_promises_approval(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog9@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog9@exemplo.com.br")
    await _plan(client, student, position)

    body = (await client.get("/api/v1/game/journey", headers=student.auth_header)).json()

    assert body["disclaimer"]
    assert "não são previsão de aprovação" in body["disclaimer"].lower()

    texto = " ".join(
        f"{item['label']} {item['description']} {item['detail']}" for item in body["milestones"]
    ).lower()
    for proibido in ("você vai passar", "será aprovado", "aprovação garantida", "chance de"):
        assert proibido not in texto


async def test_journey_advances_only_with_real_activity(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog10@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog10@exemplo.com.br")
    await _plan(client, student, position)

    before = (await client.get("/api/v1/game/journey", headers=student.auth_header)).json()
    assert before["current_key"] == "first_study"
    assert before["completed"] == 0

    started = await client.post("/api/v1/study/sessions", headers=student.auth_header, json={})
    assert started.status_code == 201, started.text
    public_id = started.json()["public_id"]

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.study import StudySession

    factory = get_session_factory()
    async with factory() as session:
        record = (
            await session.execute(select(StudySession).where(StudySession.public_id == public_id))
        ).scalar_one()
        record.started_at = datetime.now(UTC) - timedelta(minutes=40)
        await session.commit()

    finished = await client.post(
        f"/api/v1/study/sessions/{public_id}/finish", headers=student.auth_header, json={}
    )
    assert finished.status_code == 200, finished.text

    after = (await client.get("/api/v1/game/journey", headers=student.auth_header)).json()
    first = next(item for item in after["milestones"] if item["key"] == "first_study")
    assert first["state"] == "DONE"
    assert after["completed"] == 1
    assert after["current_key"] == "hundred_questions"


# --------------------------------------------------------------------------- #
# Mapa do edital
# --------------------------------------------------------------------------- #
async def test_territory_map_needs_a_plan_to_exist(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="prog11@exemplo.com.br")

    body = (await client.get("/api/v1/game/territory", headers=student.auth_header)).json()

    assert body["territories"] == []
    assert body["empty_reason"]


async def test_territory_map_starts_locked_and_declares_missing_signals(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog12@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog12@exemplo.com.br")
    await _plan(client, student, position)

    body = (await client.get("/api/v1/game/territory", headers=student.auth_header)).json()

    assert body["territories"], "as disciplinas do plano viram territórios"
    assert body["mastered"] == 0
    assert body["needs_review"] == 0

    for territory in body["territories"]:
        assert territory["state"] == "LOCKED"
        assert territory["mastery"] == 0
        assert territory["note"]
        # Sem questões nem revisões, os dois sinais são declarados ausentes.
        assert set(territory["missing_signals"]) == {"desempenho", "retencao"}
        for part in territory["parts"]:
            assert part["detail"]
            if not part["available"]:
                assert part["value"] is None
                assert part["points"] == 0


async def test_territory_parts_sum_to_the_displayed_mastery(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="prog13@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.prog13@exemplo.com.br")
    await _plan(client, student, position)

    body = (await client.get("/api/v1/game/territory", headers=student.auth_header)).json()

    for territory in body["territories"]:
        disponivel = sum(part["weight"] for part in territory["parts"] if part["available"])
        soma = sum(part["points"] for part in territory["parts"])
        esperado = round(soma / disponivel, 4) if disponivel else 0.0
        assert abs(territory["mastery"] - esperado) < 1e-6
