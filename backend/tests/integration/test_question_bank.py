"""Banco de questões: cadastro, importação e classificação assistida por IA."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderCredentials
from tests.conftest import CapturingDispatcher
from tests.factories import (
    configure_ai,
    create_admin,
    create_question,
    create_subject,
    create_user,
    question_payload,
)
from tests.fake_ai import CLASSIFY_PAYLOAD, FakeProvider

ENUNCIADO = "Segundo o Código Penal, o homicídio praticado por motivo fútil é classificado como"


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=CLASSIFY_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def test_question_is_created_with_alternatives_and_answer_key(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="banco1@exemplo.com.br")
    subject = await create_subject(client, admin)

    created = await create_question(
        client,
        admin,
        statement=ENUNCIADO,
        correct="C",
        subject_public_id=subject["public_id"],
    )

    assert created["subject_name"] == "Direito Penal"
    assert len(created["alternatives"]) == 4
    correct = [item for item in created["alternatives"] if item["is_correct"]]
    assert [item["letter"] for item in correct] == ["C"]
    # Questão nova ainda não tem amostra: percentual não é inventado.
    assert created["stats"] == {"attempts": 0, "accuracy": None, "average_time_seconds": None}


async def test_question_without_exactly_one_answer_key_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="banco2@exemplo.com.br")

    payload = question_payload(statement=ENUNCIADO)
    for alternative in payload["alternatives"]:
        alternative["is_correct"] = False

    response = await client.post("/api/v1/admin/questions", headers=admin.auth_header, json=payload)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_correct_alternative"


async def test_duplicate_statement_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="banco3@exemplo.com.br")
    await create_question(client, admin, statement=ENUNCIADO)

    # Mesmo enunciado com espaçamento e caixa diferentes: continua sendo a mesma questão.
    duplicated = question_payload(statement=f"  {ENUNCIADO.upper()}  ")
    response = await client.post(
        "/api/v1/admin/questions", headers=admin.auth_header, json=duplicated
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "duplicate_question"


async def test_import_reports_created_duplicates_and_errors(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="banco4@exemplo.com.br")
    subject = await create_subject(client, admin)

    lote = [question_payload(statement=f"{ENUNCIADO} — item {index}") for index in range(1, 4)]
    lote.append(question_payload(statement=f"{ENUNCIADO} — item 1"))  # duplicada
    sem_gabarito = question_payload(statement=f"{ENUNCIADO} — item 9")
    for alternative in sem_gabarito["alternatives"]:
        alternative["is_correct"] = False
    lote.append(sem_gabarito)

    response = await client.post(
        "/api/v1/admin/questions/import",
        headers=admin.auth_header,
        json={"questions": lote, "subject_public_id": subject["public_id"]},
    )
    assert response.status_code == 200, response.text
    summary = response.json()

    assert summary["created"] == 3
    assert summary["skipped_duplicates"] == 1
    assert len(summary["errors"]) == 1
    # O erro diz qual questão falhou e por quê.
    assert summary["errors"][0].startswith("questão 5:")
    assert "alternativa correta" in summary["errors"][0]

    listed = await client.get("/api/v1/admin/questions", headers=admin.auth_header)
    assert listed.json()["total"] == 3


async def test_ai_classification_waits_for_human_review(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="banco5@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    subject = await create_subject(client, admin)
    question = await create_question(client, admin, statement=ENUNCIADO)

    suggested = await client.post(
        f"/api/v1/admin/questions/{question['public_id']}/suggest-classification",
        headers=admin.auth_header,
    )
    assert suggested.status_code == 200, suggested.text
    suggestion = suggested.json()
    assert suggestion["subject"] == "Direito Penal"
    assert suggestion["difficulty"] == "HARD"
    assert suggestion["applied"] is False
    assert suggestion["model"] == "gpt-4o-mini"
    assert suggestion["prompt_version"]

    # Nada foi aplicado: a questão ficou aguardando revisão, sem disciplina nem
    # dificuldade alteradas pelo modelo.
    detail = (
        await client.get(
            f"/api/v1/admin/questions/{question['public_id']}", headers=admin.auth_header
        )
    ).json()
    assert detail["status"] == "NEEDS_REVIEW"
    assert detail["subject_name"] is None
    assert detail["difficulty"] == "MEDIUM"

    applied = await client.post(
        f"/api/v1/admin/questions/{question['public_id']}/apply-classification",
        headers=admin.auth_header,
        json={"subject_public_id": subject["public_id"], "difficulty": "HARD"},
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()
    assert body["status"] == "PUBLISHED"
    assert body["subject_name"] == "Direito Penal"
    assert body["difficulty"] == "HARD"
    assert body["ai_suggestion"]["applied"] is True


async def test_second_classification_request_reuses_the_cache(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="banco6@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    question = await create_question(client, admin, statement=ENUNCIADO)

    url = f"/api/v1/admin/questions/{question['public_id']}/suggest-classification"
    first = await client.post(url, headers=admin.auth_header)
    second = await client.post(url, headers=admin.auth_header)

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["subject"] == second.json()["subject"]
    # A segunda chamada saiu do cache: o provedor foi acionado uma única vez.
    assert len(fake_provider.completion_calls) == 1


async def test_candidate_search_never_exposes_the_answer_key(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="banco7@exemplo.com.br")
    await create_question(client, admin, statement=ENUNCIADO)
    student = await create_user(client, emails, email="aluno.banco@exemplo.com.br")

    response = await client.get("/api/v1/questions", headers=student.auth_header)
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    alternative = items[0]["alternatives"][0]
    assert "is_correct" not in alternative
    assert "feedback" not in alternative


async def test_candidate_cannot_reach_the_admin_bank(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.sem.acesso@exemplo.com.br")
    response = await client.get("/api/v1/admin/questions", headers=student.auth_header)
    assert response.status_code == 403
