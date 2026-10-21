"""Geração em massa por tópico, ponta a ponta.

Três comportamentos pesam mais que os outros neste arquivo:

* **nada dispara sem confirmação de uma pessoa** — montar o plano mostra a
  estimativa e não gasta um centavo;
* **a estimativa não inventa número** — sem histórico medido, ela diz que não
  dá para estimar;
* **nada é publicado** — o que sai da geração é rascunho esperando revisão, que
  é exatamente o que o portão da Fase 3 exige.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.models.ai import AIUsage
from app.models.catalog import Competition, Organization, Subject, Topic
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.training import TrainingLesson
from app.models.user import User
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin, create_user
from tests.fake_ai import FakeProvider

SCRIPT = {
    "objectives": ["Entender o tópico"],
    "scenes": [
        {"id": 1, "type": "intro", "narration": "Uma frase de abertura da aula.", "duration": 10}
    ],
}


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Troca só o adaptador: o resto do caminho roda de verdade."""
    provider = FakeProvider(completion_payload=SCRIPT)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _competition_with_programme(
    session: AsyncSession, *, topics: tuple[str, ...] = ("Crase", "Regência")
) -> tuple[str, list[int]]:
    """Monta concurso + edital analisado com tópicos ligados ao catálogo."""
    org = Organization(
        name="Tribunal da Geração",
        slug="tribunal-geracao",
        short_name="TG",
        sphere="FEDERAL",
    )
    session.add(org)
    await session.flush()
    competition = Competition(
        name="Concurso da Geração", slug="concurso-geracao", year=2026, organization_id=org.id
    )
    session.add(competition)
    subject = Subject(slug="portugues-geracao", name="Português")
    session.add(subject)
    await session.flush()

    topic_ids: list[int] = []
    for indice, nome in enumerate(topics):
        topic = Topic(
            subject_id=subject.id,
            name=nome,
            slug=f"{nome.lower()}-{indice}",
            path=f"/{nome.lower()}",
        )
        session.add(topic)
        await session.flush()
        topic_ids.append(topic.id)

    notice = Notice(competition_id=competition.id, title="Edital da Geração", kind="MAIN")
    session.add(notice)
    await session.flush()
    notice_subject = NoticeSubject(
        notice_id=notice.id, subject_id=subject.id, raw_label="Português", order_index=0
    )
    session.add(notice_subject)
    await session.flush()
    for indice, topic_id in enumerate(topic_ids):
        session.add(
            NoticeTopic(
                notice_subject_id=notice_subject.id,
                topic_id=topic_id,
                raw_label=topics[indice],
                order_index=indice,
            )
        )
    await session.commit()
    return competition.public_id, topic_ids


async def _create_plan(
    client: AsyncClient, admin: RegisteredUser, competition_public_id: str, **extra: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "competition_public_id": competition_public_id,
        "kinds": ["TRAINING_LESSON"],
    }
    payload.update(extra)
    response = await client.post(
        "/api/v1/admin/generation", headers=admin.auth_header, json=payload
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


# --------------------------------------------------------------------------- #
# Montagem do plano
# --------------------------------------------------------------------------- #
async def test_the_plan_has_one_item_per_topic_and_kind(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ger1@exemplo.com.br")
    competition, _ = await _competition_with_programme(db_session)

    plano = await _create_plan(client, admin, competition, kinds=["TRAINING_LESSON", "MIND_MAP"])

    assert plano["status"] == "DRAFT"
    assert len(plano["items"]) == 4
    assert all(item["reason"] for item in plano["items"]), "decisão sem motivo vira mistério"


async def test_without_an_analysed_notice_there_is_no_plan(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Gerar para um edital que ninguém analisou seria inventar o programa."""
    admin = await create_admin(client, emails, email="ger2@exemplo.com.br")
    org = Organization(name="Sem Edital", slug="sem-edital", short_name="SE", sphere="FEDERAL")
    db_session.add(org)
    await db_session.flush()
    competition = Competition(
        name="Concurso Sem Edital", slug="sem-edital-2026", year=2026, organization_id=org.id
    )
    db_session.add(competition)
    await db_session.commit()

    resposta = await client.post(
        "/api/v1/admin/generation",
        headers=admin.auth_header,
        json={"competition_public_id": competition.public_id, "kinds": ["TRAINING_LESSON"]},
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["error"]["code"] == "generation_no_programme"


async def test_existing_content_is_reused_instead_of_generated_again(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ger3@exemplo.com.br")
    competition, topic_ids = await _competition_with_programme(db_session)
    autor = (await db_session.execute(select(User).where(User.email == admin.email))).scalar_one()
    db_session.add(
        TrainingLesson(
            created_by_user_id=autor.id,
            title="Crase que já existe",
            subject="Português",
            topic="Crase",
            topic_id=topic_ids[0],
            character_name="Mestre",
            status="READY",
        )
    )
    await db_session.commit()

    plano = await _create_plan(client, admin, competition)

    decisoes = {item["topic_name"]: item["decision"] for item in plano["items"]}
    assert decisoes["Crase"] == "REUSE"
    assert decisoes["Regência"] == "GENERATE"


# --------------------------------------------------------------------------- #
# A estimativa
# --------------------------------------------------------------------------- #
async def test_without_measured_history_there_is_no_estimate(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O teste que sustenta a fase: chute sobre centenas de tópicos vira fatura."""
    admin = await create_admin(client, emails, email="ger4@exemplo.com.br")
    competition, _ = await _competition_with_programme(db_session)

    plano = await _create_plan(client, admin, competition)

    assert plano["estimate_is_known"] is False
    assert Decimal(plano["estimate_cents"]) == Decimal("0")
    assert plano["estimate_basis"]["unknown_features"] == ["training.script"]


async def test_the_estimate_comes_from_the_measured_median(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ger5@exemplo.com.br")
    competition, _ = await _competition_with_programme(db_session)
    for custo in ("10", "12", "14", "900"):
        db_session.add(
            AIUsage(
                feature="training.script",
                provider_slug="openai",
                model_slug="gpt-4o-mini",
                input_tokens=100,
                output_tokens=200,
                cost_cents=Decimal(custo),
                status="SUCCESS",
                cached=False,
            )
        )
    await db_session.commit()

    plano = await _create_plan(client, admin, competition)

    assert plano["estimate_is_known"] is True
    # Mediana de 10, 12, 14 e 900 é 13 — o estouro isolado não move o número.
    assert Decimal(plano["estimate_cents"]) == Decimal("26")
    assert plano["estimate_basis"]["features"]["training.script"]["samples"] == 4


async def test_cached_and_unpriced_calls_do_not_enter_the_median(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Custo zero aqui é modelo sem preço; contá-lo faria a estimativa prometer barato."""
    admin = await create_admin(client, emails, email="ger6@exemplo.com.br")
    competition, _ = await _competition_with_programme(db_session)
    for custo, cached in ((Decimal("0"), False), (Decimal("50"), True), (Decimal("20"), False)):
        db_session.add(
            AIUsage(
                feature="training.script",
                provider_slug="openai",
                model_slug="gpt-4o-mini",
                cost_cents=custo,
                status="SUCCESS",
                cached=cached,
            )
        )
    await db_session.commit()

    plano = await _create_plan(client, admin, competition)

    # Sobrou uma amostra só: abaixo do mínimo, então não há estimativa.
    assert plano["estimate_is_known"] is False
    assert plano["estimate_basis"]["features"]["training.script"]["samples"] == 1


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #
async def test_nothing_is_generated_before_a_person_confirms(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="ger7@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    competition, _ = await _competition_with_programme(db_session)

    await _create_plan(client, admin, competition)

    assert fake_provider.completion_calls == [], "montar o plano não pode gastar token"


async def _run_plan(db_session: AsyncSession, admin: RegisteredUser, public_id: str) -> None:
    """Roda a passada como o worker rodaria.

    Em produção quem chama é a tarefa Celery; aqui ela é chamada direto porque
    o laço de eventos do teste não comporta o ``asyncio.run`` da tarefa. O
    caminho exercitado é o mesmo: serviço, geração e gravação.
    """
    from app.services.auth import RequestContext
    from app.services.generation import GenerationService

    service = GenerationService(db_session)
    plan = await service.get(public_id)
    actor = (await db_session.execute(select(User).where(User.email == admin.email))).scalar_one()
    while True:
        resultado = await service.run(plan, actor, RequestContext())
        if resultado.remaining == 0:
            break
        plan = await service.get(public_id)


async def test_confirming_asks_the_worker_to_run(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirmar é o único ponto onde a geração começa a gastar."""
    admin = await create_admin(client, emails, email="ger12@exemplo.com.br")
    competition, _ = await _competition_with_programme(db_session)
    plano = await _create_plan(client, admin, competition)

    despachos: list[dict[str, Any]] = []
    from app.workers.tasks import generation as tarefa

    monkeypatch.setattr(
        tarefa.run_generation_plan_task,
        "apply_async",
        lambda **kwargs: despachos.append(kwargs),
    )

    confirmado = await client.post(
        f"/api/v1/admin/generation/{plano['public_id']}/confirm", headers=admin.auth_header
    )

    assert confirmado.status_code == 200, confirmado.text
    assert confirmado.json()["status"] == "CONFIRMED"
    assert despachos[0]["kwargs"] == {"plan_public_id": plano["public_id"]}


async def test_the_run_generates_drafts_and_publishes_nothing(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    """O portão da Fase 3 barra conteúdo de IA sem conferência humana — e isso é o desenho."""
    admin = await create_admin(client, emails, email="ger8@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    competition, topic_ids = await _competition_with_programme(db_session)
    plano = await _create_plan(client, admin, competition)
    await client.post(
        f"/api/v1/admin/generation/{plano['public_id']}/confirm", headers=admin.auth_header
    )

    await _run_plan(db_session, admin, plano["public_id"])

    final = (
        await client.get(
            f"/api/v1/admin/generation/{plano['public_id']}", headers=admin.auth_header
        )
    ).json()
    assert final["progress"]["done"] == 2
    assert final["status"] == "DONE"

    aulas = (
        (
            await db_session.execute(
                select(TrainingLesson).where(TrainingLesson.topic_id.in_(topic_ids))
            )
        )
        .scalars()
        .all()
    )
    assert len(aulas) == 2
    for aula in aulas:
        assert aula.status == "READY", "geração em massa não publica"
        assert aula.published_at is None
        assert aula.topic_id in topic_ids, "sem vínculo, a próxima passada geraria de novo"


async def test_running_again_does_not_redo_what_is_done(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    admin = await create_admin(client, emails, email="ger9@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    competition, _ = await _competition_with_programme(db_session)
    plano = await _create_plan(client, admin, competition)

    await client.post(
        f"/api/v1/admin/generation/{plano['public_id']}/confirm", headers=admin.auth_header
    )
    await _run_plan(db_session, admin, plano["public_id"])
    chamadas = len(fake_provider.completion_calls)

    await _run_plan(db_session, admin, plano["public_id"])

    assert len(fake_provider.completion_calls) == chamadas, "retomar não paga de novo"


async def test_a_second_plan_reuses_what_the_first_generated(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    fake_provider: FakeProvider,
) -> None:
    """É o reaproveitamento de verdade: o vínculo com o tópico atravessa planos."""
    admin = await create_admin(client, emails, email="ger10@exemplo.com.br")
    await configure_ai(client, admin, features=("training.script",))
    competition, _ = await _competition_with_programme(db_session)
    primeiro = await _create_plan(client, admin, competition)
    await client.post(
        f"/api/v1/admin/generation/{primeiro['public_id']}/confirm", headers=admin.auth_header
    )
    await _run_plan(db_session, admin, primeiro["public_id"])

    segundo = await _create_plan(client, admin, competition)

    assert {item["decision"] for item in segundo["items"]} == {"REUSE"}
    assert Decimal(segundo["estimate_cents"]) == Decimal("0")


async def test_a_canceled_plan_does_not_run(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ger11@exemplo.com.br")
    competition, _ = await _competition_with_programme(db_session)
    plano = await _create_plan(client, admin, competition)

    cancelado = await client.post(
        f"/api/v1/admin/generation/{plano['public_id']}/cancel", headers=admin.auth_header
    )

    assert cancelado.status_code == 200, cancelado.text
    assert cancelado.json()["status"] == "CANCELED"
    assert all(item["status"] == "CANCELED" for item in cancelado.json()["items"])


# --------------------------------------------------------------------------- #
# Acesso
# --------------------------------------------------------------------------- #
async def test_a_student_cannot_reach_generation(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    aluno = await create_user(client, emails, email="aluno.ger@exemplo.com.br")

    assert (
        await client.post(
            "/api/v1/admin/generation",
            headers=aluno.auth_header,
            json={"competition_public_id": "x", "kinds": ["TRAINING_LESSON"]},
        )
    ).status_code == 403
