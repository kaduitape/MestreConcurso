"""Retificação de edital, ponta a ponta.

O teste que sustenta a fase é o do conteúdo órfão: quando um tópico sai do
edital, a aula **continua existindo**. Apagar seria a coisa mais fácil de
programar e a mais difícil de desfazer — e um edital retificado pode ser
retificado de novo.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Competition, Organization, Subject, Topic
from app.models.notice import Notice
from app.models.notice_analysis import NoticeEvent, NoticeFact, NoticeSubject, NoticeTopic
from app.models.training import TrainingLesson
from app.models.user import User
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin, create_user


async def _versao(
    session: AsyncSession,
    competition_id: int,
    *,
    titulo: str,
    kind: str,
    subject_id: int,
    topicos: list[tuple[str, int | None]],
    data_prova: date,
    vagas: str,
    nivel_evidencia: str = "OFFICIAL",
    peso: str = "2.00",
) -> Notice:
    """Cria um edital já analisado — o que a comparação consome."""
    notice = Notice(competition_id=competition_id, title=titulo, kind=kind)
    session.add(notice)
    await session.flush()

    disciplina = NoticeSubject(
        notice_id=notice.id,
        subject_id=subject_id,
        raw_label="Português",
        weight=peso,
        questions_count=20,
        order_index=0,
    )
    session.add(disciplina)
    await session.flush()
    for indice, (rotulo, topic_id) in enumerate(topicos):
        session.add(
            NoticeTopic(
                notice_subject_id=disciplina.id,
                topic_id=topic_id,
                raw_label=rotulo,
                order_index=indice,
            )
        )
    session.add(
        NoticeEvent(
            notice_id=notice.id,
            kind="EXAM",
            title="Prova objetiva",
            date_start=data_prova,
            evidence_level=nivel_evidencia,
        )
    )
    session.add(
        NoticeFact(
            notice_id=notice.id,
            field_path="vagas",
            label="Vagas",
            value={"raw": vagas},
            evidence_level="OFFICIAL",
        )
    )
    await session.commit()
    return notice


async def _cenario(
    session: AsyncSession,
    *,
    topicos_depois: list[str] | None = None,
    data_depois: date = date(2026, 6, 21),
    vagas_depois: str = "45",
    nivel_depois: str = "OFFICIAL",
) -> tuple[str, dict[str, int]]:
    org = Organization(
        name="Tribunal da Retificação", slug="tribunal-retif", short_name="TR", sphere="FEDERAL"
    )
    session.add(org)
    await session.flush()
    competition = Competition(
        name="Concurso Retificado", slug="concurso-retif", year=2026, organization_id=org.id
    )
    session.add(competition)
    subject = Subject(slug="portugues-retif", name="Português")
    session.add(subject)
    await session.flush()

    ids: dict[str, int] = {}
    for nome in ("Crase", "Regência", "Concordância"):
        topic = Topic(
            subject_id=subject.id, name=nome, slug=f"{nome.lower()}-retif", path=f"/{nome.lower()}"
        )
        session.add(topic)
        await session.flush()
        ids[nome] = topic.id

    await _versao(
        session,
        competition.id,
        titulo="Edital nº 1/2026",
        kind="MAIN",
        subject_id=subject.id,
        topicos=[("Crase", ids["Crase"]), ("Regência", ids["Regência"])],
        data_prova=date(2026, 5, 10),
        vagas="30",
    )
    nomes = topicos_depois if topicos_depois is not None else ["Crase", "Regência"]
    await _versao(
        session,
        competition.id,
        titulo="Retificação nº 1",
        kind="RECTIFICATION",
        subject_id=subject.id,
        topicos=[(nome, ids[nome]) for nome in nomes],
        data_prova=data_depois,
        vagas=vagas_depois,
        nivel_evidencia=nivel_depois,
    )
    return competition.public_id, ids


async def _comparar(
    client: AsyncClient, admin: RegisteredUser, competition_public_id: str
) -> dict[str, Any]:
    resposta = await client.post(
        "/api/v1/admin/notice-diffs",
        headers=admin.auth_header,
        json={"competition_public_id": competition_public_id},
    )
    assert resposta.status_code == 201, resposta.text
    return dict(resposta.json())


# --------------------------------------------------------------------------- #
# A comparação
# --------------------------------------------------------------------------- #
async def test_the_moved_exam_date_shows_both_sides(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ret1@exemplo.com.br")
    competition, _ = await _cenario(db_session)

    corpo = await _comparar(client, admin, competition)

    data = next(item for item in corpo["changes"] if item["scope"] == "EVENT")
    assert data["kind"] == "CHANGED"
    assert data["before"] == "10/05/2026"
    assert data["after"] == "21/06/2026"


def _mudanca(corpo: dict[str, Any], scope: str, label: str) -> dict[str, Any]:
    return next(
        item for item in corpo["changes"] if item["scope"] == scope and item["label"] == label
    )


async def test_a_changed_fact_is_reported_with_both_values(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ret2@exemplo.com.br")
    competition, _ = await _cenario(db_session)

    corpo = await _comparar(client, admin, competition)

    vagas = _mudanca(corpo, "FACT", "Vagas")
    assert (vagas["before"], vagas["after"]) == ("30", "45")


async def test_a_new_topic_appears_as_added(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ret3@exemplo.com.br")
    competition, _ = await _cenario(
        db_session, topicos_depois=["Crase", "Regência", "Concordância"]
    )

    corpo = await _comparar(client, admin, competition)

    novo = _mudanca(corpo, "TOPIC", "Concordância")
    assert novo["kind"] == "ADDED"
    assert corpo["summary"]["missing"] == 1


async def test_the_evidence_level_reaches_the_screen(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Data conferida no PDF e data deduzida não podem chegar iguais."""
    admin = await create_admin(client, emails, email="ret4@exemplo.com.br")
    competition, _ = await _cenario(db_session, nivel_depois="INFERRED")

    corpo = await _comparar(client, admin, competition)

    data = next(item for item in corpo["changes"] if item["scope"] == "EVENT")
    assert data["evidence_level"] == "INFERRED"
    assert corpo["summary"]["inferred"] == 1


# --------------------------------------------------------------------------- #
# O impacto — e a regra de não apagar nada
# --------------------------------------------------------------------------- #
async def test_content_of_a_removed_topic_survives_as_orphaned(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O teste que sustenta a fase."""
    admin = await create_admin(client, emails, email="ret5@exemplo.com.br")
    competition, ids = await _cenario(db_session, topicos_depois=["Crase"])
    autor = (await db_session.execute(select(User).where(User.email == admin.email))).scalar_one()
    db_session.add(
        TrainingLesson(
            created_by_user_id=autor.id,
            title="Regência sem mistério",
            subject="Português",
            topic="Regência",
            topic_id=ids["Regência"],
            character_name="Mestre",
            status="PUBLISHED",
        )
    )
    await db_session.commit()

    corpo = await _comparar(client, admin, competition)

    orfao = next(item for item in corpo["impacts"] if item["action"] == "ORPHANED")
    assert orfao["content"]["public_id"]
    assert "quem decide o destino" in orfao["reason"]
    assert corpo["summary"]["orphaned"] == 1

    # E a aula continua lá, publicada.
    aula = (
        await db_session.execute(
            select(TrainingLesson).where(TrainingLesson.topic_id == ids["Regência"])
        )
    ).scalar_one()
    assert aula.status == "PUBLISHED"


async def test_a_new_topic_that_already_has_content_is_not_reported_as_missing(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ret6@exemplo.com.br")
    competition, ids = await _cenario(
        db_session, topicos_depois=["Crase", "Regência", "Concordância"]
    )
    autor = (await db_session.execute(select(User).where(User.email == admin.email))).scalar_one()
    db_session.add(
        TrainingLesson(
            created_by_user_id=autor.id,
            title="Concordância",
            subject="Português",
            topic="Concordância",
            topic_id=ids["Concordância"],
            character_name="Mestre",
            status="DRAFT",
        )
    )
    await db_session.commit()

    corpo = await _comparar(client, admin, competition)

    assert corpo["summary"]["missing"] == 0


# --------------------------------------------------------------------------- #
# Sem o que comparar
# --------------------------------------------------------------------------- #
async def test_a_single_version_cannot_be_compared(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Comparar com o vazio diria que o edital inteiro é novidade."""
    admin = await create_admin(client, emails, email="ret7@exemplo.com.br")
    org = Organization(name="Só um", slug="so-um", short_name="SU", sphere="FEDERAL")
    db_session.add(org)
    await db_session.flush()
    competition = Competition(
        name="Concurso de uma versão", slug="uma-versao", year=2026, organization_id=org.id
    )
    db_session.add(competition)
    subject = Subject(slug="portugues-uma", name="Português")
    db_session.add(subject)
    await db_session.flush()
    await _versao(
        db_session,
        competition.id,
        titulo="Edital único",
        kind="MAIN",
        subject_id=subject.id,
        topicos=[("Crase", None)],
        data_prova=date(2026, 5, 10),
        vagas="30",
    )

    resposta = await client.post(
        "/api/v1/admin/notice-diffs",
        headers=admin.auth_header,
        json={"competition_public_id": competition.public_id},
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["error"]["code"] == "notice_diff_not_enough_versions"


# --------------------------------------------------------------------------- #
# Registro e acesso
# --------------------------------------------------------------------------- #
async def test_a_comparison_can_be_marked_as_read(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ret8@exemplo.com.br")
    competition, _ = await _cenario(db_session)
    corpo = await _comparar(client, admin, competition)

    lida = await client.post(
        f"/api/v1/admin/notice-diffs/{corpo['public_id']}/reviewed", headers=admin.auth_header
    )

    assert lida.status_code == 200, lida.text
    assert lida.json()["reviewed_at"]


async def test_the_comparison_is_listed_for_the_competition(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="ret9@exemplo.com.br")
    competition, _ = await _cenario(db_session)
    await _comparar(client, admin, competition)

    listagem = await client.get(
        f"/api/v1/admin/notice-diffs?competition_public_id={competition}",
        headers=admin.auth_header,
    )

    assert listagem.status_code == 200, listagem.text
    assert listagem.json()["total"] == 1


async def test_a_student_cannot_reach_the_comparison(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    aluno = await create_user(client, emails, email="aluno.ret@exemplo.com.br")

    assert (
        await client.post(
            "/api/v1/admin/notice-diffs",
            headers=aluno.auth_header,
            json={"competition_public_id": "x"},
        )
    ).status_code == 403
