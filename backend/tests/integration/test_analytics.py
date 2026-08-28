"""Fase 9: Mestre Score, projeção, caminho e painéis.

O critério de aceite da fase é curto e exigente: **cada gráfico tem uma decisão
associada e os intervalos estão sempre visíveis**. Os testes cobram isso ponta a
ponta, junto com a regra que separa o Mestre Score do XP.
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


async def _answer_batch(
    client: AsyncClient,
    admin: RegisteredUser,
    student: RegisteredUser,
    *,
    prefix: str,
    total: int,
    correct: int,
    subject_public_id: str | None = None,
) -> None:
    for index in range(total):
        extra: dict[str, Any] = {}
        if subject_public_id:
            extra["subject_public_id"] = subject_public_id
        question = await create_question(
            client, admin, statement=f"{prefix} — enunciado {index} com texto suficiente.", **extra
        )
        letter = next(
            item["letter"]
            for item in question["alternatives"]
            if item["is_correct"] is (index < correct)
        )
        response = await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": letter, "time_seconds": 30},
        )
        assert response.status_code == 200, response.text


async def _subject_id(client: AsyncClient, admin: RegisteredUser, name: str) -> str:
    subjects = (
        await client.get("/api/v1/catalog/subjects?page_size=50", headers=admin.auth_header)
    ).json()
    return next(item["public_id"] for item in subjects["items"] if item["name"] == name)


# --------------------------------------------------------------------------- #
# Mestre Score
# --------------------------------------------------------------------------- #
async def test_a_new_candidate_gets_no_invented_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="an1@exemplo.com.br")

    body = (await client.get("/api/v1/analytics/master-score", headers=student.auth_header)).json()

    assert body["value"] == 0
    assert body["confidence"] == "NONE"
    assert body["empty_reason"]
    assert len(body["missing_signals"]) == 5
    for component in body["components"]:
        assert component["available"] is False
        assert component["detail"], "cada sinal diz quanto falta"


async def test_the_score_components_sum_exactly_to_the_displayed_value(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an2@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.an2@exemplo.com.br")

    await _answer_batch(client, admin, student, prefix="Score", total=40, correct=28)

    body = (await client.get("/api/v1/analytics/master-score", headers=student.auth_header)).json()

    assert body["value"] > 0
    assert sum(item["points"] for item in body["components"]) == body["value"]


async def test_the_score_always_carries_its_interval(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an3@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.an3@exemplo.com.br")

    await _answer_batch(client, admin, student, prefix="Faixa", total=32, correct=24)

    body = (await client.get("/api/v1/analytics/master-score", headers=student.auth_header)).json()

    assert body["low"] < body["value"] < body["high"]
    assert "Wilson" in body["interval_note"]
    assert "não é probabilidade de aprovação" in body["interval_note"]

    incluidos = [item for item in body["components"] if item["available"]]
    assert incluidos
    for component in incluidos:
        assert component["low"] <= component["value"] <= component["high"]
        assert component["sample"] > 0


async def test_xp_does_not_move_the_master_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Duas leituras com o mesmo desempenho e XP diferente devem coincidir."""
    admin = await create_admin(client, emails, email="an4@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.an4@exemplo.com.br")

    await _answer_batch(client, admin, student, prefix="XP", total=40, correct=30)
    antes = (await client.get("/api/v1/analytics/master-score", headers=student.auth_header)).json()

    # Ganhar XP por outra via (missões, sequência) não pode mexer no score.
    perfil = (await client.get("/api/v1/game/profile", headers=student.auth_header)).json()
    assert perfil["level"]["xp_total"] > 0

    depois = (
        await client.get("/api/v1/analytics/master-score", headers=student.auth_header)
    ).json()

    assert depois["value"] == antes["value"]
    assert perfil["master_score"] == antes["value"]
    assert perfil["master_score_low"] == antes["low"]
    assert "XP não entra" in perfil["master_score_note"]


async def test_the_score_history_needs_two_measurements(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="an5@exemplo.com.br")

    body = (
        await client.get("/api/v1/analytics/master-score/history", headers=student.auth_header)
    ).json()

    assert len(body["points"]) == 1
    assert body["delta"] is None
    assert "não é tendência" in body["empty_reason"]
    assert body["points"][0]["low"] <= body["points"][0]["value"] <= body["points"][0]["high"]


# --------------------------------------------------------------------------- #
# Se a prova fosse hoje
# --------------------------------------------------------------------------- #
async def test_without_the_official_distribution_there_is_no_projection(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="an6@exemplo.com.br")

    body = (await client.get("/api/v1/analytics/projection", headers=student.auth_header)).json()

    assert body["expected"] is None
    assert body["is_reliable"] is False
    assert "distribuição de questões" in body["empty_reason"]


async def test_the_projection_never_estimates_approval(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an7@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.an7@exemplo.com.br")
    await _plan(client, student, position)

    body = (await client.get("/api/v1/analytics/projection", headers=student.auth_header)).json()

    # O aviso nega a previsão; o resto da tela não pode afirmá-la em lugar nenhum.
    assert "não estima chance de aprovação" in body["disclaimer"]
    texto = " ".join(item["detail"] for item in body["subjects"]).lower()
    for proibido in ("você será aprovado", "chance de aprovação", "vai passar"):
        assert proibido not in texto


async def test_low_coverage_refuses_to_state_a_total(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an8@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.an8@exemplo.com.br")
    await _plan(client, student, position)

    # Só uma das três disciplinas ganha amostra.
    subject = await _subject_id(client, admin, "Informática")
    await _answer_batch(
        client,
        admin,
        student,
        prefix="Cobertura baixa",
        total=25,
        correct=20,
        subject_public_id=subject,
    )

    body = (await client.get("/api/v1/analytics/projection", headers=student.auth_header)).json()

    assert body["expected"] is None, "cobertura baixa não afirma total"
    assert body["is_reliable"] is False
    assert body["coverage"] < 0.5
    assert "50%" in body["empty_reason"]
    assert body["subjects"], "as disciplinas continuam listadas com o que falta"


async def test_the_projection_states_its_coverage_and_its_range(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an9@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.an9@exemplo.com.br")
    await _plan(client, student, position)

    for name, correct in (("Direito Penal", 20), ("Português", 14)):
        subject = await _subject_id(client, admin, name)
        await _answer_batch(
            client,
            admin,
            student,
            prefix=f"Projeção {name}",
            total=25,
            correct=correct,
            subject_public_id=subject,
        )

    body = (await client.get("/api/v1/analytics/projection", headers=student.auth_header)).json()

    assert body["is_reliable"] is True
    assert body["expected_low"] < body["expected"] < body["expected_high"]
    assert body["covered_questions"] == 40
    assert body["total_questions"] == 48
    assert body["coverage"] > 0.8

    incluidas = [item for item in body["subjects"] if item["included"]]
    assert len(incluidas) == 2
    for item in incluidas:
        assert item["expected_low"] <= item["expected"] <= item["expected_high"]

    fora = next(item for item in body["subjects"] if not item["included"])
    assert fora["expected"] is None
    assert "20 respostas" in fora["detail"]


# --------------------------------------------------------------------------- #
# Caminho da aprovação
# --------------------------------------------------------------------------- #
async def test_every_step_carries_the_number_that_produced_it(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an10@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.an10@exemplo.com.br")
    await _plan(client, student, position)

    subject = await _subject_id(client, admin, "Direito Penal")
    await _answer_batch(
        client,
        admin,
        student,
        prefix="Caminho",
        total=25,
        correct=10,
        subject_public_id=subject,
    )

    body = (await client.get("/api/v1/analytics/path", headers=student.auth_header)).json()

    assert body["steps"]
    for step in body["steps"]:
        assert step["action"]
        assert step["evidence"], "recomendação sem número é palpite"
    assert "não é garantia" in body["disclaimer"]

    # A disciplina medida e fraca vem antes das que ainda nem foram medidas.
    assert body["steps"][0]["subject_name"] == "Direito Penal"
    assert body["steps"][0]["kind"] == "IMPROVE"
    assert body["steps"][0]["questions_at_stake"] > 0

    medir = [item for item in body["steps"] if item["kind"] == "MEASURE"]
    assert medir
    assert all(item["questions_at_stake"] == 0 for item in medir)


# --------------------------------------------------------------------------- #
# Painéis
# --------------------------------------------------------------------------- #
async def test_every_chart_declares_the_decision_it_serves(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """É o critério de aceite da fase, cobrado mesmo com a conta vazia."""
    student = await create_user(client, emails, email="an11@exemplo.com.br")

    body = (await client.get("/api/v1/analytics/dashboard", headers=student.auth_header)).json()

    assert {item["key"] for item in body["charts"]} == {
        "acerto",
        "retencao",
        "cobertura",
        "consistencia",
    }
    for chart in body["charts"]:
        assert chart["decision"], f"{chart['key']} não declara para que serve"
        assert chart["title"] and chart["unit"]
        if not chart["points"]:
            assert chart["empty_reason"], "gráfico vazio explica a ausência"


async def test_proportion_charts_carry_interval_and_sample(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an12@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.an12@exemplo.com.br")

    await _answer_batch(client, admin, student, prefix="Painel", total=12, correct=8)

    body = (await client.get("/api/v1/analytics/dashboard", headers=student.auth_header)).json()
    acerto = next(item for item in body["charts"] if item["key"] == "acerto")

    # Uma semana só ainda não é evolução.
    assert acerto["points"] == []
    assert acerto["empty_reason"]
    assert acerto["decision"]


async def test_the_overview_answers_the_whole_screen_at_once(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="an13@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.an13@exemplo.com.br")
    await _plan(client, student, position)
    await _answer_batch(client, admin, student, prefix="Visão", total=32, correct=22)

    body = (await client.get("/api/v1/analytics/overview", headers=student.auth_header)).json()

    assert body["master_score"]["value"] > 0
    assert body["master_score"]["low"] < body["master_score"]["high"]
    assert body["projection"]["disclaimer"]
    assert body["path"]["disclaimer"]
    assert len(body["charts"]) == 4
    for chart in body["charts"]:
        assert chart["decision"]
