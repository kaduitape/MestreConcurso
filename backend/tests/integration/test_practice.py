"""Resolver questões avulsas: correção, estatísticas e histórico."""

from __future__ import annotations

from httpx import AsyncClient

from app.models.question import MIN_STATS_SAMPLE
from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    create_admin,
    create_question,
    create_subject,
    create_user,
)

ENUNCIADO = "A prescrição da pretensão punitiva estatal, no direito penal brasileiro, é"


async def _scenario(
    client: AsyncClient, emails: CapturingDispatcher, *, student_email: str
) -> tuple[RegisteredUser, RegisteredUser, dict]:
    admin = await create_admin(client, emails, email=f"gestor.{student_email}")
    subject = await create_subject(client, admin)
    question = await create_question(
        client,
        admin,
        statement=ENUNCIADO,
        correct="B",
        subject_public_id=subject["public_id"],
        explanation="A prescrição extingue a punibilidade.",
    )
    student = await create_user(client, emails, email=student_email)
    return admin, student, question


async def test_correct_answer_returns_the_reasoning(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, question = await _scenario(client, emails, student_email="pratica1@exemplo.com.br")

    response = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": "b", "time_seconds": 45, "confidence": "HIGH"},
    )
    assert response.status_code == 200, response.text
    feedback = response.json()

    assert feedback["is_correct"] is True
    assert feedback["is_blank"] is False
    assert feedback["selected_letter"] == "B"
    assert feedback["correct_letter"] == "B"
    assert feedback["correct_feedback"] == "Comentário da alternativa B."
    assert feedback["explanation"] == "A prescrição extingue a punibilidade."
    assert feedback["time_seconds"] == 45


async def test_wrong_answer_explains_both_alternatives(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, question = await _scenario(client, emails, student_email="pratica2@exemplo.com.br")

    response = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": "D"},
    )
    feedback = response.json()

    assert feedback["is_correct"] is False
    assert feedback["correct_letter"] == "B"
    # A marcada e a certa vêm comentadas: o candidato entende o erro.
    assert feedback["selected_feedback"] == "Comentário da alternativa D."
    assert feedback["correct_feedback"] == "Comentário da alternativa B."


async def test_blank_answer_is_recorded_as_blank(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, question = await _scenario(client, emails, student_email="pratica3@exemplo.com.br")

    response = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": None},
    )
    feedback = response.json()
    assert feedback["is_blank"] is True
    assert feedback["is_correct"] is False
    assert feedback["selected_letter"] is None


async def test_letter_outside_the_question_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, question = await _scenario(client, emails, student_email="pratica4@exemplo.com.br")

    response = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": "Z"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_alternative"


async def test_accuracy_appears_only_with_a_minimum_sample(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, _, question = await _scenario(client, emails, student_email="pratica5@exemplo.com.br")

    # Uma amostra pequena não vira percentual: a interface mostra "dados insuficientes".
    for index in range(MIN_STATS_SAMPLE - 1):
        student = await create_user(client, emails, email=f"amostra{index}@exemplo.com.br")
        answer = await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": "B" if index % 2 == 0 else "A", "time_seconds": 60},
        )
        assert answer.status_code == 200, answer.text

    partial = (
        await client.get(
            f"/api/v1/admin/questions/{question['public_id']}", headers=admin.auth_header
        )
    ).json()
    assert partial["stats"]["attempts"] == MIN_STATS_SAMPLE - 1
    assert partial["stats"]["accuracy"] is None
    assert partial["stats"]["average_time_seconds"] == 60

    last = await create_user(client, emails, email="amostra.final@exemplo.com.br")
    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=last.auth_header,
        json={"letter": "B", "time_seconds": 60},
    )

    complete = (
        await client.get(
            f"/api/v1/admin/questions/{question['public_id']}", headers=admin.auth_header
        )
    ).json()
    assert complete["stats"]["attempts"] == MIN_STATS_SAMPLE
    # 10 acertos entre os 19 primeiros (índices pares) + o último.
    assert complete["stats"]["accuracy"] == 11 / MIN_STATS_SAMPLE


async def test_history_lists_the_answers_of_the_candidate_only(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, question = await _scenario(client, emails, student_email="pratica6@exemplo.com.br")
    other = await create_user(client, emails, email="outro.aluno@exemplo.com.br")

    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": "B", "time_seconds": 30},
    )
    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=other.auth_header,
        json={"letter": "A"},
    )

    response = await client.get("/api/v1/questions/history", headers=student.auth_header)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["question_public_id"] == question["public_id"]
    assert item["is_correct"] is True
    assert item["time_seconds"] == 30
