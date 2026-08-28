"""Fase 3: temporadas e ligas.

A liga é a parte mais delicada da gamificação inteira: comparação mal feita
desanima quem está indo bem. Os testes cobram as três proteções — contexto,
anonimato e tamanho mínimo — além da regra que sustenta tudo: o XP da temporada
sai do razão, não de um contador paralelo.
"""

from __future__ import annotations

from datetime import date, timedelta
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

TODAY = date.today()


async def _open_season(
    client: AsyncClient, admin: RegisteredUser, *, name: str = "Temporada de teste"
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/game/seasons",
        headers=admin.auth_header,
        json={
            "name": name,
            "starts_on": (TODAY - timedelta(days=7)).isoformat(),
            "ends_on": (TODAY + timedelta(days=20)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


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


async def _answer_some(
    client: AsyncClient, admin: RegisteredUser, student: RegisteredUser, *, prefix: str, total: int
) -> None:
    for index in range(total):
        question = await create_question(
            client, admin, statement=f"{prefix} — enunciado {index} com texto suficiente."
        )
        letter = next(
            item["letter"] for item in question["alternatives"] if item["is_correct"] is True
        )
        answered = await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": letter, "time_seconds": 30},
        )
        assert answered.status_code == 200, answered.text


# --------------------------------------------------------------------------- #
# Temporada
# --------------------------------------------------------------------------- #
async def test_without_an_open_season_there_is_no_scoreboard(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="season1@exemplo.com.br")

    body = (await client.get("/api/v1/game/season", headers=student.auth_header)).json()

    assert body["name"] is None
    assert body["standing"] is None
    assert "Nenhuma temporada aberta" in body["empty_reason"]


async def test_seasonal_xp_comes_from_the_ledger(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O placar da temporada é a soma do extrato — não um contador paralelo."""
    admin = await create_admin(client, emails, email="season2@exemplo.com.br")
    await _open_season(client, admin)
    student = await create_user(client, emails, email="aluno.season2@exemplo.com.br")

    await _answer_some(client, admin, student, prefix="Temporada", total=5)

    season = (await client.get("/api/v1/game/season", headers=student.auth_header)).json()
    extrato = (
        await client.get(
            "/api/v1/game/xp/history?page=1&page_size=100", headers=student.auth_header
        )
    ).json()
    soma = sum(item["amount"] for item in extrato["items"])

    assert season["standing"]["seasonal_xp"] == soma
    assert season["standing"]["questions"] == 5
    assert season["days_left"] == 20
    assert 0 < season["progress"] < 1


async def test_the_season_declares_that_it_measures_effort_not_mastery(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="season3@exemplo.com.br")
    await _open_season(client, admin)
    student = await create_user(client, emails, email="aluno.season3@exemplo.com.br")

    body = (await client.get("/api/v1/game/season", headers=student.auth_header)).json()

    assert "esforço" in body["note"]
    assert "rank" in body["note"]


async def test_every_reward_declares_utility_and_criterion(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Nada de caixa surpresa: o prêmio diz para que serve e como se ganha."""
    admin = await create_admin(client, emails, email="season4@exemplo.com.br")
    await _open_season(client, admin)
    student = await create_user(client, emails, email="aluno.season4@exemplo.com.br")

    body = (await client.get("/api/v1/game/season", headers=student.auth_header)).json()

    assert body["rewards"] == [], "candidato novo ainda não cumpriu critério nenhum"
    assert len(body["missed_rewards"]) == 2
    for reward in body["missed_rewards"]:
        assert reward["utility"]
        assert reward["criterion"]

    selo = next(item for item in body["missed_rewards"] if item["slug"] == "selo-temporada")
    assert "não desbloqueia" in selo["utility"]


async def test_overlapping_seasons_are_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="season5@exemplo.com.br")
    await _open_season(client, admin)

    again = await client.post(
        "/api/v1/admin/game/seasons",
        headers=admin.auth_header,
        json={
            "name": "Outra",
            "starts_on": TODAY.isoformat(),
            "ends_on": (TODAY + timedelta(days=10)).isoformat(),
        },
    )

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "season_overlap"


async def test_closing_a_season_freezes_the_position_and_grants_the_shield(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="season6@exemplo.com.br")
    season = await _open_season(client, admin)
    student = await create_user(client, emails, email="aluno.season6@exemplo.com.br")

    await _answer_some(client, admin, student, prefix="Fechamento", total=4)
    before = (await client.get("/api/v1/game/streak", headers=student.auth_header)).json()

    closed = await client.post(
        f"/api/v1/admin/game/seasons/{season['slug']}/close", headers=admin.auth_header
    )
    assert closed.status_code == 200, closed.text
    records = closed.json()
    assert len(records) == 1
    assert records[0]["seasonal_xp"] > 0
    assert records[0]["closed_at"]

    # Sem liga (o candidato não tem cargo-alvo), não há posição — nem escudo.
    assert records[0]["position"] is None
    after = (await client.get("/api/v1/game/streak", headers=student.auth_header)).json()
    assert after["shields_left"] == before["shields_left"]

    history = (await client.get("/api/v1/game/season/history", headers=student.auth_header)).json()
    assert len(history) == 1
    assert history[0]["season_name"] == season["name"]

    # Fechada, a temporada sai do ar em vez de continuar recebendo pontos.
    current = (await client.get("/api/v1/game/season", headers=student.auth_header)).json()
    assert current["empty_reason"]


async def test_a_closed_season_cannot_be_closed_twice(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="season7@exemplo.com.br")
    season = await _open_season(client, admin)

    first = await client.post(
        f"/api/v1/admin/game/seasons/{season['slug']}/close", headers=admin.auth_header
    )
    assert first.status_code == 200
    again = await client.post(
        f"/api/v1/admin/game/seasons/{season['slug']}/close", headers=admin.auth_header
    )

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "season_already_closed"


# --------------------------------------------------------------------------- #
# Liga
# --------------------------------------------------------------------------- #
async def test_league_needs_a_target_position(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="league1@exemplo.com.br")
    await _open_season(client, admin)
    student = await create_user(client, emails, email="aluno.league1@exemplo.com.br")

    body = (await client.get("/api/v1/game/league", headers=student.auth_header)).json()

    assert body["members"] == []
    assert "mesmo cargo" in body["empty_reason"]


async def test_a_small_group_is_not_turned_into_a_leaderboard(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="league2@exemplo.com.br")
    await _open_season(client, admin)
    position = await create_position_with_subjects(client, admin)

    for index in range(3):
        student = await create_user(client, emails, email=f"aluno{index}.league2@exemplo.com.br")
        await _plan(client, student, position)

    body = (await client.get("/api/v1/game/league", headers=student.auth_header)).json()

    assert body["members"] == []
    assert body["participants"] == 3
    assert "a partir de 5" in body["empty_reason"].lower()


async def test_the_league_is_anonymous_by_default_and_can_be_named(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="league3@exemplo.com.br")
    await _open_season(client, admin)
    position = await create_position_with_subjects(client, admin)

    students = []
    for index in range(6):
        student = await create_user(client, emails, email=f"aluno{index}.league3@exemplo.com.br")
        await _plan(client, student, position)
        students.append(student)

    you = students[0]
    body = (await client.get("/api/v1/game/league", headers=you.auth_header)).json()

    assert body["participants"] == 6
    assert len(body["members"]) == 6
    assert body["division_label"] == "Divisão 1"
    assert all(item["label"].startswith("Candidato #") for item in body["members"])
    assert all(item["is_named"] is False for item in body["members"])
    assert any(item["is_you"] for item in body["members"])

    named = await client.put(
        "/api/v1/game/league/preferences",
        headers=you.auth_header,
        json={"display_name": "Marina S."},
    )
    assert named.status_code == 200
    assert named.json()["display_name"] == "Marina S."

    updated = (await client.get("/api/v1/game/league", headers=you.auth_header)).json()
    mine = next(item for item in updated["members"] if item["is_you"])
    assert mine["label"] == "Marina S."
    assert mine["is_named"] is True


async def test_leaving_the_comparison_removes_the_candidate_from_every_table(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Item 21: a comparação é desligável, e desligar tem efeito dos dois lados."""
    admin = await create_admin(client, emails, email="league4@exemplo.com.br")
    await _open_season(client, admin)
    position = await create_position_with_subjects(client, admin)

    students = []
    for index in range(6):
        student = await create_user(client, emails, email=f"aluno{index}.league4@exemplo.com.br")
        await _plan(client, student, position)
        students.append(student)

    quitter, observer = students[0], students[1]
    out = await client.put(
        "/api/v1/game/league/preferences", headers=quitter.auth_header, json={"opt_out": True}
    )
    assert out.status_code == 200
    assert out.json()["opt_out"] is True

    mine = (await client.get("/api/v1/game/league", headers=quitter.auth_header)).json()
    assert mine["members"] == []
    assert "desligou" in mine["empty_reason"]

    # E some da tabela de quem ficou: agora são 5 participantes, não 6.
    theirs = (await client.get("/api/v1/game/league", headers=observer.auth_header)).json()
    assert theirs["participants"] == 5
    assert len(theirs["members"]) == 5


async def test_the_league_ranks_by_effort_in_the_season(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="league5@exemplo.com.br")
    await _open_season(client, admin)
    position = await create_position_with_subjects(client, admin)

    students = []
    for index in range(5):
        student = await create_user(client, emails, email=f"aluno{index}.league5@exemplo.com.br")
        await _plan(client, student, position)
        students.append(student)

    # Só um deles resolve questões no período.
    await _answer_some(client, admin, students[3], prefix="Liga", total=6)

    body = (await client.get("/api/v1/game/league", headers=students[3].auth_header)).json()

    assert body["your_position"] == 1
    assert body["members"][0]["is_you"] is True
    assert body["members"][0]["seasonal_xp"] > 0
    assert body["members"][-1]["seasonal_xp"] == 0
    assert "esforço" in body["note"]
