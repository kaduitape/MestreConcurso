"""O agente de memorização: baralho oficial em rascunho, a partir de aula publicada.

Este arquivo cobra a regra que fez o agente esperar até aqui: **cartão oficial
não nasce de rascunho**. O Professor gera a aula; enquanto uma pessoa não a
publica, o tópico fica sem baralho, com o motivo escrito — e isso não é falha
do item, é ausência de insumo.

O outro grupo cobra a fronteira entre os dois agentes: o Professor não monta
baralho e a Memorização não gera aula, mesmo quando os dois tipos estão no mesmo
plano.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.domain.agents import AgentKey
from app.models.catalog import Competition, Organization, Subject, Topic
from app.models.deck import DeckStatus, OfficialDeck
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.training import TrainingLesson, TrainingStatus
from app.models.user import User
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin
from tests.fake_ai import FakeProvider

AULA = (
    "A crase é a contração da preposição A com o artigo feminino A. "
    "Não se usa crase antes de palavra masculina nem antes de verbo."
)

CARTOES: dict[str, Any] = {
    "cards": [
        {
            "front": "O que é crase?",
            "back": "A contração da preposição A com o artigo feminino A.",
            "hint": None,
            "quote": "A crase é a contração da preposição A com o artigo feminino A",
        },
        {
            "front": "Qual a multa por errar a crase?",
            "back": "Duzentos reais.",
            "hint": None,
            # Não existe na aula: tem de ser descartado.
            "quote": "a multa por errar a crase é de duzentos reais",
        },
    ],
    "skipped_reason": None,
}


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=CARTOES)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _programme(session: AsyncSession, *, slug: str) -> tuple[Competition, Topic]:
    org = Organization(
        name=f"Tribunal {slug}", slug=f"tribunal-{slug}", short_name="TM", sphere="FEDERAL"
    )
    session.add(org)
    await session.flush()
    competition = Competition(
        name=f"Concurso {slug}", slug=f"concurso-{slug}", year=2026, organization_id=org.id
    )
    subject = Subject(slug=f"portugues-{slug}", name="Português")
    session.add_all([competition, subject])
    await session.flush()
    topic = Topic(subject_id=subject.id, name="Crase", slug=f"crase-{slug}")
    session.add(topic)
    await session.flush()
    topic.path = str(topic.id)

    notice = Notice(competition_id=competition.id, title="Edital", kind="MAIN")
    session.add(notice)
    await session.flush()
    disciplina = NoticeSubject(
        notice_id=notice.id, subject_id=subject.id, raw_label="Português", order_index=0
    )
    session.add(disciplina)
    await session.flush()
    session.add(
        NoticeTopic(
            notice_subject_id=disciplina.id, topic_id=topic.id, raw_label="Crase", order_index=0
        )
    )
    await session.commit()
    return competition, topic


async def _lesson(
    session: AsyncSession,
    admin: RegisteredUser,
    topic: Topic,
    *,
    status: str,
) -> TrainingLesson:
    autor = (await session.execute(select(User).where(User.email == admin.email))).scalar_one()
    lesson = TrainingLesson(
        created_by_user_id=autor.id,
        title="Aula de crase",
        subject="Português",
        topic="Crase",
        subject_id=topic.subject_id,
        topic_id=topic.id,
        character_name="Mestre",
        status=status,
        script={"objectives": [], "scenes": [{"id": 1, "narration": AULA, "screen_text": ""}]},
        published_at=datetime.now(UTC) if status == TrainingStatus.PUBLISHED else None,
    )
    session.add(lesson)
    await session.commit()
    return lesson


async def _confirmed_plan(
    client: AsyncClient, admin: RegisteredUser, competition: Competition, kinds: list[str]
) -> str:
    criado = await client.post(
        "/api/v1/admin/generation",
        headers=admin.auth_header,
        json={"competition_public_id": competition.public_id, "kinds": kinds},
    )
    assert criado.status_code == 201, criado.text
    plano = criado.json()["public_id"]
    confirmado = await client.post(
        f"/api/v1/admin/generation/{plano}/confirm", headers=admin.auth_header
    )
    assert confirmado.status_code == 200, confirmado.text
    return str(plano)


async def _run_memory(
    client: AsyncClient,
    admin: RegisteredUser,
    session: AsyncSession,
    competition: Competition,
) -> dict[str, Any]:
    """Roda o agente de memorização sozinho.

    A dependência do Professor é concluída à mão: aqui o que está sob teste é o
    que a Memorização faz com o material, não o grafo de dependências — e um
    pulo por dependência esconderia o motivo que este arquivo cobra.
    """
    from app.models.agent_run import AgentRun, AgentStep

    criado = await client.post(
        "/api/v1/admin/agents",
        headers=admin.auth_header,
        json={"competition_public_id": competition.public_id},
    )
    assert criado.status_code == 201, criado.text
    run_public_id = criado.json()["public_id"]

    linha = (
        await session.execute(select(AgentRun).where(AgentRun.public_id == run_public_id))
    ).scalar_one()
    professor = (
        await session.execute(
            select(AgentStep).where(
                AgentStep.run_id == linha.id, AgentStep.agent_key == AgentKey.TEACHER
            )
        )
    ).scalar_one()
    professor.status = "DONE"
    await session.commit()

    corpo = (
        await client.post(
            f"/api/v1/admin/agents/{run_public_id}/run/{AgentKey.MEMORY}",
            headers=admin.auth_header,
        )
    ).json()
    passo = next(item for item in corpo["steps"] if item["key"] == AgentKey.MEMORY)
    return dict(passo)


async def test_the_memory_agent_skips_without_a_confirmed_plan(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Pulado com motivo escrito — nunca verde por não ter o que fazer."""
    admin = await create_admin(client, emails, email="mem1@exemplo.com.br")
    competition, _ = await _programme(db_session, slug="mem1")

    passo = await _run_memory(client, admin, db_session, competition)

    assert passo["is_implemented"] is True
    assert passo["status"] == "SKIPPED"
    assert "baralho de flashcards" in passo["detail"]
    assert "não autoriza o gasto" in passo["detail"]


async def test_the_memory_agent_refuses_to_build_a_deck_from_a_draft_lesson(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    """A regra que fez o agente esperar: rascunho de IA não vira memória de longo prazo."""
    admin = await create_admin(client, emails, email="mem2@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))
    competition, topic = await _programme(db_session, slug="mem2")
    await _lesson(db_session, admin, topic, status=TrainingStatus.READY)
    await _confirmed_plan(client, admin, competition, ["FLASHCARD_DECK"])

    passo = await _run_memory(client, admin, db_session, competition)

    assert passo["status"] == "DONE"
    assert "sem material conferido" in passo["detail"]
    assert "não nasce de rascunho" in passo["detail"]
    assert fake_provider.completion_calls == [], "sem aula publicada não se gasta token"
    assert (await db_session.execute(select(OfficialDeck))).scalars().all() == []


async def test_the_memory_agent_builds_a_draft_deck_from_a_published_lesson(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    """E publica nada: o baralho fica em rascunho esperando curadoria."""
    admin = await create_admin(client, emails, email="mem3@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation",))
    competition, topic = await _programme(db_session, slug="mem3")
    aula = await _lesson(db_session, admin, topic, status=TrainingStatus.PUBLISHED)
    await _confirmed_plan(client, admin, competition, ["FLASHCARD_DECK"])

    passo = await _run_memory(client, admin, db_session, competition)

    assert passo["status"] == "DONE"
    assert "1 baralho(s) montado(s) em rascunho" in passo["detail"]
    assert "Nenhum baralho foi publicado" in passo["detail"]

    deck = (await db_session.execute(select(OfficialDeck))).scalars().one()
    assert deck.status == DeckStatus.DRAFT
    assert deck.topic_id == topic.id
    assert deck.source_kind == "LESSON"
    assert deck.source_ref == aula.public_id

    detalhe = (
        await client.get(
            f"/api/v1/admin/flashcard-decks/{deck.public_id}", headers=admin.auth_header
        )
    ).json()
    # Um cartão entrou (citação confere na aula) e o outro foi descartado.
    assert len(detalhe["cards"]) == 1
    assert detalhe["cards"][0]["origin"] == "AI"
    assert "Aula publicada" in detalhe["cards"][0]["source_document"]


async def test_the_teacher_does_not_build_decks_and_the_memory_does_not_write_lessons(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    """A fronteira entre os dois agentes, no mesmo plano.

    Sem o filtro por tipo, o primeiro a rodar levaria o crédito pelo trabalho do
    outro — e a tela de acompanhamento mentiria sobre quem fez o quê.
    """
    admin = await create_admin(client, emails, email="mem4@exemplo.com.br")
    await configure_ai(client, admin, features=("flashcard.generation", "training.script"))
    competition, topic = await _programme(db_session, slug="mem4")
    await _lesson(db_session, admin, topic, status=TrainingStatus.PUBLISHED)
    await _confirmed_plan(client, admin, competition, ["TRAINING_LESSON", "FLASHCARD_DECK"])

    passo = await _run_memory(client, admin, db_session, competition)
    assert passo["status"] == "DONE"
    assert "1 baralho(s) montado(s) em rascunho" in passo["detail"]

    plano = (await client.get("/api/v1/admin/generation", headers=admin.auth_header)).json()[
        "items"
    ][0]
    por_tipo = {item["kind"]: item["status"] for item in plano["items"]}
    # O item de aula continua esperando o Professor.
    assert por_tipo["TRAINING_LESSON"] == "PENDING"
    assert por_tipo["FLASHCARD_DECK"] in {"DONE", "REUSED"}
