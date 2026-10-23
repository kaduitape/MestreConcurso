"""O agente mestre de batalhas: questões inéditas em rascunho, por tópico do edital.

Mesma regra que prendeu o agente de memorização, pelo mesmo motivo: **questão
não nasce de rascunho**. E uma regra a mais, que só a questão tem — se nada
sobreviver à conferência de origem, o passo diz isso em vez de contar como
sucesso o que não produziu nada.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.domain.agents import AgentKey
from app.models.catalog import Competition, Organization, Subject, Topic
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.question import Question, QuestionOrigin, QuestionStatus
from app.models.training import TrainingLesson, TrainingStatus
from app.models.user import User
from app.services.question_bank import statement_checksum
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin
from tests.fake_ai import FakeProvider

AULA = (
    "A crase é a contração da preposição A com o artigo feminino A. Não se usa "
    "crase antes de palavra masculina, antes de verbo e antes da maioria dos "
    "pronomes. Diante de nome de lugar, o teste é voltar de: se se volta da "
    "Bahia, vai-se à Bahia. A crase é obrigatória nas locuções adverbiais "
    "femininas, como à noite e à tarde, e também na expressão à medida que."
)


def _alternativas() -> list[dict[str, Any]]:
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
            "is_correct": indice == 1,
            "feedback": "É o que a aula diz." if indice == 1 else "A aula nega.",
        }
        for indice, (letra, texto) in enumerate(zip("ABCD", textos, strict=True))
    ]


BOA: dict[str, Any] = {
    "questions": [
        {
            "statement": (
                "Assinale a alternativa que define corretamente o fenômeno da "
                "crase na língua portuguesa."
            ),
            "difficulty": "MEDIUM",
            "alternatives": _alternativas(),
            "explanation": "A definição está na aula.",
            "quote": "A crase é a contração da preposição A com o artigo feminino A",
        }
    ],
    "skipped_reason": None,
}

#: Todas com citação inventada: nada deve sobreviver à conferência.
NENHUMA_PASSA: dict[str, Any] = {
    "questions": [
        {
            "statement": (
                "Assinale a alternativa correta sobre a multa prevista para o "
                "emprego indevido da crase em petições judiciais."
            ),
            "difficulty": "MEDIUM",
            "alternatives": _alternativas(),
            "explanation": "Inventada.",
            "quote": "a multa pelo emprego indevido da crase é de duzentos reais",
        }
    ],
    "skipped_reason": None,
}


def _provider(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> FakeProvider:
    provider = FakeProvider(completion_payload=payload)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


@pytest.fixture
def boa_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    return _provider(monkeypatch, BOA)


@pytest.fixture
def nada_passa_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    return _provider(monkeypatch, NENHUMA_PASSA)


async def _programme(session: AsyncSession, *, slug: str) -> tuple[Competition, Topic]:
    org = Organization(
        name=f"Tribunal {slug}", slug=f"tribunal-{slug}", short_name="TB", sphere="FEDERAL"
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
    session: AsyncSession, admin: RegisteredUser, topic: Topic, *, status: str
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
    client: AsyncClient,
    admin: RegisteredUser,
    competition: Competition,
    **extra: Any,
) -> str:
    criado = await client.post(
        "/api/v1/admin/generation",
        headers=admin.auth_header,
        json={
            "competition_public_id": competition.public_id,
            "kinds": ["QUESTION_SET"],
            **extra,
        },
    )
    assert criado.status_code == 201, criado.text
    plano = criado.json()
    confirmado = await client.post(
        f"/api/v1/admin/generation/{plano['public_id']}/confirm", headers=admin.auth_header
    )
    assert confirmado.status_code == 200, confirmado.text
    return str(plano["public_id"])


async def _run_battle_master(
    client: AsyncClient, admin: RegisteredUser, session: AsyncSession, competition: Competition
) -> dict[str, Any]:
    """Roda o agente sozinho, com a dependência do Professor concluída à mão."""
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
            f"/api/v1/admin/agents/{run_public_id}/run/{AgentKey.BATTLE_MASTER}",
            headers=admin.auth_header,
        )
    ).json()
    return dict(next(item for item in corpo["steps"] if item["key"] == AgentKey.BATTLE_MASTER))


async def test_the_battle_master_skips_without_a_confirmed_plan(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="bm1@exemplo.com.br")
    competition, _ = await _programme(db_session, slug="bm1")

    passo = await _run_battle_master(client, admin, db_session, competition)

    assert passo["is_implemented"] is True
    assert passo["status"] == "SKIPPED"
    assert "questões" in passo["detail"]
    assert "não autoriza o gasto" in passo["detail"]


async def test_the_battle_master_refuses_to_write_questions_from_a_draft_lesson(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    boa_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="bm2@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    competition, topic = await _programme(db_session, slug="bm2")
    await _lesson(db_session, admin, topic, status=TrainingStatus.READY)
    await _confirmed_plan(client, admin, competition)

    passo = await _run_battle_master(client, admin, db_session, competition)

    assert passo["status"] == "DONE"
    assert "sem material conferido" in passo["detail"]
    assert boa_provider.completion_calls == [], "sem aula publicada não se gasta token"
    total = (
        await db_session.execute(
            select(func.count()).select_from(Question).where(Question.origin == "AI_GENERATED")
        )
    ).scalar_one()
    assert total == 0


async def test_the_battle_master_writes_drafts_from_a_published_lesson(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    boa_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="bm3@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    competition, topic = await _programme(db_session, slug="bm3")
    aula = await _lesson(db_session, admin, topic, status=TrainingStatus.PUBLISHED)
    await _confirmed_plan(client, admin, competition)

    passo = await _run_battle_master(client, admin, db_session, competition)

    assert passo["status"] == "DONE"
    assert "1 tópico(s) com questões geradas em rascunho" in passo["detail"]
    assert "Nada foi publicado" in passo["detail"]
    assert "nenhuma delas se apresenta como questão de banca" in passo["detail"]

    questao = (
        await db_session.execute(
            select(Question).where(Question.origin == QuestionOrigin.AI_GENERATED)
        )
    ).scalar_one()
    assert questao.status == QuestionStatus.DRAFT
    assert questao.topic_id == topic.id
    assert questao.exam_board_id is None
    assert questao.year is None
    assert aula.title in (questao.source_note or "")


async def test_when_nothing_survives_the_check_the_step_says_so(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    nada_passa_provider: FakeProvider,
) -> None:
    """Zero questão aprovada não é sucesso silencioso nem falha de código."""
    admin = await create_admin(client, emails, email="bm4@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    competition, topic = await _programme(db_session, slug="bm4")
    await _lesson(db_session, admin, topic, status=TrainingStatus.PUBLISHED)
    plano = await _confirmed_plan(client, admin, competition)

    passo = await _run_battle_master(client, admin, db_session, competition)

    assert passo["status"] == "DONE"
    assert "sem material conferido ou sem questão aprovada" in passo["detail"]

    detalhe = (
        await client.get(f"/api/v1/admin/generation/{plano}", headers=admin.auth_header)
    ).json()
    item = detalhe["items"][0]
    assert item["status"] == "NO_SOURCE"
    assert "QUOTE_NOT_IN_MATERIAL" in (item["reason"] or "")


async def test_a_topic_already_covered_by_the_bank_is_not_generated_again(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    boa_provider: FakeProvider,
) -> None:
    """O corte é de quem monta o plano: um tópico com questão suficiente é reaproveitado."""
    admin = await create_admin(client, emails, email="bm5@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    competition, topic = await _programme(db_session, slug="bm5")
    await _lesson(db_session, admin, topic, status=TrainingStatus.PUBLISHED)
    for indice in range(2):
        enunciado = f"Questão oficial {indice} de crase já existente no banco de provas."
        db_session.add(
            Question(
                statement=enunciado,
                subject_id=topic.subject_id,
                topic_id=topic.id,
                status=QuestionStatus.PUBLISHED,
                checksum=statement_checksum(enunciado),
            )
        )
    await db_session.commit()

    plano = await _confirmed_plan(client, admin, competition, min_questions_per_topic=2)

    detalhe = (
        await client.get(f"/api/v1/admin/generation/{plano}", headers=admin.auth_header)
    ).json()
    item = detalhe["items"][0]
    assert item["decision"] == "REUSE"
    assert "2 questão(ões) no banco" in item["reason"]

    passo = await _run_battle_master(client, admin, db_session, competition)
    assert passo["status"] == "DONE"
    assert boa_provider.completion_calls == [], "tópico coberto não gasta token"
