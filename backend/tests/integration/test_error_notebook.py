"""Caderno de Erros: causa declarada, sugestão de IA e radar de pegadinhas."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderCredentials
from app.domain.intelligence.errors import MIN_CAUSE_SAMPLE, MIN_TRAP_SAMPLE
from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    configure_ai,
    create_admin,
    create_question,
    create_subject,
    create_user,
)
from tests.fake_ai import FakeProvider

CAUSE_PAYLOAD = {
    "cause": "INTERPRETATION",
    "trap_slug": None,
    "confidence": 0.62,
    "rationale": "O comando pedia a alternativa incorreta.",
    "study_tip": "Sublinhe o comando antes de ler as alternativas.",
}


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=CAUSE_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _wrong_answer(
    client: AsyncClient,
    admin: RegisteredUser,
    student: RegisteredUser,
    *,
    statement: str,
    subject_public_id: str | None = None,
) -> str:
    """Erra uma questão de propósito e devolve o public_id da tentativa."""
    question = await create_question(
        client, admin, statement=statement, subject_public_id=subject_public_id
    )
    wrong = next(item["letter"] for item in question["alternatives"] if not item["is_correct"])
    answered = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": wrong},
    )
    assert answered.status_code == 200, answered.text

    history = await client.get("/api/v1/questions/history", headers=student.auth_header)
    return str(history.json()["items"][0]["public_id"])


async def _scenario(
    client: AsyncClient, emails: CapturingDispatcher, *, student_email: str
) -> tuple[RegisteredUser, RegisteredUser, dict]:
    admin = await create_admin(client, emails, email=f"gestor.{student_email}")
    subject = await create_subject(client, admin)
    student = await create_user(client, emails, email=student_email)
    return admin, student, subject


async def test_wrong_answers_appear_in_the_queue_to_be_classified(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro1@exemplo.com.br")
    await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão errada de propósito sobre direito penal",
        subject_public_id=subject["public_id"],
    )

    response = await client.get("/api/v1/errors/pending", headers=student.auth_header)
    assert response.status_code == 200, response.text
    pending = response.json()
    assert len(pending) == 1
    assert pending[0]["subject_name"] == "Direito Penal"
    assert pending[0]["selected_letter"]


async def test_declared_cause_counts_immediately_in_the_notebook(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro2@exemplo.com.br")
    attempt = await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão sobre prazos processuais que foi respondida com pressa",
        subject_public_id=subject["public_id"],
    )

    classified = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=student.auth_header,
        json={"cause": "RUSH", "note": "Li rápido demais."},
    )
    assert classified.status_code == 201, classified.text
    body = classified.json()
    assert body["cause"] == "RUSH"
    assert body["cause_label"] == "Pressa ou desatenção"
    assert body["source"] == "USER"
    # Declarada pela pessoa: já vale como confirmada.
    assert body["is_confirmed"] is True

    # E some da fila de pendentes.
    pending = await client.get("/api/v1/errors/pending", headers=student.auth_header)
    assert pending.json() == []

    notebook = await client.get("/api/v1/errors/notebook", headers=student.auth_header)
    assert notebook.json()["total"] == 1


async def test_correct_answer_cannot_be_classified_as_error(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro3@exemplo.com.br")
    question = await create_question(
        client,
        admin,
        statement="Questão respondida corretamente sobre direito penal",
        subject_public_id=subject["public_id"],
    )
    correct = next(item["letter"] for item in question["alternatives"] if item["is_correct"])
    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": correct},
    )
    history = await client.get("/api/v1/questions/history", headers=student.auth_header)
    attempt = history.json()["items"][0]["public_id"]

    response = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=student.auth_header,
        json={"cause": "RUSH"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "attempt_not_wrong"


async def test_trap_pattern_requires_the_trap_cause(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro4@exemplo.com.br")
    attempt = await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão com generalização indevida na alternativa marcada",
        subject_public_id=subject["public_id"],
    )

    response = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=student.auth_header,
        json={"cause": "FORGETTING", "trap_slug": "generalizacao-indevida"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "trap_requires_trap_cause"


async def test_ai_suggestion_waits_for_confirmation_before_counting(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro5@exemplo.com.br")
    await configure_ai(client, admin, features=("error.classify",))
    attempt = await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão cujo comando pedia a alternativa incorreta e confundiu",
        subject_public_id=subject["public_id"],
    )

    suggested = await client.post(
        f"/api/v1/errors/attempts/{attempt}/suggest-cause", headers=student.auth_header
    )
    assert suggested.status_code == 200, suggested.text
    suggestion = suggested.json()
    assert suggestion["cause"] == "INTERPRETATION"
    assert suggestion["cause_label"] == "Interpretei o enunciado errado"
    assert suggestion["confirmed"] is False
    assert suggestion["model"] == "gpt-4o-mini"
    assert suggestion["study_tip"]

    # Enquanto não for confirmada, não entra em estatística alguma.
    notebook = await client.get("/api/v1/errors/notebook", headers=student.auth_header)
    assert notebook.json()["total"] == 0

    listed = await client.get("/api/v1/errors?pending=true", headers=student.auth_header)
    pending_rows = listed.json()["items"]
    assert len(pending_rows) == 1
    assert pending_rows[0]["source"] == "AI"
    assert pending_rows[0]["is_confirmed"] is False
    assert pending_rows[0]["rationale"]

    confirmed = await client.post(
        f"/api/v1/errors/{pending_rows[0]['public_id']}/confirm", headers=student.auth_header
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["is_confirmed"] is True

    notebook = await client.get("/api/v1/errors/notebook", headers=student.auth_header)
    assert notebook.json()["total"] == 1


async def test_the_candidate_can_override_the_suggested_cause(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro6@exemplo.com.br")
    await configure_ai(client, admin, features=("error.classify",))
    attempt = await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão que a IA leu como interpretação e o candidato discorda",
        subject_public_id=subject["public_id"],
    )

    await client.post(
        f"/api/v1/errors/attempts/{attempt}/suggest-cause", headers=student.auth_header
    )
    corrected = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=student.auth_header,
        json={"cause": "UNKNOWN_CONTENT"},
    )
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["cause"] == "UNKNOWN_CONTENT"
    assert corrected.json()["source"] == "USER"

    notebook = await client.get("/api/v1/errors/notebook", headers=student.auth_header)
    by_cause = notebook.json()["by_cause"]
    assert [item["cause"] for item in by_cause] == ["UNKNOWN_CONTENT"]


async def test_notebook_points_the_dominant_cause_only_with_sample(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro7@exemplo.com.br")

    async def classify(index: int, cause: str) -> None:
        attempt = await _wrong_answer(
            client,
            admin,
            student,
            statement=f"Questão número {index} respondida com desatenção evidente",
            subject_public_id=subject["public_id"],
        )
        response = await client.post(
            f"/api/v1/errors/attempts/{attempt}",
            headers=student.auth_header,
            json={"cause": cause},
        )
        assert response.status_code == 201, response.text

    # Abaixo da amostra mínima o caderno não aponta causa predominante.
    for index in range(MIN_CAUSE_SAMPLE - 1):
        await classify(index, "RUSH")

    partial = (await client.get("/api/v1/errors/notebook", headers=student.auth_header)).json()
    # A leitura por disciplina já existe (3 erros bastam), mas a causa predominante
    # do caderno inteiro exige uma amostra maior — e a diferença é dita.
    assert all("dos seus" not in insight for insight in partial["insights"])
    assert any("predominante" in note for note in partial["notes"])

    await classify(99, "RUSH")
    full = (await client.get("/api/v1/errors/notebook", headers=student.auth_header)).json()
    assert full["total"] == MIN_CAUSE_SAMPLE
    assert full["by_cause"][0]["cause"] == "RUSH"
    assert full["insights"]
    # A recomendação vem da causa, com o número real do caderno.
    assert full["by_cause"][0]["action"] in full["insights"][0]
    assert str(MIN_CAUSE_SAMPLE) in full["insights"][0]


async def test_trap_radar_needs_repetition_to_point_a_pattern(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro8@exemplo.com.br")
    catalogue = await client.get("/api/v1/errors/traps", headers=student.auth_header)
    assert catalogue.status_code == 200
    slugs = {item["slug"] for item in catalogue.json()}
    assert "generalizacao-indevida" in slugs

    async def fall_into_trap(index: int) -> None:
        attempt = await _wrong_answer(
            client,
            admin,
            student,
            statement=f"Questão {index} com a palavra sempre numa regra que tem exceções",
            subject_public_id=subject["public_id"],
        )
        response = await client.post(
            f"/api/v1/errors/attempts/{attempt}",
            headers=student.auth_header,
            json={"cause": "TRAP", "trap_slug": "generalizacao-indevida"},
        )
        assert response.status_code == 201, response.text

    for index in range(MIN_TRAP_SAMPLE - 1):
        await fall_into_trap(index)

    partial = (await client.get("/api/v1/errors/notebook", headers=student.auth_header)).json()
    assert partial["traps"] == []
    assert any("radar" in note.lower() for note in partial["notes"])

    await fall_into_trap(99)
    full = (await client.get("/api/v1/errors/notebook", headers=student.auth_header)).json()
    assert full["traps"][0]["slug"] == "generalizacao-indevida"
    assert full["traps"][0]["count"] == MIN_TRAP_SAMPLE
    assert full["traps"][0]["name"] == "Generalização indevida"


async def test_resolved_error_stays_in_the_history(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro9@exemplo.com.br")
    attempt = await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão que o candidato revisou depois e considera superada",
        subject_public_id=subject["public_id"],
    )
    created = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=student.auth_header,
        json={"cause": "FORGETTING"},
    )
    public_id = created.json()["public_id"]

    resolved = await client.post(f"/api/v1/errors/{public_id}/resolve", headers=student.auth_header)
    assert resolved.status_code == 200
    assert resolved.json()["is_resolved"] is True

    notebook = (await client.get("/api/v1/errors/notebook", headers=student.auth_header)).json()
    assert notebook["total"] == 1
    assert notebook["resolved"] == 1


async def test_a_candidate_never_sees_the_errors_of_another(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin, student, subject = await _scenario(client, emails, student_email="erro10@exemplo.com.br")
    intruder = await create_user(client, emails, email="intruso.erro@exemplo.com.br")
    attempt = await _wrong_answer(
        client,
        admin,
        student,
        statement="Questão errada que pertence somente a quem a respondeu",
        subject_public_id=subject["public_id"],
    )
    created = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=student.auth_header,
        json={"cause": "RUSH"},
    )

    stolen = await client.post(
        f"/api/v1/errors/{created.json()['public_id']}/confirm", headers=intruder.auth_header
    )
    assert stolen.status_code == 404

    listed = await client.get("/api/v1/errors", headers=intruder.auth_header)
    assert listed.json()["total"] == 0
