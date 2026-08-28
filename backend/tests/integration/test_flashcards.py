"""Flashcards: criação, origem declarada e geração com citação conferida."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderCredentials
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

MATERIAL = (
    "O regime disciplinar diferenciado poderá ser aplicado ao preso provisório e ao "
    "condenado, nacional ou estrangeiro, conforme o artigo 52 da Lei de Execução Penal. "
    "A duração máxima é de até dois anos, sem prejuízo de repetição da sanção por nova "
    "falta grave de mesma espécie. O recolhimento se dá em cela individual."
)

GENERATION_PAYLOAD: dict[str, Any] = {
    "cards": [
        {
            "front": "A quem pode ser aplicado o regime disciplinar diferenciado?",
            "back": "Ao preso provisório e ao condenado, nacional ou estrangeiro.",
            "hint": None,
            "quote": "poderá ser aplicado ao preso provisório e ao condenado",
        },
        {
            "front": "Qual a duração máxima do RDD?",
            "back": "Até dois anos.",
            "hint": None,
            "quote": "A duração máxima é de até dois anos",
        },
        {
            "front": "Qual o prazo de recurso contra a aplicação do RDD?",
            "back": "Quinze dias úteis.",
            "hint": None,
            # Citação que NÃO existe no material: precisa ser descartada.
            "quote": "o prazo de recurso contra a aplicação é de quinze dias úteis",
        },
    ],
    "skipped_reason": None,
}


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=GENERATION_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _card(client: AsyncClient, user: RegisteredUser, **body: Any) -> dict[str, Any]:
    payload = {"front": "Pergunta padrão do cartão", "back": "Resposta", **body}
    response = await client.post("/api/v1/flashcards", headers=user.auth_header, json=payload)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_card_is_created_with_its_origin_declared(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="card1@exemplo.com.br")
    subject = await create_subject(client, admin)

    card = await _card(
        client,
        admin,
        front="O que é o regime disciplinar diferenciado?",
        back="Sanção disciplinar com isolamento em cela individual.",
        subject_public_id=subject["public_id"],
    )

    assert card["origin"] == "USER"
    assert card["subject_name"] == "Direito Penal"
    assert card["is_owned"] is True
    # Cartão escrito à mão não finge ter origem documental.
    assert card["source_quote"] is None
    assert card["model_slug"] is None


async def test_duplicate_front_is_refused(client: AsyncClient, emails: CapturingDispatcher) -> None:
    student = await create_user(client, emails, email="card2@exemplo.com.br")
    await _card(client, student, front="Qual o prazo do recurso administrativo?")

    duplicated = await client.post(
        "/api/v1/flashcards",
        headers=student.auth_header,
        json={"front": "  QUAL O PRAZO DO RECURSO ADMINISTRATIVO?  ", "back": "outro"},
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["code"] == "duplicate_flashcard"


async def test_card_born_from_a_wrong_question_keeps_the_reference(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="card3@exemplo.com.br")
    subject = await create_subject(client, admin)
    question = await create_question(
        client,
        admin,
        statement="Questão sobre a aplicação do regime disciplinar diferenciado",
        correct="B",
        subject_public_id=subject["public_id"],
        explanation="Ver artigo 52 da LEP.",
    )

    created = await client.post(
        "/api/v1/flashcards/from-source",
        headers=admin.auth_header,
        json={"question_public_id": question["public_id"]},
    )
    assert created.status_code == 201, created.text
    card = created.json()

    assert card["origin"] == "QUESTION"
    assert card["source_ref"] == question["public_id"]
    assert card["front"].startswith("Questão sobre a aplicação")
    # O verso traz o gabarito e o comentário da alternativa correta.
    assert card["back"].startswith("B)")
    assert "Comentário da alternativa B." in card["back"]


async def test_card_born_from_a_classified_error(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="card4@exemplo.com.br")
    subject = await create_subject(client, admin)
    question = await create_question(
        client,
        admin,
        statement="Questão que o candidato errou e classificou no caderno",
        subject_public_id=subject["public_id"],
    )
    wrong = next(item["letter"] for item in question["alternatives"] if not item["is_correct"])
    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=admin.auth_header,
        json={"letter": wrong},
    )
    history = await client.get("/api/v1/questions/history", headers=admin.auth_header)
    attempt = history.json()["items"][0]["public_id"]
    classified = await client.post(
        f"/api/v1/errors/attempts/{attempt}",
        headers=admin.auth_header,
        json={"cause": "FORGETTING"},
    )
    assert classified.status_code == 201, classified.text

    created = await client.post(
        "/api/v1/flashcards/from-source",
        headers=admin.auth_header,
        json={"error_public_id": classified.json()["public_id"]},
    )
    assert created.status_code == 201, created.text
    card = created.json()

    assert card["origin"] == "ERROR"
    assert card["source_ref"] == classified.json()["public_id"]
    assert card["subject_name"] == "Direito Penal"


async def test_generation_discards_the_card_whose_quote_is_not_in_the_material(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="card5@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))

    response = await client.post(
        "/api/v1/flashcards/generate",
        headers=admin.auth_header,
        json={"material": MATERIAL, "quantity": 5, "source_document": "LEP art. 52"},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # Dois cartões têm citação real; o terceiro foi inventado e não entra no baralho.
    assert len(body["created"]) == 2
    assert len(body["discarded"]) == 1
    assert "prazo de recurso" in body["discarded"][0]

    for card in body["created"]:
        assert card["origin"] == "AI"
        assert card["source_quote"] in MATERIAL
        assert card["source_document"] == "LEP art. 52"
        assert card["model_slug"] == "gpt-4o-mini"


async def test_material_too_short_is_refused_before_spending_tokens(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="card6@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))

    response = await client.post(
        "/api/v1/flashcards/generate",
        headers=admin.auth_header,
        json={"material": "texto curto", "quantity": 3},
    )
    assert response.status_code == 422
    assert fake_provider.completion_calls == []


async def test_second_generation_of_the_same_material_uses_the_cache(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="card7@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))

    body = {"material": MATERIAL, "quantity": 5}
    first = await client.post("/api/v1/flashcards/generate", headers=admin.auth_header, json=body)
    second = await client.post("/api/v1/flashcards/generate", headers=admin.auth_header, json=body)

    assert first.status_code == 200 and second.status_code == 200
    # A segunda chamada saiu do cache e os cartões já existiam: nada duplicado.
    assert len(fake_provider.completion_calls) == 1
    assert second.json()["created"] == []

    listed = await client.get("/api/v1/flashcards", headers=admin.auth_header)
    assert listed.json()["total"] == 2


async def test_editing_and_removing_only_reaches_your_own_cards(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="card8@exemplo.com.br")
    intruder = await create_user(client, emails, email="intruso.card@exemplo.com.br")
    card = await _card(client, student, front="Cartão que pertence a quem o criou")

    updated = await client.patch(
        f"/api/v1/flashcards/{card['public_id']}",
        headers=student.auth_header,
        json={"back": "Resposta revisada"},
    )
    assert updated.status_code == 200
    assert updated.json()["back"] == "Resposta revisada"

    stolen = await client.patch(
        f"/api/v1/flashcards/{card['public_id']}",
        headers=intruder.auth_header,
        json={"back": "invasão"},
    )
    assert stolen.status_code == 404

    removed = await client.delete(
        f"/api/v1/flashcards/{card['public_id']}", headers=student.auth_header
    )
    assert removed.status_code == 200
    listed = await client.get("/api/v1/flashcards", headers=student.auth_header)
    assert listed.json()["total"] == 0


async def test_source_is_required_to_create_from_source(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="card9@exemplo.com.br")
    response = await client.post(
        "/api/v1/flashcards/from-source", headers=student.auth_header, json={}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "source_required"
