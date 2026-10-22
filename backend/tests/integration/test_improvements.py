"""Analista de melhorias (Agente 8), ponta a ponta.

Dois testes sustentam a fase. O primeiro é
``test_a_detector_without_sample_closes_nothing``: um detector que não pôde
rodar **não fecha** achado antigo, porque ausência de medição não é ausência de
problema — fechar ali esconderia o problema junto com a lacuna. O segundo é
``test_nobody_can_declare_a_finding_resolved``: só o detector fecha, quando
deixa de achar.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Competition, Organization, Subject, Topic
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.question import Alternative, Question, QuestionAttempt
from app.models.user import User
from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    create_admin,
    create_question,
    create_subject,
    create_user,
)

BASE = "/api/v1/admin/improvements"
ENUNCIADO = "Segundo o Código Penal, o homicídio praticado por motivo fútil é classificado como"


async def _user_row(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def _run(client: AsyncClient, admin: RegisteredUser) -> dict[str, Any]:
    resposta = await client.post(f"{BASE}/run", headers=admin.auth_header)
    assert resposta.status_code == 200, resposta.text
    return dict(resposta.json())


async def _findings(
    client: AsyncClient, admin: RegisteredUser, **params: str
) -> list[dict[str, Any]]:
    consulta = "&".join(f"{chave}={valor}" for chave, valor in params.items())
    url = f"{BASE}/findings" + (f"?{consulta}" if consulta else "")
    resposta = await client.get(url, headers=admin.auth_header)
    assert resposta.status_code == 200, resposta.text
    return list(resposta.json())


def _detector(report: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in report["detectors"] if item["key"] == key)


async def _answered_question(
    client: AsyncClient,
    admin: RegisteredUser,
    session: AsyncSession,
    *,
    email: str,
    attempts: int = 40,
    correct: int = 2,
    statement: str = ENUNCIADO,
) -> str:
    """Questão publicada com respostas reais, a maioria errada.

    As respostas são gravadas direto porque o detector lê ``question_attempts``;
    passar pelo fluxo de prática exigiria um simulado inteiro para cada questão.
    """
    await create_subject(client, admin, name="Direito Penal")
    criada = await create_question(client, admin, statement=statement)
    user = await _user_row(session, email)
    questao = (
        await session.execute(select(Question).where(Question.public_id == criada["public_id"]))
    ).scalar_one()
    letras = {
        linha.letter: linha
        for linha in (
            await session.execute(select(Alternative).where(Alternative.question_id == questao.id))
        )
        .scalars()
        .all()
    }
    certa = next(item for item in letras.values() if item.is_correct)
    errada = next(item for item in letras.values() if not item.is_correct)

    for indice in range(attempts):
        acertou = indice < correct
        escolhida = certa if acertou else errada
        session.add(
            QuestionAttempt(
                user_id=user.id,
                question_id=questao.id,
                selected_alternative_id=escolhida.id,
                selected_letter=escolhida.letter,
                is_correct=acertou,
                is_blank=False,
                subject_id=questao.subject_id,
                created_at=datetime.now(UTC),
            )
        )
    await session.commit()
    return str(criada["public_id"])


# --------------------------------------------------------------------------- #
# Acesso
# --------------------------------------------------------------------------- #
async def test_a_student_cannot_see_or_run_the_analyst(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="mel1@exemplo.com.br")

    assert (await client.get(f"{BASE}/findings", headers=student.auth_header)).status_code == 403
    assert (await client.post(f"{BASE}/run", headers=student.auth_header)).status_code == 403
    assert (await client.get(f"{BASE}/detectors", headers=student.auth_header)).status_code == 403


# --------------------------------------------------------------------------- #
# Instalação vazia
# --------------------------------------------------------------------------- #
async def test_on_an_empty_install_every_detector_says_what_it_lacks(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Silêncio não é resultado: cada detector declara o que faltou."""
    admin = await create_admin(client, emails, email="mel2@exemplo.com.br")

    relatorio = await _run(client, admin)

    assert relatorio["opened"] == 0
    assert len(relatorio["detectors"]) == 4
    for item in relatorio["detectors"]:
        assert item["status"] == "NOT_ENOUGH_DATA"
        assert item["detail"], f"{item['key']} precisa dizer o que faltou"


async def test_without_a_restricted_credential_the_report_says_so(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """ "Isolado" e "isolado só no código" não são a mesma coisa."""
    admin = await create_admin(client, emails, email="mel3@exemplo.com.br")

    relatorio = await _run(client, admin)

    assert relatorio["isolation"] == "CODE_ONLY"


async def test_the_detector_sheet_shows_the_last_pass(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="mel4@exemplo.com.br")
    await _run(client, admin)

    fichas = (await client.get(f"{BASE}/detectors", headers=admin.auth_header)).json()

    assert len(fichas) == 4
    for ficha in fichas:
        assert ficha["last_status"] == "NOT_ENOUGH_DATA"
        assert ficha["last_run_at"]
        assert ficha["scope"], "detector sem alcance declarado engana quem lê"
        assert ficha["config"]["mute_days"] == 90


# --------------------------------------------------------------------------- #
# Gabarito suspeito
# --------------------------------------------------------------------------- #
async def test_a_question_nobody_gets_right_becomes_a_finding_with_evidence(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel5@exemplo.com.br")
    public_id = await _answered_question(client, admin, db_session, email="mel5@exemplo.com.br")

    relatorio = await _run(client, admin)
    assert _detector(relatorio, "SUSPECT_ANSWER_KEY")["found"] == 1
    assert relatorio["opened"] == 1

    achados = await _findings(client, admin, detector="SUSPECT_ANSWER_KEY")
    achado = achados[0]
    assert achado["severity"] == "HIGH"
    assert achado["destination"] == "ADMIN"
    assert achado["target_public_id"] == public_id
    assert achado["evidence"]["attempts"] == 40
    assert achado["evidence"]["correct"] == 2
    assert achado["evidence"]["chance"] == 0.25
    # A alternativa mais marcada é a evidência mais forte do detector.
    assert achado["evidence"]["most_chosen_count"] == 38
    assert achado["evidence"]["most_chosen_letter"] != achado["evidence"]["answer_letter"]
    # E a proposta é texto, nunca patch.
    assert "Conferir o gabarito" in achado["proposal"]


async def test_a_second_pass_updates_the_finding_instead_of_duplicating_it(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel6@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel6@exemplo.com.br")

    await _run(client, admin)
    segundo = await _run(client, admin)

    assert segundo["opened"] == 0
    assert segundo["updated"] == 1
    achados = await _findings(client, admin, detector="SUSPECT_ANSWER_KEY")
    assert len(achados) == 1
    assert achados[0]["seen_count"] == 2


# --------------------------------------------------------------------------- #
# Decisão humana
# --------------------------------------------------------------------------- #
async def test_rejecting_requires_a_reason(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel7@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel7@exemplo.com.br")
    await _run(client, admin)
    achado = (await _findings(client, admin))[0]

    sem_motivo = await client.patch(
        f"{BASE}/findings/{achado['public_id']}",
        headers=admin.auth_header,
        json={"status": "REJECTED"},
    )
    assert sem_motivo.status_code == 422
    assert sem_motivo.json()["error"]["code"] == "improvement_reason_required"


async def test_nobody_can_declare_a_finding_resolved(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O teste que sustenta a fase.

    Deixar uma pessoa fechar o achado faria o painel mostrar um problema
    resolvido que continua no ar. Só o detector fecha, quando deixa de achar.
    """
    admin = await create_admin(client, emails, email="mel8@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel8@exemplo.com.br")
    await _run(client, admin)
    achado = (await _findings(client, admin))[0]

    resposta = await client.patch(
        f"{BASE}/findings/{achado['public_id']}",
        headers=admin.auth_header,
        json={"status": "RESOLVED"},
    )

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "improvement_status_not_decidable"


async def test_a_rejected_finding_stays_quiet_for_the_declared_window(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Recusar e ser ignorado faria o administrador parar de recusar."""
    admin = await create_admin(client, emails, email="mel9@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel9@exemplo.com.br")
    await _run(client, admin)
    achado = (await _findings(client, admin))[0]

    recusa = await client.patch(
        f"{BASE}/findings/{achado['public_id']}",
        headers=admin.auth_header,
        json={"status": "REJECTED", "reason": "A questão é difícil de propósito."},
    )
    assert recusa.status_code == 200
    assert recusa.json()["muted_until"]

    segundo = await _run(client, admin)
    assert segundo["muted"] == 1
    assert segundo["updated"] == 0
    ainda_recusado = (await _findings(client, admin, status="REJECTED"))[0]
    assert ainda_recusado["decision_reason"] == "A questão é difícil de propósito."


async def test_accepting_keeps_the_finding_open_for_work(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel10@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel10@exemplo.com.br")
    await _run(client, admin)
    achado = (await _findings(client, admin))[0]

    aceito = await client.patch(
        f"{BASE}/findings/{achado['public_id']}",
        headers=admin.auth_header,
        json={"status": "ACCEPTED"},
    )

    assert aceito.status_code == 200
    assert aceito.json()["status"] == "ACCEPTED"
    assert aceito.json()["resolved_at"] is None


# --------------------------------------------------------------------------- #
# Fechamento e reabertura
# --------------------------------------------------------------------------- #
async def test_a_finding_closes_when_the_detector_stops_finding_it(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel11@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel11@exemplo.com.br")
    await _run(client, admin)

    # O gabarito foi corrigido: as respostas passam a acertar.
    tentativas = (await db_session.execute(select(QuestionAttempt))).scalars().all()
    for tentativa in tentativas:
        tentativa.is_correct = True
    await db_session.commit()

    segundo = await _run(client, admin)

    assert segundo["resolved"] == 1
    fechados = await _findings(client, admin, status="RESOLVED")
    assert len(fechados) == 1
    assert fechados[0]["resolved_at"]


async def test_a_problem_that_comes_back_reopens_the_finding(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel12@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel12@exemplo.com.br")
    await _run(client, admin)

    tentativas = (await db_session.execute(select(QuestionAttempt))).scalars().all()
    for tentativa in tentativas:
        tentativa.is_correct = True
    await db_session.commit()
    await _run(client, admin)

    for tentativa in tentativas:
        tentativa.is_correct = False
    await db_session.commit()
    terceiro = await _run(client, admin)

    assert terceiro["reopened"] == 1
    abertos = await _findings(client, admin, status="OPEN")
    assert abertos[0]["reopened_count"] == 1


async def test_a_detector_without_sample_closes_nothing(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """O teste que sustenta a fase.

    Subir a amostra mínima acima do que existe faz o detector parar de poder
    rodar. Fechar o achado antigo ali diria que o problema acabou — quando o que
    acabou foi a capacidade de medi-lo.
    """
    admin = await create_admin(client, emails, email="mel13@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel13@exemplo.com.br")
    await _run(client, admin)
    assert len(await _findings(client, admin, status="OPEN")) == 1

    ajuste = await client.patch(
        f"{BASE}/detectors/SUSPECT_ANSWER_KEY",
        headers=admin.auth_header,
        json={"config": {"min_attempts": 5000}},
    )
    assert ajuste.status_code == 200
    assert ajuste.json()["config"]["min_attempts"] == 5000

    segundo = await _run(client, admin)

    assert _detector(segundo, "SUSPECT_ANSWER_KEY")["status"] == "NOT_ENOUGH_DATA"
    assert segundo["resolved"] == 0
    assert len(await _findings(client, admin, status="OPEN")) == 1


# --------------------------------------------------------------------------- #
# Limiares
# --------------------------------------------------------------------------- #
async def test_an_unknown_threshold_is_refused_with_the_list_of_valid_ones(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="mel14@exemplo.com.br")

    resposta = await client.patch(
        f"{BASE}/detectors/SUSPECT_ANSWER_KEY",
        headers=admin.auth_header,
        json={"config": {"limiar_inventado": 3}},
    )

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "improvement_unknown_threshold"
    assert "min_attempts" in resposta.json()["error"]["details"]["available"]


async def test_a_disabled_detector_does_not_run_and_says_it(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel15@exemplo.com.br")
    await _answered_question(client, admin, db_session, email="mel15@exemplo.com.br")

    await client.patch(
        f"{BASE}/detectors/SUSPECT_ANSWER_KEY",
        headers=admin.auth_header,
        json={"is_enabled": False},
    )
    relatorio = await _run(client, admin)

    assert _detector(relatorio, "SUSPECT_ANSWER_KEY")["status"] == "DISABLED"
    assert relatorio["opened"] == 0


# --------------------------------------------------------------------------- #
# Tópico do edital sem material
# --------------------------------------------------------------------------- #
async def test_a_notice_topic_without_material_is_ranked_by_weight(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    admin = await create_admin(client, emails, email="mel16@exemplo.com.br")

    org = Organization(
        name="Tribunal da Lacuna", slug="tribunal-lacuna", short_name="TL", sphere="FEDERAL"
    )
    db_session.add(org)
    await db_session.flush()
    competition = Competition(
        name="Concurso com Lacuna",
        slug="concurso-lacuna",
        year=2026,
        organization_id=org.id,
        is_published=True,
    )
    subject = Subject(slug="portugues-lacuna", name="Português")
    db_session.add_all([competition, subject])
    await db_session.flush()

    topicos = {}
    for nome in ("Crase", "Regência"):
        topico = Topic(subject_id=subject.id, name=nome, slug=f"{nome.lower()}-lac", depth=0)
        db_session.add(topico)
        await db_session.flush()
        topico.path = str(topico.id)
        topicos[nome] = topico

    notice = Notice(competition_id=competition.id, title="Edital nº 1/2026", kind="MAIN")
    db_session.add(notice)
    await db_session.flush()
    disciplina = NoticeSubject(
        notice_id=notice.id,
        subject_id=subject.id,
        raw_label="Língua Portuguesa",
        weight="3.00",
        questions_count=20,
        order_index=0,
        evidence_level="OFFICIAL",
    )
    db_session.add(disciplina)
    await db_session.flush()
    for indice, nome in enumerate(("Crase", "Regência")):
        db_session.add(
            NoticeTopic(
                notice_subject_id=disciplina.id,
                topic_id=topicos[nome].id,
                raw_label=nome,
                order_index=indice,
            )
        )
    await db_session.commit()

    relatorio = await _run(client, admin)

    assert _detector(relatorio, "TOPIC_WITHOUT_MATERIAL")["found"] == 1
    achado = (await _findings(client, admin, detector="TOPIC_WITHOUT_MATERIAL"))[0]
    assert achado["target_public_id"] == competition.public_id
    assert achado["evidence"]["linked_topics"] == 2
    assert achado["evidence"]["topics_without_material"] == 2
    assert "plano de geração" in achado["proposal"]
