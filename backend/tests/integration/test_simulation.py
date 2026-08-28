"""Simulados: montagem por tipo, execução com pausa e correção completa."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    create_admin,
    create_question,
    create_subject,
    create_user,
)

MIN_QUESTIONS = 5


async def _bank(
    client: AsyncClient,
    emails: CapturingDispatcher,
    *,
    admin_email: str,
    total: int = 6,
) -> tuple[RegisteredUser, dict, list[dict]]:
    admin = await create_admin(client, emails, email=admin_email)
    subject = await create_subject(client, admin)
    questions = [
        await create_question(
            client,
            admin,
            statement=f"Questão {index} sobre a teoria geral do crime no direito penal",
            correct="A" if index % 2 == 0 else "B",
            subject_public_id=subject["public_id"],
        )
        for index in range(total)
    ]
    return admin, subject, questions


async def test_custom_simulation_runs_from_start_to_correction(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, subject, questions = await _bank(client, emails, admin_email="sim1@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.sim1@exemplo.com.br")

    created = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={
            "kind": "CUSTOM",
            "questions_count": MIN_QUESTIONS,
            "subject_public_id": subject["public_id"],
            "duration_minutes": 30,
        },
    )
    assert created.status_code == 201, created.text
    simulation = created.json()
    assert simulation["questions_count"] == MIN_QUESTIONS
    assert simulation["name"] == "Simulado personalizado"
    # A regra de montagem fica registrada — nada de caixa preta.
    assert simulation["config"]["rule"]

    started = await client.post(
        f"/api/v1/simulations/{simulation['public_id']}/start", headers=student.auth_header
    )
    assert started.status_code == 201, started.text
    run = started.json()
    attempt_id = run["attempt"]["public_id"]
    assert len(run["questions"]) == MIN_QUESTIONS
    assert run["remaining_seconds"] == 30 * 60
    # Durante a execução o gabarito não trafega.
    assert "is_correct" not in run["questions"][0]["question"]["alternatives"][0]

    order = [item["question"]["public_id"] for item in run["questions"]]
    gabarito = {item["public_id"]: item for item in questions}

    # Primeira: marca errado e depois corrige — o autosave substitui a resposta.
    correta = next(
        alternative["letter"]
        for alternative in gabarito[order[0]]["alternatives"]
        if alternative["is_correct"]
    )
    errada = next(
        alternative["letter"]
        for alternative in gabarito[order[0]]["alternatives"]
        if not alternative["is_correct"]
    )
    for letter in (errada, correta):
        saved = await client.post(
            f"/api/v1/simulations/attempts/{attempt_id}/answer",
            headers=student.auth_header,
            json={
                "question_public_id": order[0],
                "letter": letter,
                "time_seconds": 40,
            },
        )
        assert saved.status_code == 200, saved.text

    # Mais duas certas, uma errada e uma em branco.
    for index in (1, 2):
        letter = next(
            alternative["letter"]
            for alternative in gabarito[order[index]]["alternatives"]
            if alternative["is_correct"]
        )
        await client.post(
            f"/api/v1/simulations/attempts/{attempt_id}/answer",
            headers=student.auth_header,
            json={"question_public_id": order[index], "letter": letter, "time_seconds": 30},
        )
    letter_errada = next(
        alternative["letter"]
        for alternative in gabarito[order[3]]["alternatives"]
        if not alternative["is_correct"]
    )
    await client.post(
        f"/api/v1/simulations/attempts/{attempt_id}/answer",
        headers=student.auth_header,
        json={"question_public_id": order[3], "letter": letter_errada, "time_seconds": 20},
    )

    # Retomar de onde parou devolve as marcações já salvas.
    resumed = await client.get(
        f"/api/v1/simulations/attempts/{attempt_id}", headers=student.auth_header
    )
    assert resumed.status_code == 200, resumed.text
    marked = {
        item["question"]["public_id"]: item["selected_letter"]
        for item in resumed.json()["questions"]
    }
    assert marked[order[0]] == correta  # a resposta anterior foi substituída
    assert marked[order[4]] is None

    finished = await client.post(
        f"/api/v1/simulations/attempts/{attempt_id}/finish", headers=student.auth_header
    )
    assert finished.status_code == 200, finished.text
    attempt = finished.json()

    assert attempt["status"] == "FINISHED"
    assert attempt["correct_count"] == 3
    assert attempt["wrong_count"] == 1
    assert attempt["blank_count"] == 1
    assert attempt["score"] == 60.0

    analysis = attempt["analysis"]
    assert analysis["total"] == MIN_QUESTIONS
    assert analysis["accuracy"] == 0.6
    assert analysis["previous_accuracy"] is None  # primeiro simulado: nada a comparar
    assert [item["subject_name"] for item in analysis["by_subject"]] == ["Direito Penal"]
    assert analysis["by_subject"][0]["correct"] == 3
    assert {item["difficulty"] for item in analysis["by_difficulty"]} == {"MEDIUM"}
    assert analysis["recommendations"]


async def test_errors_simulation_without_errors_says_why(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    await _bank(client, emails, admin_email="sim2@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.sim2@exemplo.com.br")

    response = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "ERRORS", "questions_count": MIN_QUESTIONS},
    )
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["code"] == "no_questions_available"
    assert "questões erradas" in error["message"]


async def test_errors_simulation_uses_the_questions_the_candidate_missed(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, _, questions = await _bank(client, emails, admin_email="sim3@exemplo.com.br", total=8)
    student = await create_user(client, emails, email="aluno.sim3@exemplo.com.br")

    erradas = []
    for question in questions[:5]:
        letter = next(
            alternative["letter"]
            for alternative in question["alternatives"]
            if not alternative["is_correct"]
        )
        await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": letter},
        )
        erradas.append(question["public_id"])

    # Uma acertada não deve entrar no simulado dos erros.
    acertada = questions[5]
    letter = next(
        alternative["letter"]
        for alternative in acertada["alternatives"]
        if alternative["is_correct"]
    )
    await client.post(
        f"/api/v1/questions/{acertada['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": letter},
    )

    created = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "ERRORS", "questions_count": 10},
    )
    assert created.status_code == 201, created.text
    simulation = created.json()
    assert simulation["questions_count"] == 5

    started = await client.post(
        f"/api/v1/simulations/{simulation['public_id']}/start", headers=student.auth_header
    )
    incluidas = {item["question"]["public_id"] for item in started.json()["questions"]}
    assert incluidas == set(erradas)
    assert acertada["public_id"] not in incluidas


async def test_official_simulation_needs_an_active_plan(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    await _bank(client, emails, admin_email="sim4@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.sim4@exemplo.com.br")

    response = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "OFFICIAL", "questions_count": MIN_QUESTIONS},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "no_questions_available"
    assert "plano" in response.json()["error"]["message"]


async def test_pause_freezes_the_clock_and_only_one_run_at_a_time(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, subject, _ = await _bank(client, emails, admin_email="sim5@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.sim5@exemplo.com.br")

    async def build() -> str:
        response = await client.post(
            "/api/v1/simulations",
            headers=student.auth_header,
            json={
                "kind": "CUSTOM",
                "questions_count": MIN_QUESTIONS,
                "subject_public_id": subject["public_id"],
            },
        )
        assert response.status_code == 201, response.text
        return str(response.json()["public_id"])

    first = await build()
    second = await build()

    started = await client.post(f"/api/v1/simulations/{first}/start", headers=student.auth_header)
    attempt_id = started.json()["attempt"]["public_id"]

    # Enquanto houver execução aberta, começar outra é bloqueado com o motivo.
    blocked = await client.post(f"/api/v1/simulations/{second}/start", headers=student.auth_header)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "simulation_already_running"

    paused = await client.post(
        f"/api/v1/simulations/attempts/{attempt_id}/pause", headers=student.auth_header
    )
    assert paused.status_code == 200, paused.text
    assert paused.json()["status"] == "PAUSED"

    # Pausar duas vezes seguidas não faz sentido e é recusado.
    again = await client.post(
        f"/api/v1/simulations/attempts/{attempt_id}/pause", headers=student.auth_header
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "not_in_progress"

    resumed = await client.post(
        f"/api/v1/simulations/attempts/{attempt_id}/resume", headers=student.auth_header
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "IN_PROGRESS"

    # Em andamento, o simulado aparece como o atual do candidato.
    current = await client.get("/api/v1/simulations/current", headers=student.auth_header)
    assert current.status_code == 200
    assert current.json()["attempt"]["public_id"] == attempt_id


async def test_second_run_compares_with_the_previous_accuracy(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, subject, questions = await _bank(client, emails, admin_email="sim6@exemplo.com.br", total=10)
    student = await create_user(client, emails, email="aluno.sim6@exemplo.com.br")
    gabarito = {item["public_id"]: item for item in questions}

    async def run(*, hits: int) -> dict:
        created = await client.post(
            "/api/v1/simulations",
            headers=student.auth_header,
            json={
                "kind": "CUSTOM",
                "questions_count": MIN_QUESTIONS,
                "subject_public_id": subject["public_id"],
            },
        )
        simulation = created.json()
        started = await client.post(
            f"/api/v1/simulations/{simulation['public_id']}/start", headers=student.auth_header
        )
        run_body = started.json()
        attempt_id = run_body["attempt"]["public_id"]
        for position, item in enumerate(run_body["questions"]):
            public_id = item["question"]["public_id"]
            wanted = position < hits
            letter = next(
                alternative["letter"]
                for alternative in gabarito[public_id]["alternatives"]
                if alternative["is_correct"] is wanted
            )
            await client.post(
                f"/api/v1/simulations/attempts/{attempt_id}/answer",
                headers=student.auth_header,
                json={"question_public_id": public_id, "letter": letter, "time_seconds": 25},
            )
        finished = await client.post(
            f"/api/v1/simulations/attempts/{attempt_id}/finish", headers=student.auth_header
        )
        assert finished.status_code == 200, finished.text
        return dict(finished.json())

    first = await run(hits=2)
    assert first["analysis"]["previous_accuracy"] is None

    second = await run(hits=4)
    analysis = second["analysis"]
    assert analysis["accuracy"] == 0.8
    assert analysis["previous_accuracy"] == 0.4
    # A evolução é calculada em Python a partir dos números registrados.
    assert round(analysis["accuracy_delta"], 4) == 0.4

    history = await client.get("/api/v1/simulations/history", headers=student.auth_header)
    assert history.status_code == 200
    assert len(history.json()) == 2


async def test_a_candidate_cannot_open_the_run_of_another(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, subject, _ = await _bank(client, emails, admin_email="sim7@exemplo.com.br")
    owner = await create_user(client, emails, email="dono.sim7@exemplo.com.br")
    intruder = await create_user(client, emails, email="intruso.sim7@exemplo.com.br")

    created = await client.post(
        "/api/v1/simulations",
        headers=owner.auth_header,
        json={
            "kind": "CUSTOM",
            "questions_count": MIN_QUESTIONS,
            "subject_public_id": subject["public_id"],
        },
    )
    started = await client.post(
        f"/api/v1/simulations/{created.json()['public_id']}/start", headers=owner.auth_header
    )
    attempt_id = started.json()["attempt"]["public_id"]

    response = await client.get(
        f"/api/v1/simulations/attempts/{attempt_id}", headers=intruder.auth_header
    )
    assert response.status_code == 404
