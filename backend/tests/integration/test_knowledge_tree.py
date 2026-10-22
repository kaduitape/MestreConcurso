"""Árvore de conhecimento, ponta a ponta.

Os dois testes que sustentam a fase: o tópico do edital **sem vínculo** com o
catálogo aparece declarado como não medido e **fora da média da disciplina**; e
a resposta dada num subtópico conta para o ramo do edital que o contém — é o
que faz a árvore descrever o edital e não o nosso catálogo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Competition, Organization, Subject, Topic
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.question import Question, QuestionAttempt, QuestionStatus
from app.models.training import TrainingLesson, TrainingProgress, TrainingProgressStatus
from app.models.user import User
from app.services.question_bank import statement_checksum
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_user

TREE_URL = "/api/v1/game/knowledge-tree"


async def _user_row(session: AsyncSession, email: str) -> User:
    from sqlalchemy import select

    found = (await session.execute(select(User).where(User.email == email))).scalar_one()
    return found


async def _catalogo(session: AsyncSession) -> tuple[Competition, Subject, dict[str, Topic]]:
    org = Organization(
        name="Tribunal da Árvore", slug="tribunal-arvore", short_name="TA", sphere="FEDERAL"
    )
    session.add(org)
    await session.flush()
    competition = Competition(
        name="Concurso da Árvore",
        slug="concurso-arvore",
        year=2026,
        organization_id=org.id,
        is_published=True,
    )
    subject = Subject(slug="portugues-arvore", name="Português")
    session.add_all([competition, subject])
    await session.flush()

    topicos: dict[str, Topic] = {}
    # O caminho materializado é montado como o serviço de catálogo monta:
    # a raiz é o próprio id, o filho é "<pai>/<id>". Testar com outro formato
    # exercitaria um prefixo que a produção não tem.
    crase = Topic(subject_id=subject.id, name="Crase", slug="crase-arv", depth=0)
    session.add(crase)
    await session.flush()
    crase.path = str(crase.id)
    topicos["Crase"] = crase

    # Um subtópico de verdade: é ele que prova a soma por subárvore.
    filho = Topic(
        subject_id=subject.id,
        parent_id=crase.id,
        name="Crase antes de pronome",
        slug="crase-pronome-arv",
        depth=1,
    )
    session.add(filho)
    await session.flush()
    filho.path = f"{crase.path}/{filho.id}"
    topicos["Crase · pronome"] = filho

    regencia = Topic(subject_id=subject.id, name="Regência", slug="regencia-arv", depth=0)
    session.add(regencia)
    await session.flush()
    regencia.path = str(regencia.id)
    topicos["Regência"] = regencia
    await session.commit()
    return competition, subject, topicos


async def _edital(
    session: AsyncSession,
    competition: Competition,
    subject: Subject,
    *,
    topicos: list[tuple[str, int | None]],
) -> Notice:
    notice = Notice(competition_id=competition.id, title="Edital nº 1/2026", kind="MAIN")
    session.add(notice)
    await session.flush()
    disciplina = NoticeSubject(
        notice_id=notice.id,
        subject_id=subject.id,
        raw_label="Língua Portuguesa",
        weight="2.00",
        questions_count=20,
        order_index=0,
        evidence_level="OFFICIAL",
        page_number=7,
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
                page_number=8,
            )
        )
    await session.commit()
    return notice


async def _responder(
    session: AsyncSession,
    user: User,
    subject: Subject,
    topic: Topic,
    *,
    acertos: int,
    erros: int,
    dias_atras: int = 1,
) -> None:
    """Grava respostas reais — a árvore não tem contador paralelo para alimentar."""
    quando = datetime.now(UTC) - timedelta(days=dias_atras)
    for indice in range(acertos + erros):
        enunciado = f"Questão {topic.slug} {indice} sobre o assunto cobrado no edital."
        question = Question(
            statement=enunciado,
            subject_id=subject.id,
            topic_id=topic.id,
            status=QuestionStatus.PUBLISHED,
            checksum=statement_checksum(enunciado),
        )
        session.add(question)
        await session.flush()
        session.add(
            QuestionAttempt(
                user_id=user.id,
                question_id=question.id,
                is_correct=indice < acertos,
                is_blank=False,
                subject_id=subject.id,
                created_at=quando,
            )
        )
    await session.commit()


async def _focar(client: AsyncClient, candidato: RegisteredUser, competition: Competition) -> None:
    resposta = await client.put(
        "/api/v1/users/me/focus",
        headers=candidato.auth_header,
        json={"competition_public_id": competition.public_id},
    )
    assert resposta.status_code == 200, resposta.text


# --------------------------------------------------------------------------- #
# Sem base para desenhar
# --------------------------------------------------------------------------- #
async def test_without_a_primary_competition_the_tree_says_why(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    candidato = await create_user(client, emails, email="arv1@exemplo.com.br")

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()

    assert corpo["subjects"] == []
    assert "concurso principal" in corpo["unavailable_reason"]


async def test_without_an_analysed_notice_the_tree_refuses_to_draw(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """A árvore é o conteúdo programático do edital. Sem análise, não há fonte."""
    candidato = await create_user(client, emails, email="arv2@exemplo.com.br")
    competition, _, _ = await _catalogo(db_session)
    await _focar(client, candidato, competition)

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()

    assert corpo["competition_name"] == "Concurso da Árvore"
    assert corpo["subjects"] == []
    assert "ainda não foi analisado" in corpo["unavailable_reason"]


# --------------------------------------------------------------------------- #
# A árvore desenhada
# --------------------------------------------------------------------------- #
async def test_the_tree_follows_the_notice_and_carries_its_provenance(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    candidato = await create_user(client, emails, email="arv3@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(
        db_session,
        competition,
        subject,
        topicos=[("Crase", topicos["Crase"].id), ("Regência", topicos["Regência"].id)],
    )
    await _focar(client, candidato, competition)

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()

    assert corpo["notice_title"] == "Edital nº 1/2026"
    assert len(corpo["subjects"]) == 1
    disciplina = corpo["subjects"][0]
    # O rótulo é o do edital, não o do catálogo: é do edital que a banca cobra.
    assert disciplina["label"] == "Língua Portuguesa"
    assert disciplina["weight"] == "2.00"
    assert disciplina["evidence_level"] == "OFFICIAL"
    assert [item["label"] for item in disciplina["topics"]] == ["Crase", "Regência"]
    # Sem material cadastrado, os dois tópicos declaram a lacuna da plataforma.
    assert {item["state"] for item in disciplina["topics"]} == {"NO_MATERIAL"}
    assert corpo["summary"]["no_material"] == 2
    assert corpo["summary"]["measurable"] == 0


async def test_an_answer_in_a_child_topic_counts_for_the_notice_branch(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O segundo teste que sustenta a fase.

    O edital diz "Crase"; o catálogo tem "Crase antes de pronome" embaixo. Uma
    resposta no subtópico é uma resposta de crase — e precisa chegar no ramo
    que o candidato vê.
    """
    candidato = await create_user(client, emails, email="arv4@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(db_session, competition, subject, topicos=[("Crase", topicos["Crase"].id)])
    await _focar(client, candidato, competition)
    user = await _user_row(db_session, "arv4@exemplo.com.br")

    await _responder(db_session, user, subject, topicos["Crase · pronome"], acertos=16, erros=4)

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()

    ramo = corpo["subjects"][0]["topics"][0]
    assert ramo["label"] == "Crase"
    assert ramo["evidence"]["answers"] == 20
    assert ramo["accuracy"] == 0.8
    assert ramo["state"] == "MASTERED"
    # O ramo declara quantos subtópicos entraram na conta dele.
    assert ramo["descendants"] == 1


async def test_a_small_sample_shows_what_is_missing_instead_of_a_percentage(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    candidato = await create_user(client, emails, email="arv5@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(db_session, competition, subject, topicos=[("Crase", topicos["Crase"].id)])
    await _focar(client, candidato, competition)
    user = await _user_row(db_session, "arv5@exemplo.com.br")

    await _responder(db_session, user, subject, topicos["Crase"], acertos=3, erros=0)

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()

    ramo = corpo["subjects"][0]["topics"][0]
    assert ramo["state"] == "IN_PROGRESS"
    assert ramo["accuracy"] is None
    assert ramo["evidence"]["answers_missing"] == 9
    assert "faltam 9" in ramo["reason"]


async def test_an_unlinked_notice_topic_is_declared_and_left_out_of_the_average(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O teste que sustenta a fase.

    Contar o tópico sem vínculo como zero acerto faria a disciplina parecer
    pior do que o candidato — atribuindo a ele uma falha de cadastro.
    """
    candidato = await create_user(client, emails, email="arv6@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(
        db_session,
        competition,
        subject,
        topicos=[("Crase", topicos["Crase"].id), ("Colocação pronominal", None)],
    )
    await _focar(client, candidato, competition)
    user = await _user_row(db_session, "arv6@exemplo.com.br")

    await _responder(db_session, user, subject, topicos["Crase"], acertos=18, erros=2)

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()
    disciplina = corpo["subjects"][0]
    sem_vinculo = disciplina["topics"][1]

    assert sem_vinculo["state"] == "NOT_LINKED"
    assert "não foi vinculado ao catálogo" in sem_vinculo["reason"]
    # A disciplina continua com 90%: o tópico não medido não entrou na conta.
    assert disciplina["accuracy"] == 0.9
    assert disciplina["evidence"]["answers"] == 20
    assert corpo["summary"]["not_linked"] == 1
    assert corpo["summary"]["measurable"] == 1


async def test_available_material_without_activity_is_not_started(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    candidato = await create_user(client, emails, email="arv7@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(db_session, competition, subject, topicos=[("Crase", topicos["Crase"].id)])
    await _focar(client, candidato, competition)

    autor = await _user_row(db_session, "arv7@exemplo.com.br")
    aula = TrainingLesson(
        created_by_user_id=autor.id,
        title="Crase sem decoreba",
        character_name="Mestre",
        subject="Português",
        topic="Crase",
        subject_id=subject.id,
        topic_id=topicos["Crase"].id,
        status="READY",
    )
    db_session.add(aula)
    await db_session.commit()

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()
    ramo = corpo["subjects"][0]["topics"][0]

    assert ramo["state"] == "NOT_STARTED"
    assert ramo["evidence"]["lessons_available"] == 1
    assert ramo["evidence"]["lessons_done"] == 0
    assert corpo["summary"]["not_started"] == 1


async def test_a_finished_lesson_counts_as_activity(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    candidato = await create_user(client, emails, email="arv8@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(db_session, competition, subject, topicos=[("Crase", topicos["Crase"].id)])
    await _focar(client, candidato, competition)
    user = await _user_row(db_session, "arv8@exemplo.com.br")

    aula = TrainingLesson(
        created_by_user_id=user.id,
        title="Crase sem decoreba",
        character_name="Mestre",
        subject="Português",
        topic="Crase",
        subject_id=subject.id,
        topic_id=topicos["Crase"].id,
        status="READY",
    )
    db_session.add(aula)
    await db_session.flush()
    agora = datetime.now(UTC)
    db_session.add(
        TrainingProgress(
            user_id=user.id,
            lesson_id=aula.id,
            status=TrainingProgressStatus.COMPLETED,
            started_at=agora,
            last_seen_at=agora,
            completed_at=agora,
        )
    )
    await db_session.commit()

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()
    ramo = corpo["subjects"][0]["topics"][0]

    # Tocou no assunto, mas não há resposta para medir: em andamento, e o
    # motivo diz quantas respostas faltam.
    assert ramo["state"] == "IN_PROGRESS"
    assert ramo["evidence"]["lessons_done"] == 1


async def test_the_attention_list_leaves_platform_gaps_out(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    candidato = await create_user(client, emails, email="arv9@exemplo.com.br")
    competition, subject, topicos = await _catalogo(db_session)
    await _edital(
        db_session,
        competition,
        subject,
        topicos=[("Crase", topicos["Crase"].id), ("Colocação pronominal", None)],
    )
    await _focar(client, candidato, competition)
    user = await _user_row(db_session, "arv9@exemplo.com.br")

    await _responder(db_session, user, subject, topicos["Crase"], acertos=8, erros=12)

    corpo = (await client.get(TREE_URL, headers=candidato.auth_header)).json()

    assert corpo["subjects"][0]["topics"][0]["state"] == "MEASURED"
    assert corpo["attention"] == ["Crase"]
