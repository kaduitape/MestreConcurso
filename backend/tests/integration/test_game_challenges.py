"""Fase 3: rodadas de desafio.

O ponto que os testes protegem: um desafio é um recorte de **questões reais**.
Se o banco não tem questões suficientes, a rodada não acontece — repetir
enunciado para completar o número seria fabricar desafio, e o placar resultante
não significaria nada.
"""

from __future__ import annotations

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


async def _stock(client: AsyncClient, admin: RegisteredUser, *, total: int, prefix: str) -> None:
    for index in range(total):
        await create_question(
            client, admin, statement=f"{prefix} — enunciado {index} com texto suficiente."
        )


async def _answer(
    client: AsyncClient,
    student: RegisteredUser,
    run: dict[str, Any],
    *,
    correct: bool,
    seconds: int = 20,
) -> dict[str, Any]:
    question = run["question"]
    assert question is not None, "a rodada precisa oferecer a questão da vez"
    letters = [item["letter"] for item in question["alternatives"]]
    # A visão do candidato não traz gabarito; acertamos pela alternativa "A",
    # que as fábricas de teste marcam como correta.
    letter = "A" if correct else next(item for item in letters if item != "A")
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
    body = response.json()
    assert body["is_correct"] is correct
    return body["run"]


async def test_modes_declare_their_own_victory_rule(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="run1@exemplo.com.br")

    body = (await client.get("/api/v1/game/challenges/modes", headers=student.auth_header)).json()

    assert {item["mode"] for item in body} == {"BOSS", "SURVIVAL", "COMBO", "TIME_ATTACK"}
    for mode in body:
        assert mode["rule"], "todo modo diz por escrito como se vence"
        assert mode["questions"] > 0

    survival = next(item for item in body if item["mode"] == "SURVIVAL")
    assert survival["lives"] == 3
    relogio = next(item for item in body if item["mode"] == "TIME_ATTACK")
    assert relogio["time_limit_seconds"] == 600


async def test_without_enough_questions_the_run_is_refused_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run2@exemplo.com.br")
    await _stock(client, admin, total=5, prefix="Banco curto")
    student = await create_user(client, emails, email="aluno.run2@exemplo.com.br")

    response = await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_enough_questions"
    assert "5 questão" in response.json()["error"]["message"]


async def test_boss_battle_requires_a_computed_priority_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O boss é a disciplina mais frágil de verdade — não um sorteio."""
    admin = await create_admin(client, emails, email="run3@exemplo.com.br")
    await _stock(client, admin, total=20, prefix="Boss")
    student = await create_user(client, emails, email="aluno.run3@exemplo.com.br")

    response = await client.post("/api/v1/game/challenges/BOSS", headers=student.auth_header)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_priority_score"
    assert "Priority Score" in response.json()["error"]["message"]


async def test_boss_battle_targets_the_weakest_subject_and_says_so(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run4@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.run4@exemplo.com.br")

    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    priorities = (
        await client.post("/api/v1/intelligence/priority/recompute", headers=student.auth_header)
    ).json()
    alvo = priorities["items"][0]

    # O banco precisa ter questões da disciplina que o Priority Score apontou.
    subjects = (
        await client.get("/api/v1/catalog/subjects?page_size=50", headers=admin.auth_header)
    ).json()
    subject = next(item for item in subjects["items"] if item["name"] == alvo["label"])
    for index in range(15):
        await create_question(
            client,
            admin,
            statement=f"Boss alvo — enunciado {index} com texto suficiente.",
            subject_public_id=subject["public_id"],
        )

    response = await client.post("/api/v1/game/challenges/BOSS", headers=student.auth_header)
    assert response.status_code == 201, response.text
    run = response.json()

    assert run["mode"] == "BOSS"
    assert run["selection"]["rule"] == "disciplina de maior Priority Score"
    assert run["selection"]["subject"] == alvo["label"]
    assert run["subject_label"] == alvo["label"]
    assert "priority_score" in run["selection"]
    assert run["state"]["questions_left"] == 15


async def test_only_one_run_at_a_time(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="run5@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Uma por vez")
    student = await create_user(client, emails, email="aluno.run5@exemplo.com.br")

    first = await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)
    assert first.status_code == 201
    second = await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "run_already_running"


async def test_the_run_state_is_derived_from_the_answers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run6@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Estado")
    student = await create_user(client, emails, email="aluno.run6@exemplo.com.br")

    run = (await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)).json()

    for _ in range(4):
        run = await _answer(client, student, run, correct=True)

    assert run["state"]["answered"] == 4
    assert run["state"]["correct"] == 4
    assert run["state"]["combo"] == 4
    assert run["state"]["multiplier"] == 1.3
    assert run["state"]["accuracy"] == 1.0

    run = await _answer(client, student, run, correct=False)
    assert run["state"]["combo"] == 0, "um erro zera a sequência"
    assert run["state"]["best_combo"] == 4, "mas o recorde da rodada fica"


async def test_a_fast_answer_does_not_build_the_combo(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run7@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Rápido demais")
    student = await create_user(client, emails, email="aluno.run7@exemplo.com.br")

    run = (await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)).json()
    for _ in range(3):
        run = await _answer(client, student, run, correct=True, seconds=1)

    assert run["state"]["correct"] == 3, "a resposta aconteceu e foi registrada"
    assert run["state"]["combo"] == 0, "mas não conta como sequência"
    assert run["state"]["multiplier"] == 1.0


async def test_survival_ends_at_the_third_mistake_and_scores_what_was_survived(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run8@exemplo.com.br")
    await _stock(client, admin, total=45, prefix="Sobrevivência")
    student = await create_user(client, emails, email="aluno.run8@exemplo.com.br")

    run = (
        await client.post("/api/v1/game/challenges/SURVIVAL", headers=student.auth_header)
    ).json()
    assert run["state"]["lives_left"] == 3

    for _ in range(2):
        run = await _answer(client, student, run, correct=True)
    for _ in range(3):
        run = await _answer(client, student, run, correct=False)

    assert run["status"] == "FINISHED"
    assert run["state"]["lives_left"] == 0
    assert run["state"]["is_over"] is True
    assert "erros" in run["state"]["over_reason"]
    assert run["score"]["score"] == 2
    assert run["score"]["achieved"] is False
    assert run["question"] is None, "rodada encerrada não oferece próxima questão"


async def test_answering_a_finished_run_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run9@exemplo.com.br")
    await _stock(client, admin, total=45, prefix="Encerrada")
    student = await create_user(client, emails, email="aluno.run9@exemplo.com.br")

    run = (
        await client.post("/api/v1/game/challenges/SURVIVAL", headers=student.auth_header)
    ).json()
    question = run["question"]
    for _ in range(3):
        run = await _answer(client, student, run, correct=False)

    late = await client.post(
        f"/api/v1/game/challenges/runs/{run['public_id']}/answer",
        headers=student.auth_header,
        json={"question_public_id": question["public_id"], "letter": "A", "time_seconds": 10},
    )

    assert late.status_code == 409
    assert late.json()["error"]["code"] == "run_not_running"


async def test_the_xp_of_a_run_is_an_open_account(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run10@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Conta aberta")
    student = await create_user(client, emails, email="aluno.run10@exemplo.com.br")

    run = (await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)).json()
    for _ in range(5):
        run = await _answer(client, student, run, correct=True)

    finished = await client.post(
        f"/api/v1/game/challenges/runs/{run['public_id']}/finish", headers=student.auth_header
    )
    assert finished.status_code == 200, finished.text
    body = finished.json()

    assert body["status"] == "FINISHED"
    rotulos = [line["label"] for line in body["score"]["breakdown"]]
    assert "XP base do modo" in rotulos
    assert "XP da rodada" in rotulos
    assert body["xp_awarded"] == body["score"]["xp"]

    # E o ganho aparece no extrato, com o motivo.
    extrato = (
        await client.get("/api/v1/game/xp/history?page=1&page_size=50", headers=student.auth_header)
    ).json()
    linha = next(item for item in extrato["items"] if item["event_kind"] == "CHALLENGE_FINISHED")
    assert linha["amount"] == body["score"]["xp"]
    assert "Combo" in linha["reason"]


async def test_an_abandoned_run_does_not_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Parar no meio não é desempenho — e não vira XP."""
    admin = await create_admin(client, emails, email="run11@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Abandonada")
    student = await create_user(client, emails, email="aluno.run11@exemplo.com.br")

    run = (await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)).json()
    run = await _answer(client, student, run, correct=True)

    abandoned = await client.post(
        f"/api/v1/game/challenges/runs/{run['public_id']}/finish?abandon=true",
        headers=student.auth_header,
    )

    assert abandoned.status_code == 200
    assert abandoned.json()["status"] == "ABANDONED"
    assert abandoned.json()["xp_awarded"] == 0

    extrato = (
        await client.get("/api/v1/game/xp/history?page=1&page_size=50", headers=student.auth_header)
    ).json()
    assert all(item["event_kind"] != "CHALLENGE_FINISHED" for item in extrato["items"])


async def test_run_answers_count_in_the_real_statistics(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Resposta de desafio é resposta de verdade: entra nas estatísticas."""
    admin = await create_admin(client, emails, email="run12@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Estatística")
    student = await create_user(client, emails, email="aluno.run12@exemplo.com.br")

    run = (await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)).json()
    for _ in range(3):
        run = await _answer(client, student, run, correct=True)

    profile = (await client.get("/api/v1/game/profile", headers=student.auth_header)).json()
    assert profile["metrics"]["questions_answered"] == 3


async def test_the_history_keeps_the_closed_rounds(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="run13@exemplo.com.br")
    await _stock(client, admin, total=30, prefix="Histórico")
    student = await create_user(client, emails, email="aluno.run13@exemplo.com.br")

    run = (await client.post("/api/v1/game/challenges/COMBO", headers=student.auth_header)).json()
    run = await _answer(client, student, run, correct=True)
    await client.post(
        f"/api/v1/game/challenges/runs/{run['public_id']}/finish", headers=student.auth_header
    )

    # Encerrada a rodada, não há mais nenhuma em andamento.
    current = (
        await client.get("/api/v1/game/challenges/current", headers=student.auth_header)
    ).json()
    assert current is None

    history = (
        await client.get("/api/v1/game/challenges/history", headers=student.auth_header)
    ).json()
    assert len(history) == 1
    assert history[0]["mode_name"] == "Combo"
    assert history[0]["summary"]["answered"] == 1
