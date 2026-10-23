"""Baralho oficial por tópico, ponta a ponta.

Os testes que sustentam esta parte são os de **escopo**: um cartão oficial não
chega a ninguém por existir no banco. Ele chega porque o baralho foi publicado
por uma pessoa **e** porque o candidato entrou nele. Entre esses dois fatos não
há atalho, e é isso que separa "cartão global com escopo" de "cartão global
solto", que cairia na fila de quem estuda outro concurso.

O outro grupo cobra a contrapartida: sair do baralho ou tirar um cartão de
circulação **não apaga memória de ninguém**.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.models.flashcard import CardMemoryState
from app.models.user import User
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin, create_subject, create_user
from tests.fake_ai import FakeProvider

MATERIAL = (
    "A crase é a contração da preposição A com o artigo feminino A. Não se usa crase "
    "antes de palavra masculina, antes de verbo e antes da maioria dos pronomes. "
    "Diante de nome de lugar, o teste é voltar de: volto da Bahia, então vou à Bahia."
)

PAYLOAD: dict[str, Any] = {
    "cards": [
        {
            "front": "O que é crase?",
            "back": "A contração da preposição A com o artigo feminino A.",
            "hint": None,
            "quote": "A crase é a contração da preposição A com o artigo feminino A",
        },
        {
            "front": "Qual o teste para nome de lugar?",
            "back": "Voltar de: volto da Bahia, então vou à Bahia.",
            "hint": None,
            "quote": "o teste é voltar de",
        },
        {
            "front": "Qual a multa por usar crase errada?",
            "back": "Duzentos reais.",
            "hint": None,
            # Citação que não existe no material: precisa ser descartada.
            "quote": "a multa por usar crase errada é de duzentos reais",
        },
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


async def _topic(client: AsyncClient, admin: RegisteredUser, *, name: str = "Crase") -> str:
    subject = await create_subject(client, admin, name=f"Português {name}")
    created = await client.post(
        f"/api/v1/admin/catalog/subjects/{subject['public_id']}/topics",
        headers=admin.auth_header,
        json={"name": name},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["public_id"])


async def _deck(client: AsyncClient, admin: RegisteredUser, *, name: str = "Crase") -> str:
    topic = await _topic(client, admin, name=name)
    created = await client.post(
        "/api/v1/admin/flashcard-decks",
        headers=admin.auth_header,
        json={"topic_public_id": topic},
    )
    assert created.status_code == 201, created.text
    corpo = created.json()
    assert corpo["status"] == "DRAFT"
    return str(corpo["public_id"])


async def _card(client: AsyncClient, admin: RegisteredUser, deck: str, *, front: str) -> str:
    created = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/cards",
        headers=admin.auth_header,
        json={"front": front, "back": "A resposta curada pela equipe."},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["public_id"])


async def _queue_ids(client: AsyncClient, user: RegisteredUser) -> list[str]:
    queue = await client.get("/api/v1/review/queue", headers=user.auth_header)
    assert queue.status_code == 200, queue.text
    return [item["card"]["public_id"] for item in queue.json()["items"]]


# --------------------------------------------------------------------------- #
# Escopo: publicar não é entregar
# --------------------------------------------------------------------------- #
async def test_an_official_card_reaches_only_who_entered_a_published_deck(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O teste central da parte: três portas, e nenhuma delas é opcional."""
    admin = await create_admin(client, emails, email="bar1@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar1c@exemplo.com.br")
    deck = await _deck(client, admin)
    card = await _card(client, admin, deck, front="O que é crase na gramática?")

    # Porta 1: rascunho não chega a ninguém.
    listagem = (await client.get("/api/v1/flashcards", headers=candidato.auth_header)).json()
    assert listagem["items"] == []
    assert await _queue_ids(client, candidato) == []

    publicado = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header
    )
    assert publicado.status_code == 200, publicado.text
    assert publicado.json()["status"] == "PUBLISHED"

    # Porta 2: publicado, mas sem assinatura, continua invisível.
    assert (await client.get("/api/v1/flashcards", headers=candidato.auth_header)).json()[
        "items"
    ] == []

    assinado = await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)
    assert assinado.status_code == 200, assinado.text
    assert assinado.json()["is_subscribed"] is True

    # Porta 3: agora sim — e o cartão chega com o selo de oficial.
    itens = (await client.get("/api/v1/flashcards", headers=candidato.auth_header)).json()["items"]
    assert [item["public_id"] for item in itens] == [card]
    assert itens[0]["is_official"] is True
    assert itens[0]["is_owned"] is False
    assert itens[0]["origin"] == "EDITORIAL"
    assert card in await _queue_ids(client, candidato)


async def test_a_draft_deck_cannot_be_subscribed(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Rascunho não é conteúdo: ele existe por ainda não ter sido conferido."""
    admin = await create_admin(client, emails, email="bar2@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar2c@exemplo.com.br")
    deck = await _deck(client, admin)
    await _card(client, admin, deck, front="Pergunta ainda em rascunho sobre crase")

    resposta = await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)

    assert resposta.status_code == 404, resposta.text


async def test_leaving_the_deck_empties_the_queue_and_keeps_the_memory(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Sair de circulação e apagar histórico são coisas diferentes."""
    admin = await create_admin(client, emails, email="bar3@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar3c@exemplo.com.br")
    deck = await _deck(client, admin)
    card = await _card(client, admin, deck, front="Quando não se usa crase?")
    await client.post(f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header)
    await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)
    assert card in await _queue_ids(client, candidato)

    respondido = await client.post(
        f"/api/v1/review/{card}/answer",
        headers=candidato.auth_header,
        json={"rating": "GOOD", "time_seconds": 8},
    )
    assert respondido.status_code == 200, respondido.text
    intervalo = respondido.json()["interval_days"]
    assert intervalo >= 1

    saiu = await client.delete(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)
    assert saiu.status_code == 200, saiu.text

    assert await _queue_ids(client, candidato) == []
    assert (await client.get("/api/v1/flashcards", headers=candidato.auth_header)).json()[
        "items"
    ] == []

    # A memória continua no banco, intacta.
    user_id = (
        await db_session.execute(select(User.id).where(User.email == candidato.email))
    ).scalar_one()
    estados = (
        (
            await db_session.execute(
                select(CardMemoryState).where(CardMemoryState.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(estados) == 1
    assert estados[0].interval_days == intervalo
    assert estados[0].last_rating == "GOOD"
    assert estados[0].last_reviewed_at is not None

    # E voltar não recomeça do zero.
    await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)
    estatisticas = (await client.get("/api/v1/review/stats", headers=candidato.auth_header)).json()
    assert estatisticas["total_cards"] == 1
    assert estatisticas["total_reviews"] == 1


async def test_a_card_out_of_circulation_leaves_the_queue(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A ferramenta da curadoria para o cartão que o portão não pega."""
    admin = await create_admin(client, emails, email="bar4@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar4c@exemplo.com.br")
    deck = await _deck(client, admin)
    ruim = await _card(client, admin, deck, front="Cartão com redação infeliz sobre crase")
    bom = await _card(client, admin, deck, front="Cartão bem escrito sobre crase")
    await client.post(f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header)
    await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)
    assert sorted(await _queue_ids(client, candidato)) == sorted([ruim, bom])

    tirado = await client.patch(
        f"/api/v1/admin/flashcard-decks/{deck}/cards/{ruim}",
        headers=admin.auth_header,
        json={"is_active": False},
    )
    assert tirado.status_code == 200, tirado.text
    assert tirado.json()["is_active"] is False

    assert await _queue_ids(client, candidato) == [bom]

    # E a curadoria continua vendo o cartão para poder devolvê-lo.
    detalhe = (
        await client.get(f"/api/v1/admin/flashcard-decks/{deck}", headers=admin.auth_header)
    ).json()
    assert {item["public_id"]: item["is_active"] for item in detalhe["cards"]} == {
        ruim: False,
        bom: True,
    }
    assert detalhe["deck"]["active_cards"] == 1
    assert detalhe["deck"]["inactive_cards"] == 1


# --------------------------------------------------------------------------- #
# Curadoria
# --------------------------------------------------------------------------- #
async def test_a_deck_without_an_active_card_is_not_published(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bar5@exemplo.com.br")
    deck = await _deck(client, admin)

    vazio = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header
    )
    assert vazio.status_code == 422, vazio.text
    assert vazio.json()["error"]["code"] == "deck_without_cards"

    card = await _card(client, admin, deck, front="Único cartão deste baralho de crase")
    await client.patch(
        f"/api/v1/admin/flashcard-decks/{deck}/cards/{card}",
        headers=admin.auth_header,
        json={"is_active": False},
    )
    sem_ativo = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header
    )
    assert sem_ativo.status_code == 422, sem_ativo.text


async def test_a_topic_has_a_single_official_deck(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """ "O baralho oficial do tópico" não pode ser ambíguo."""
    admin = await create_admin(client, emails, email="bar6@exemplo.com.br")
    topic = await _topic(client, admin)

    primeiro = await client.post(
        "/api/v1/admin/flashcard-decks",
        headers=admin.auth_header,
        json={"topic_public_id": topic},
    )
    assert primeiro.status_code == 201, primeiro.text

    segundo = await client.post(
        "/api/v1/admin/flashcard-decks",
        headers=admin.auth_header,
        json={"topic_public_id": topic},
    )
    assert segundo.status_code == 409, segundo.text
    assert segundo.json()["error"]["code"] == "deck_already_exists"


async def test_the_candidate_cannot_edit_or_remove_an_official_card(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bar7@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar7c@exemplo.com.br")
    deck = await _deck(client, admin)
    card = await _card(client, admin, deck, front="Cartão oficial que ninguém edita por fora")
    await client.post(f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header)
    await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)

    # Ele vê o cartão...
    visto = await client.get(f"/api/v1/flashcards/{card}", headers=candidato.auth_header)
    assert visto.status_code == 200, visto.text

    # ...e não mexe nele.
    editado = await client.patch(
        f"/api/v1/flashcards/{card}",
        headers=candidato.auth_header,
        json={"back": "Resposta trocada por fora"},
    )
    assert editado.status_code == 404, editado.text
    removido = await client.delete(f"/api/v1/flashcards/{card}", headers=candidato.auth_header)
    assert removido.status_code == 404, removido.text


async def test_an_archived_deck_leaves_circulation_without_deleting_cards(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bar8@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar8c@exemplo.com.br")
    deck = await _deck(client, admin)
    card = await _card(client, admin, deck, front="Cartão de um baralho que será arquivado")
    await client.post(f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header)
    await client.post(f"/api/v1/decks/{deck}/subscribe", headers=candidato.auth_header)

    arquivado = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/archive", headers=admin.auth_header
    )
    assert arquivado.status_code == 200, arquivado.text
    assert await _queue_ids(client, candidato) == []

    detalhe = (
        await client.get(f"/api/v1/admin/flashcard-decks/{deck}", headers=admin.auth_header)
    ).json()
    assert [item["public_id"] for item in detalhe["cards"]] == [card]


# --------------------------------------------------------------------------- #
# Geração com citação conferida
# --------------------------------------------------------------------------- #
async def test_generation_into_the_deck_discards_the_card_without_a_literal_quote(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """Mesma peneira do baralho pessoal, pelo mesmo motivo."""
    admin = await create_admin(client, emails, email="bar9@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))
    deck = await _deck(client, admin)

    gerado = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/generate",
        headers=admin.auth_header,
        json={"material": MATERIAL, "quantity": 5},
    )
    assert gerado.status_code == 200, gerado.text
    corpo = gerado.json()

    assert len(corpo["created"]) == 2
    assert len(corpo["discarded"]) == 1
    assert "multa" in corpo["discarded"][0]
    # Cartão de IA dentro de baralho oficial continua dizendo que é de IA.
    assert {item["origin"] for item in corpo["created"]} == {"AI"}
    assert all(item["source_quote"] for item in corpo["created"])

    # E nada foi publicado pela geração.
    detalhe = (
        await client.get(f"/api/v1/admin/flashcard-decks/{deck}", headers=admin.auth_header)
    ).json()
    assert detalhe["deck"]["status"] == "DRAFT"
    assert detalhe["deck"]["ai_cards"] == 2


async def test_generating_twice_does_not_duplicate_the_card(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="bar10@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))
    deck = await _deck(client, admin)

    await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/generate",
        headers=admin.auth_header,
        json={"material": MATERIAL, "quantity": 5},
    )
    segunda = await client.post(
        f"/api/v1/admin/flashcard-decks/{deck}/generate",
        headers=admin.auth_header,
        json={"material": MATERIAL, "quantity": 5},
    )

    corpo = segunda.json()
    assert corpo["created"] == []
    assert corpo["duplicated"] == 2


# --------------------------------------------------------------------------- #
# O catálogo do candidato
# --------------------------------------------------------------------------- #
async def test_without_a_primary_competition_the_catalogue_says_why(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Despejar todo baralho publicado da plataforma seria fingir recomendação."""
    admin = await create_admin(client, emails, email="bar11@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar11c@exemplo.com.br")
    deck = await _deck(client, admin)
    await _card(client, admin, deck, front="Cartão de um tópico fora do edital dele")
    await client.post(f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header)

    catalogo = (await client.get("/api/v1/decks", headers=candidato.auth_header)).json()

    assert catalogo["items"] == []
    assert catalogo["total"] == 0
    assert "concurso principal" in catalogo["scope"]
    assert catalogo["competition_name"] is None


async def test_the_catalogue_lists_the_decks_of_the_topics_in_my_notice(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O escopo é o edital do candidato, não o acervo inteiro da plataforma."""
    from app.models.catalog import Competition, Organization, Subject, Topic
    from app.models.notice import Notice
    from app.models.notice_analysis import NoticeSubject, NoticeTopic

    admin = await create_admin(client, emails, email="bar12@exemplo.com.br")
    candidato = await create_user(client, emails, email="bar12c@exemplo.com.br")

    org = Organization(
        name="Tribunal do Baralho", slug="tribunal-baralho", short_name="TB", sphere="FEDERAL"
    )
    db_session.add(org)
    await db_session.flush()
    competition = Competition(
        name="Concurso do Baralho",
        slug="concurso-baralho",
        year=2026,
        organization_id=org.id,
        is_published=True,
    )
    subject = Subject(slug="portugues-baralho", name="Português do Baralho")
    db_session.add_all([competition, subject])
    await db_session.flush()
    dentro = Topic(subject_id=subject.id, name="Crase no edital", slug="crase-edital")
    fora = Topic(subject_id=subject.id, name="Tópico fora do edital", slug="fora-edital")
    db_session.add_all([dentro, fora])
    await db_session.flush()
    dentro.path = str(dentro.id)
    fora.path = str(fora.id)

    notice = Notice(competition_id=competition.id, title="Edital do Baralho", kind="MAIN")
    db_session.add(notice)
    await db_session.flush()
    disciplina = NoticeSubject(
        notice_id=notice.id, subject_id=subject.id, raw_label="Português", order_index=0
    )
    db_session.add(disciplina)
    await db_session.flush()
    db_session.add(
        NoticeTopic(
            notice_subject_id=disciplina.id,
            topic_id=dentro.id,
            raw_label="Crase",
            order_index=0,
        )
    )
    await db_session.commit()

    publicados: list[str] = []
    for topic in (dentro, fora):
        criado = await client.post(
            "/api/v1/admin/flashcard-decks",
            headers=admin.auth_header,
            json={"topic_public_id": topic.public_id},
        )
        assert criado.status_code == 201, criado.text
        deck = criado.json()["public_id"]
        await client.post(
            f"/api/v1/admin/flashcard-decks/{deck}/cards",
            headers=admin.auth_header,
            json={"front": f"Pergunta do baralho de {topic.name}", "back": "Resposta."},
        )
        await client.post(
            f"/api/v1/admin/flashcard-decks/{deck}/publish", headers=admin.auth_header
        )
        publicados.append(deck)

    focado = await client.put(
        "/api/v1/users/me/focus",
        headers=candidato.auth_header,
        json={"competition_public_id": competition.public_id},
    )
    assert focado.status_code == 200, focado.text

    catalogo = (await client.get("/api/v1/decks", headers=candidato.auth_header)).json()

    assert [item["public_id"] for item in catalogo["items"]] == [publicados[0]]
    assert catalogo["competition_name"] == "Concurso do Baralho"
    assert "Concurso do Baralho" in catalogo["scope"]
    assert catalogo["items"][0]["is_subscribed"] is False
