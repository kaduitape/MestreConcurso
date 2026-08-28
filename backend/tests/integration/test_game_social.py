"""Fase 4: duelos, eventos, Modo Guerra e card compartilhável.

Metade destes testes existe por causa do card: ele sai da plataforma e vai para
um lugar onde ninguém pode conferir o contexto. É o ponto onde um número inflado
custaria mais caro.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    create_admin,
    create_question,
    create_user,
)

TODAY = date.today()


async def _stock(client: AsyncClient, admin: RegisteredUser, *, total: int, prefix: str) -> None:
    for index in range(total):
        await create_question(
            client, admin, statement=f"{prefix} — enunciado {index} com texto suficiente."
        )


async def _answer_run(
    client: AsyncClient,
    student: RegisteredUser,
    run: dict[str, Any],
    *,
    correct: bool,
    seconds: int = 20,
) -> dict[str, Any]:
    question = run["question"]
    letter = (
        "A"
        if correct
        else next(item["letter"] for item in question["alternatives"] if item["letter"] != "A")
    )
    response = await client.post(
        f"/api/v1/game/challenges/runs/{run['public_id']}/answer",
        headers=student.auth_header,
        json={
            "question_public_id": question["public_id"],
            "letter": letter,
            "time_seconds": seconds,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["run"]


async def _play_duel_side(
    client: AsyncClient, student: RegisteredUser, duel: dict[str, Any], *, correct: int
) -> None:
    """Responde a rodada inteira daquele lado, acertando ``correct`` questões."""
    run = duel["my_run"]
    assert run is not None
    index = 0
    while run["question"] is not None:
        run = await _answer_run(client, student, run, correct=index < correct)
        index += 1


# --------------------------------------------------------------------------- #
# Duelos
# --------------------------------------------------------------------------- #
async def test_a_duel_needs_enough_questions_to_exist(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="duel1@exemplo.com.br")
    await _stock(client, admin, total=4, prefix="Duelo curto")
    student = await create_user(client, emails, email="aluno.duel1@exemplo.com.br")

    response = await client.post("/api/v1/game/duels", headers=student.auth_header)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_enough_questions"


async def test_both_sides_answer_the_same_questions(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Um duelo com listas diferentes compararia sortes, não candidatos."""
    admin = await create_admin(client, emails, email="duel2@exemplo.com.br")
    await _stock(client, admin, total=20, prefix="Mesmas questões")
    ana = await create_user(client, emails, email="ana.duel2@exemplo.com.br")
    bruno = await create_user(client, emails, email="bruno.duel2@exemplo.com.br")

    created = (await client.post("/api/v1/game/duels", headers=ana.auth_header)).json()
    accepted = (
        await client.post(
            "/api/v1/game/duels/accept",
            headers=bruno.auth_header,
            json={"code": created["code"]},
        )
    ).json()

    assert created["my_run"]["question"]["public_id"] == accepted["my_run"]["question"]["public_id"]
    assert accepted["status"] == "RUNNING"


async def test_the_result_waits_for_both_sides(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="duel3@exemplo.com.br")
    await _stock(client, admin, total=20, prefix="Espera")
    ana = await create_user(client, emails, email="ana.duel3@exemplo.com.br")
    bruno = await create_user(client, emails, email="bruno.duel3@exemplo.com.br")

    created = (await client.post("/api/v1/game/duels", headers=ana.auth_header)).json()
    await client.post(
        "/api/v1/game/duels/accept", headers=bruno.auth_header, json={"code": created["code"]}
    )

    view = (
        await client.get(f"/api/v1/game/duels/{created['public_id']}", headers=ana.auth_header)
    ).json()
    await _play_duel_side(client, ana, view, correct=8)

    after = (
        await client.get(f"/api/v1/game/duels/{created['public_id']}", headers=ana.auth_header)
    ).json()

    assert after["outcome"] == "UNDECIDED"
    assert after["you_won"] is None
    assert any("só é declarado" in line for line in after["lines"])


async def test_the_duel_is_decided_by_real_answers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="duel4@exemplo.com.br")
    await _stock(client, admin, total=20, prefix="Placar")
    ana = await create_user(client, emails, email="ana.duel4@exemplo.com.br")
    bruno = await create_user(client, emails, email="bruno.duel4@exemplo.com.br")

    created = (await client.post("/api/v1/game/duels", headers=ana.auth_header)).json()
    accepted = (
        await client.post(
            "/api/v1/game/duels/accept",
            headers=bruno.auth_header,
            json={"code": created["code"]},
        )
    ).json()

    await _play_duel_side(client, ana, created, correct=9)
    await _play_duel_side(client, bruno, accepted, correct=4)

    final = (
        await client.get(f"/api/v1/game/duels/{created['public_id']}", headers=ana.auth_header)
    ).json()

    assert final["status"] == "FINISHED"
    assert final["outcome"] == "WIN"
    assert final["you_won"] is True
    assert final["challenger"]["correct"] == 9
    assert final["opponent"]["correct"] == 4
    assert "9 a 4" in final["headline"]

    # O outro lado vê o mesmo resultado, do ponto de vista dele.
    other = (
        await client.get(f"/api/v1/game/duels/{created['public_id']}", headers=bruno.auth_header)
    ).json()
    assert other["you_won"] is False
    assert other["is_challenger"] is False


async def test_a_duel_cannot_be_accepted_twice_or_by_its_author(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="duel5@exemplo.com.br")
    await _stock(client, admin, total=20, prefix="Aceite")
    ana = await create_user(client, emails, email="ana.duel5@exemplo.com.br")
    bruno = await create_user(client, emails, email="bruno.duel5@exemplo.com.br")
    carla = await create_user(client, emails, email="carla.duel5@exemplo.com.br")

    created = (await client.post("/api/v1/game/duels", headers=ana.auth_header)).json()

    mine = await client.post(
        "/api/v1/game/duels/accept", headers=ana.auth_header, json={"code": created["code"]}
    )
    assert mine.status_code == 422
    assert mine.json()["error"]["code"] == "cannot_duel_yourself"

    first = await client.post(
        "/api/v1/game/duels/accept", headers=bruno.auth_header, json={"code": created["code"]}
    )
    assert first.status_code == 200

    late = await client.post(
        "/api/v1/game/duels/accept", headers=carla.auth_header, json={"code": created["code"]}
    )
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "duel_already_taken"


async def test_a_duel_is_private_to_its_two_sides(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="duel6@exemplo.com.br")
    await _stock(client, admin, total=20, prefix="Privado")
    ana = await create_user(client, emails, email="ana.duel6@exemplo.com.br")
    estranho = await create_user(client, emails, email="estranho.duel6@exemplo.com.br")

    created = (await client.post("/api/v1/game/duels", headers=ana.auth_header)).json()

    response = await client.get(
        f"/api/v1/game/duels/{created['public_id']}", headers=estranho.auth_header
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Eventos
# --------------------------------------------------------------------------- #
async def test_an_event_reward_must_declare_what_it_is_for(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="event1@exemplo.com.br")

    response = await client.post(
        "/api/v1/admin/game/events",
        headers=admin.auth_header,
        json={
            "name": "Semana intensiva",
            "starts_on": TODAY.isoformat(),
            "ends_on": (TODAY + timedelta(days=6)).isoformat(),
            "goals": [{"metric": "questions", "target": 50}],
            "reward_label": "Selo da semana",
        },
    )

    assert response.status_code == 422
    assert "declarar para que serve" in response.json()["error"]["message"]


async def test_an_event_only_accepts_known_metrics(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="event2@exemplo.com.br")

    response = await client.post(
        "/api/v1/admin/game/events",
        headers=admin.auth_header,
        json={
            "name": "Evento fantasia",
            "starts_on": TODAY.isoformat(),
            "ends_on": (TODAY + timedelta(days=6)).isoformat(),
            "goals": [{"metric": "sorte", "target": 10}],
        },
    )

    assert response.status_code == 422
    assert "Métrica desconhecida" in response.json()["error"]["message"]


async def test_event_progress_comes_from_real_activity(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="event3@exemplo.com.br")
    created = await client.post(
        "/api/v1/admin/game/events",
        headers=admin.auth_header,
        json={
            "name": "Semana de questões",
            "starts_on": TODAY.isoformat(),
            "ends_on": (TODAY + timedelta(days=6)).isoformat(),
            "goals": [{"metric": "questions", "target": 4}],
            "reward_label": "Selo da semana",
            "reward_utility": "Marca visual no perfil. Não altera o rank.",
        },
    )
    assert created.status_code == 201, created.text
    student = await create_user(client, emails, email="aluno.event3@exemplo.com.br")

    before = (await client.get("/api/v1/game/events", headers=student.auth_header)).json()
    assert len(before) == 1
    assert before[0]["goals"][0]["current"] == 0
    assert before[0]["completed"] is False
    assert "não altera o seu rank" in before[0]["note"]

    for index in range(4):
        question = await create_question(
            client, admin, statement=f"Evento — enunciado {index} com texto suficiente."
        )
        await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": "A", "time_seconds": 30},
        )

    after = (await client.get("/api/v1/game/events", headers=student.auth_header)).json()

    assert after[0]["goals"][0]["current"] == 4
    assert after[0]["completed"] is True
    assert after[0]["reward_utility"]


# --------------------------------------------------------------------------- #
# Modo Guerra
# --------------------------------------------------------------------------- #
async def test_war_mode_starts_empty_and_explains_itself(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="war1@exemplo.com.br")

    body = (await client.get("/api/v1/game/war", headers=student.auth_header)).json()

    assert body["status"] is None
    assert "você escolhe os dias" in body["empty_reason"]


async def test_an_unrealistic_target_is_refused_by_the_rules(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="war2@exemplo.com.br")

    response = await client.post(
        "/api/v1/game/war",
        headers=student.auth_header,
        json={"days": 1, "daily_minutes": 10, "daily_questions": 0},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_war_plan"


async def test_war_mode_tracks_real_days_and_never_accuses(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="war3@exemplo.com.br")

    created = await client.post(
        "/api/v1/game/war",
        headers=student.auth_header,
        json={"days": 5, "daily_minutes": 120, "daily_questions": 0},
    )
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["status"] == "RUNNING"
    assert body["days"] == 5
    assert len(body["schedule"]) == 5
    assert body["days_met"] == 0
    assert body["days_missed"] == 0, "o primeiro dia ainda pode ser cumprido"

    texto = body["message"].lower()
    for proibido in ("falhou", "fracass", "você não conseguiu", "perdeu tudo"):
        assert proibido not in texto


async def test_only_one_war_mode_at_a_time(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="war4@exemplo.com.br")
    payload = {"days": 5, "daily_minutes": 120, "daily_questions": 0}

    first = await client.post("/api/v1/game/war", headers=student.auth_header, json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/game/war", headers=student.auth_header, json=payload)

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "campaign_already_running"


async def test_abandoning_war_mode_keeps_what_was_done(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="war5@exemplo.com.br")
    await client.post(
        "/api/v1/game/war",
        headers=student.auth_header,
        json={"days": 5, "daily_minutes": 120, "daily_questions": 0},
    )

    ended = await client.post("/api/v1/game/war/abandon", headers=student.auth_header)
    assert ended.status_code == 200
    assert ended.json()["status"] == "ABANDONED"
    assert ended.json()["succeeded"] is False

    history = (await client.get("/api/v1/game/war/history", headers=student.auth_header)).json()
    assert len(history) == 1

    # Encerrado, dá para declarar outro.
    again = await client.post(
        "/api/v1/game/war",
        headers=student.auth_header,
        json={"days": 5, "daily_minutes": 120, "daily_questions": 0},
    )
    assert again.status_code == 201


# --------------------------------------------------------------------------- #
# Card compartilhável
# --------------------------------------------------------------------------- #
async def test_the_card_omits_statistics_without_sample_and_says_why(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="card1@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.card1@exemplo.com.br")

    question = await create_question(
        client, admin, statement="Card — enunciado único com texto suficiente."
    )
    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": "A", "time_seconds": 30},
    )

    body = (
        await client.post(
            "/api/v1/game/cards/preview",
            headers=student.auth_header,
            json={"include": ["accuracy", "retention", "coverage"]},
        )
    ).json()

    assert body["stats"] == []
    assert len(body["omitted"]) == 3
    assert any("30 respostas" in item for item in body["omitted"])
    assert any("plano de estudo" in item for item in body["omitted"])


async def test_the_card_never_promises_approval(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="card2@exemplo.com.br")

    body = (
        await client.post(
            "/api/v1/game/cards/preview",
            headers=student.auth_header,
            json={"include": ["level", "rank", "streak"], "display_name": "Marina"},
        )
    ).json()

    texto = " ".join(
        [body["headline"], body["footer"], *(item["detail"] for item in body["stats"])]
    ).lower()
    for proibido in ("aprovado", "vai passar", "aprovação garantida", "sucesso garantido"):
        assert proibido not in texto
    assert "não resultado em prova" in body["footer"]


async def test_a_card_is_published_only_on_request_and_can_be_revoked(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="card3@exemplo.com.br")

    empty = (await client.get("/api/v1/game/cards", headers=student.auth_header)).json()
    assert empty == [], "nada é publicado por padrão"

    published = await client.post(
        "/api/v1/game/cards",
        headers=student.auth_header,
        json={"include": ["level", "rank"], "display_name": "Marina"},
    )
    assert published.status_code == 201, published.text
    card = published.json()
    assert card["token"]

    # O link é público: abre sem autenticação.
    public = await client.get(f"/api/v1/game/cards/public/{card['token']}")
    assert public.status_code == 200
    assert public.json()["display_name"] == "Marina"
    assert "token" not in public.json(), "o link não devolve o próprio segredo"

    revoked = await client.delete(
        f"/api/v1/game/cards/{card['public_id']}", headers=student.auth_header
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"]

    gone = await client.get(f"/api/v1/game/cards/public/{card['token']}")
    assert gone.status_code == 404


async def test_the_published_card_is_frozen_at_publication(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O link mostra os números do dia — não um retrato que muda sozinho."""
    admin = await create_admin(client, emails, email="card4@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.card4@exemplo.com.br")

    published = (
        await client.post(
            "/api/v1/game/cards",
            headers=student.auth_header,
            json={"include": ["questions"], "display_name": "Marina"},
        )
    ).json()
    assert published["stats"][0]["value"] == "0"

    for index in range(3):
        question = await create_question(
            client, admin, statement=f"Congelado — enunciado {index} com texto suficiente."
        )
        await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": "A", "time_seconds": 30},
        )

    public = (await client.get(f"/api/v1/game/cards/public/{published['token']}")).json()
    assert public["stats"][0]["value"] == "0", "o card publicado não muda sozinho"

    # Uma nova publicação, sim, traz os números atualizados.
    again = (
        await client.post(
            "/api/v1/game/cards",
            headers=student.auth_header,
            json={"include": ["questions"], "display_name": "Marina"},
        )
    ).json()
    assert again["stats"][0]["value"] == "3"
