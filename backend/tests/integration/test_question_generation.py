"""Geração de questões, ponta a ponta.

O que estes testes sustentam, em ordem de importância:

1. **Nenhuma questão gerada se passa por oficial.** Ela nasce ``AI_GENERATED``,
   sem banca, sem ano e sem prova, e o enunciado que se veste de questão de
   banca é descartado na origem.
2. **Nenhuma questão gerada chega a candidato sem conferência humana.** Ela
   nasce ``DRAFT``; publicar sem a marca de revisão é barrado pelo portão da
   Fase 3.
3. **O que não passou é dito.** Rascunho descartado aparece na resposta com o
   motivo, nunca só contado — e nunca guardado "com aviso".
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.models.question import Question, QuestionOrigin, QuestionStatus
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin, create_board
from tests.fake_ai import FakeProvider

MATERIAL = (
    "A crase é a contração da preposição A com o artigo feminino A. Não se usa "
    "crase antes de palavra masculina, antes de verbo e antes da maioria dos "
    "pronomes. Diante de nome de lugar, o teste é voltar de: se se volta da "
    "Bahia, vai-se à Bahia; se se volta de Roma, vai-se a Roma. A crase também "
    "é obrigatória nas locuções adverbiais femininas, como à noite e à tarde."
)


def _alternativas(correta: int = 1) -> list[dict[str, Any]]:
    textos = [
        "É a contração de duas preposições iguais.",
        "É a contração da preposição A com o artigo feminino A.",
        "É o acento usado obrigatoriamente antes de verbo.",
        "É o acento usado antes de qualquer palavra masculina.",
    ]
    return [
        {
            "letter": letra,
            "content": texto,
            "is_correct": indice == correta,
            "feedback": "É o que o material diz." if indice == correta else "O material nega.",
        }
        for indice, (letra, texto) in enumerate(zip("ABCD", textos, strict=True))
    ]


def _questao(**troca: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "statement": (
            "Assinale a alternativa que define corretamente o fenômeno da crase "
            "na língua portuguesa."
        ),
        "difficulty": "MEDIUM",
        "alternatives": _alternativas(),
        "explanation": "A definição está no material.",
        "quote": "A crase é a contração da preposição A com o artigo feminino A",
    }
    base.update(troca)
    return base


#: Uma boa, uma que se veste de banca, uma com citação inventada.
PAYLOAD: dict[str, Any] = {
    "questions": [
        _questao(),
        _questao(
            statement=(
                "(CESPE/2023) Assinale a alternativa que trata do emprego da "
                "crase nas locuções adverbiais femininas."
            ),
            quote="a crase também é obrigatória nas locuções adverbiais femininas",
        ),
        _questao(
            statement=(
                "Assinale a alternativa correta sobre a multa prevista para o "
                "emprego indevido da crase em petições."
            ),
            quote="a multa pelo emprego indevido da crase é de duzentos reais",
        ),
    ],
    "skipped_reason": None,
}


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _gerar(client: AsyncClient, admin: RegisteredUser, **body: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"material": MATERIAL, "quantity": 5, **body}
    resposta = await client.post(
        "/api/v1/admin/questions/generate", headers=admin.auth_header, json=payload
    )
    assert resposta.status_code == 200, resposta.text
    return dict(resposta.json())


# --------------------------------------------------------------------------- #
# A conferência na origem
# --------------------------------------------------------------------------- #
async def test_the_generated_question_is_born_a_draft_without_board_or_year(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="qg1@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))

    corpo = await _gerar(client, admin)

    assert len(corpo["created"]) == 1
    criada = corpo["created"][0]
    assert criada["origin"] == QuestionOrigin.AI_GENERATED
    assert criada["status"] == QuestionStatus.DRAFT
    assert criada["year"] is None

    linha = (
        await db_session.execute(select(Question).where(Question.public_id == criada["public_id"]))
    ).scalar_one()
    # Sem banca, sem ano e sem prova: preenchê-los a faria passar por aplicada.
    assert linha.exam_board_id is None
    assert linha.exam_id is None
    assert linha.year is None
    assert linha.reviewed_by_user_id is None
    assert linha.ai_suggestion["quote"]


async def test_a_question_dressed_as_a_board_question_is_discarded(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
) -> None:
    """O enunciado que se veste de prova não entra nem com a banca no catálogo
    nem sem ela: o formato de atribuição já basta."""
    admin = await create_admin(client, emails, email="qg2@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    await create_board(client, admin)

    corpo = await _gerar(client, admin)

    motivos = {item["reason"] for item in corpo["discarded"]}
    assert any("banca" in motivo for motivo in motivos)
    assert corpo["reasons"]["FABRICATED_PROVENANCE"] == 1


async def test_a_question_whose_quote_is_not_in_the_material_is_discarded(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="qg3@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))

    corpo = await _gerar(client, admin)

    assert corpo["reasons"]["QUOTE_NOT_IN_MATERIAL"] == 1
    descartada = next(item for item in corpo["discarded"] if "multa" in item["statement"])
    assert "citação" in descartada["reason"]


async def test_the_material_needs_to_be_long_enough_to_sustain_a_question(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="qg4@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))

    resposta = await client.post(
        "/api/v1/admin/questions/generate",
        headers=admin.auth_header,
        json={"material": "A crase é a contração da preposição A.", "quantity": 3},
    )

    assert resposta.status_code == 422, resposta.text
    assert fake_provider.completion_calls == [], "material curto não gasta token"


async def test_generating_twice_does_not_duplicate_the_question(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="qg5@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))

    await _gerar(client, admin)
    segunda = await _gerar(client, admin)

    assert segunda["created"] == []
    assert segunda["duplicated"] == 1


# --------------------------------------------------------------------------- #
# O portão da publicação
# --------------------------------------------------------------------------- #
async def test_publishing_without_human_review_is_blocked(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """A regra da Fase 3 que dá sentido ao rascunho."""
    admin = await create_admin(client, emails, email="qg6@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    corpo = await _gerar(client, admin)
    public_id = corpo["created"][0]["public_id"]

    barrada = await client.patch(
        f"/api/v1/admin/questions/{public_id}",
        headers=admin.auth_header,
        json={"status": "PUBLISHED"},
    )

    assert barrada.status_code == 409, barrada.text
    assert barrada.json()["error"]["code"] == "content_audit_blocked"


async def test_after_a_person_reviews_it_the_question_publishes(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="qg7@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    corpo = await _gerar(client, admin)
    public_id = corpo["created"][0]["public_id"]

    conferida = await client.post(
        f"/api/v1/admin/questions/{public_id}/reviewed", headers=admin.auth_header
    )
    assert conferida.status_code == 200, conferida.text

    publicada = await client.patch(
        f"/api/v1/admin/questions/{public_id}",
        headers=admin.auth_header,
        json={"status": "PUBLISHED"},
    )
    assert publicada.status_code == 200, publicada.text
    assert publicada.json()["status"] == "PUBLISHED"
    # E continua dizendo que foi gerada por IA depois de publicada.
    assert publicada.json()["origin"] == QuestionOrigin.AI_GENERATED

    linha = (
        await db_session.execute(select(Question).where(Question.public_id == public_id))
    ).scalar_one()
    assert linha.reviewed_by_user_id is not None
    assert linha.reviewed_at is not None


async def test_the_review_mark_is_for_generated_questions_only(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="qg8@exemplo.com.br")
    criada = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json={
            "statement": "Questão oficial cadastrada à mão para este teste de marca.",
            "alternatives": _alternativas(),
            "status": "DRAFT",
        },
    )
    assert criada.status_code == 201, criada.text

    resposta = await client.post(
        f"/api/v1/admin/questions/{criada.json()['public_id']}/reviewed",
        headers=admin.auth_header,
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["error"]["code"] == "question_not_generated"


async def test_a_draft_question_does_not_reach_the_candidate(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """Rascunho não entra em busca de questão: o filtro é por status publicado."""
    from tests.factories import create_user

    admin = await create_admin(client, emails, email="qg9@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    candidato = await create_user(client, emails, email="qg9c@exemplo.com.br")
    corpo = await _gerar(client, admin)
    public_id = corpo["created"][0]["public_id"]

    busca = await client.get("/api/v1/questions?page=1&page_size=50", headers=candidato.auth_header)

    assert busca.status_code == 200, busca.text
    assert public_id not in {item["public_id"] for item in busca.json()["items"]}
