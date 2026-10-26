"""Cadastro de concurso a partir de uma URL, do endereço ao botão.

A rede é a única coisa dublada: o resto do caminho é o de produção — o edital é
criado, o PDF é guardado com checksum, o pipeline da Fase 3 roda e confere cada
citação no texto do documento, e a proposta só vira cadastro quando alguém
aplica.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials
from app.models.catalog import Competition, Position, PositionSubject
from app.models.notice import Notice
from app.models.notice_analysis import EvidenceLevel, NoticePosition
from app.services import intake as intake_service
from app.services.web_fetch import FetchedResource, FetchRefusedError
from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    configure_ai,
    create_admin,
    create_subject,
    create_user,
)
from tests.fake_ai import EXTRACTION_MULTICARGO, EXTRACTION_PAYLOAD, FakeProvider
from tests.pdf_fixtures import EDITAL_MULTICARGO_PAGES, build_edital_pdf

PAGINA_DO_CONCURSO = """
<html><body>
  <a href="/arquivos/edital-de-abertura-01-2026.pdf">Edital de Abertura nº 1/2026</a>
  <a href="/arquivos/anexo-ii.pdf">Anexo II</a>
</body></html>
"""

PAGINA_AMBIGUA = """
<html><body>
  <a href="/arquivos/edital-1-2026.pdf">Edital nº 1/2026</a>
  <a href="/arquivos/edital-2-2026.pdf">Edital nº 2/2026</a>
</body></html>
"""

URL_DA_PAGINA = "https://orgao.gov.br/concursos/agente"
URL_DO_PDF = "https://orgao.gov.br/arquivos/edital-de-abertura-01-2026.pdf"


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=EXTRACTION_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


def _rede(monkeypatch: pytest.MonkeyPatch, respostas: dict[str, FetchedResource]) -> list[str]:
    """Substitui só a busca na rede e registra os endereços pedidos."""
    pedidos: list[str] = []

    async def fake_fetch(url: str, *, max_bytes: int = 0) -> FetchedResource:
        pedidos.append(url)
        if url not in respostas:
            raise FetchRefusedError(f"O site respondeu 404 para este endereço. ({url})")
        return respostas[url]

    monkeypatch.setattr(intake_service, "fetch", fake_fetch)
    return pedidos


def _pagina(html: str, url: str = URL_DA_PAGINA) -> FetchedResource:
    return FetchedResource(
        url=url, final_url=url, content_type="text/html; charset=utf-8", content=html.encode()
    )


def _pdf(url: str = URL_DO_PDF) -> FetchedResource:
    return FetchedResource(
        url=url, final_url=url, content_type="application/pdf", content=build_edital_pdf()
    )


# --------------------------------------------------------------------------- #
# O caminho inteiro
# --------------------------------------------------------------------------- #
async def test_uma_url_vira_proposta_de_cadastro_com_citacao_por_campo(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="intake1@exemplo.com.br")
    await configure_ai(client, admin)
    pedidos = _rede(
        monkeypatch,
        {URL_DA_PAGINA: _pagina(PAGINA_DO_CONCURSO), URL_DO_PDF: _pdf()},
    )

    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": URL_DA_PAGINA, "auto_apply": False},
    )
    assert criado.status_code == 201, criado.text
    corpo = criado.json()

    assert corpo["status"] == "AWAITING_REVIEW"
    assert corpo["detail"] is None
    # Buscou a página e, depois de escolher, o PDF — nessa ordem.
    assert pedidos == [URL_DA_PAGINA, URL_DO_PDF]

    # A escolha do PDF é explicada, e o anexo foi pontuado e descartado.
    assert corpo["chosen_url"] == URL_DO_PDF
    assert "edital de abertura" in corpo["choice_reason"]
    por_arquivo = {item["url"].rsplit("/", 1)[-1]: item for item in corpo["candidates"]}
    assert (
        por_arquivo["anexo-ii.pdf"]["score"]
        < por_arquivo["edital-de-abertura-01-2026.pdf"]["score"]
    )
    assert "anexo" in por_arquivo["anexo-ii.pdf"]["explanation"]

    # O edital existe de verdade, com o PDF guardado.
    assert corpo["notice_public_id"]
    edital = await client.get(
        f"/api/v1/admin/notices/{corpo['notice_public_id']}", headers=admin.auth_header
    )
    assert edital.status_code == 200
    assert edital.json()["files"][0]["checksum_sha256"]

    # Nada foi cadastrado ainda: a proposta é rascunho.
    assert corpo["competition_public_id"] is None

    campos = {item["field_path"]: item for item in corpo["proposal"]["fields"]}
    salario = campos["position.salary_cents"]
    assert salario["evidence_level"] == EvidenceLevel.OFFICIAL
    assert "8.157,00" in salario["quote"]
    assert salario["page_number"] == 1
    assert salario["target"] == "salary_max_cents"
    assert salario["applicable"] is True


async def test_campo_sem_citacao_conferida_chega_em_branco_para_alguem_digitar(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O que a IA deduziu não é aplicado sozinho — aplicar é assinar."""
    admin = await create_admin(client, emails, email="intake2@exemplo.com.br")
    await configure_ai(client, admin)
    _rede(monkeypatch, {URL_DO_PDF: _pdf()})

    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": URL_DO_PDF, "auto_apply": False},
    )
    assert criado.status_code == 201, criado.text
    corpo = criado.json()
    # O endereço já era o PDF: não houve o que escolher, e o serviço diz isso.
    assert corpo["candidates"] == []
    assert corpo["choice_reason"] == "o endereço informado já é o PDF do edital"

    campos = {item["field_path"]: item for item in corpo["proposal"]["fields"]}
    inferido = campos["exam.min_score_rule"]
    assert inferido["evidence_level"] == EvidenceLevel.INFERRED
    assert inferido["applicable"] is False

    assert corpo["proposal"]["needs_typing"] >= 1
    assert corpo["proposal"]["applicable"] + corpo["proposal"]["needs_typing"] == len(campos)


async def test_aplicar_cadastra_o_concurso_e_vincula_o_edital(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
) -> None:
    admin = await create_admin(client, emails, email="intake3@exemplo.com.br")
    await configure_ai(client, admin)
    _rede(monkeypatch, {URL_DO_PDF: _pdf()})

    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": URL_DO_PDF, "auto_apply": False},
    )
    intake_id = criado.json()["public_id"]
    campos = {item["field_path"]: item for item in criado.json()["proposal"]["fields"]}

    aplicado = await client.post(
        f"/api/v1/admin/competition-intakes/{intake_id}/apply",
        headers=admin.auth_header,
        json={
            "name": campos["competition.name"]["value"],
            "year": 2026,
            "organization_name": campos["organization.name"]["value"],
            "organization_short_name": "PCDF",
            "fields": {
                "salary_max_cents": campos["position.salary_cents"]["value"],
                "vacancies_total": campos["position.vacancies"]["value"],
                "registration_start": campos["registration.start_date"]["value"],
                "exam_date": campos["exam.date"]["value"],
            },
        },
    )
    assert aplicado.status_code == 200, aplicado.text
    concurso = aplicado.json()
    assert concurso["name"] == campos["competition.name"]["value"]
    assert concurso["salary_max_cents"] == 815700
    assert concurso["vacancies_total"] == 1200
    assert concurso["source_url"] == URL_DO_PDF
    # Cadastro novo não vai ao ar sozinho.
    assert concurso["is_published"] is False

    detalhe = await client.get(
        f"/api/v1/admin/competition-intakes/{intake_id}", headers=admin.auth_header
    )
    assert detalhe.json()["status"] == "APPLIED"
    assert detalhe.json()["competition_public_id"] == concurso["public_id"]

    # O edital passou a pertencer ao concurso: é o vínculo que faz o
    # conteúdo programático já analisado encontrar o concurso novo.
    edital = (
        await db_session.execute(
            select(Notice).where(Notice.public_id == detalhe.json()["notice_public_id"])
        )
    ).scalar_one()
    competicao = (
        await db_session.execute(
            select(Competition).where(Competition.public_id == concurso["public_id"])
        )
    ).scalar_one()
    assert edital.competition_id == competicao.id


async def test_aplicar_duas_vezes_e_conflito(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="intake4@exemplo.com.br")
    await configure_ai(client, admin)
    _rede(monkeypatch, {URL_DO_PDF: _pdf()})

    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": URL_DO_PDF, "auto_apply": False},
    )
    assert criado.status_code == 201, criado.text
    assert criado.json()["status"] == "AWAITING_REVIEW", criado.text
    intake_id = criado.json()["public_id"]
    corpo = {
        "name": "Concurso PCDF Agente 2026",
        "year": 2026,
        "organization_name": "Polícia Civil do Distrito Federal",
        "organization_short_name": "PCDF",
        "fields": {},
    }
    primeiro = await client.post(
        f"/api/v1/admin/competition-intakes/{intake_id}/apply",
        headers=admin.auth_header,
        json=corpo,
    )
    assert primeiro.status_code == 200, primeiro.text

    segundo = await client.post(
        f"/api/v1/admin/competition-intakes/{intake_id}/apply",
        headers=admin.auth_header,
        json=corpo,
    )
    assert segundo.status_code == 409
    assert segundo.json()["error"]["code"] == "intake_not_ready"


# --------------------------------------------------------------------------- #
# As recusas
# --------------------------------------------------------------------------- #
async def test_quando_dois_pdfs_empatam_o_servico_para_e_pede_que_alguem_aponte(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="intake5@exemplo.com.br")
    await configure_ai(client, admin)
    escolhido = "https://orgao.gov.br/arquivos/edital-1-2026.pdf"
    _rede(
        monkeypatch,
        {URL_DA_PAGINA: _pagina(PAGINA_AMBIGUA), escolhido: _pdf(escolhido)},
    )

    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": URL_DA_PAGINA, "auto_apply": False},
    )
    assert criado.status_code == 201, criado.text
    corpo = criado.json()
    assert corpo["status"] == "AWAITING_CHOICE"
    assert "aponte qual" in corpo["detail"]
    # Recusar não é esconder: os dois candidatos estão listados com a nota.
    assert len(corpo["candidates"]) == 2
    assert corpo["notice_public_id"] is None

    escolha = await client.post(
        f"/api/v1/admin/competition-intakes/{corpo['public_id']}/choose",
        headers=admin.auth_header,
        json={"url": escolhido, "auto_apply": False},
    )
    assert escolha.status_code == 200, escolha.text
    assert escolha.json()["status"] == "AWAITING_REVIEW"
    assert escolha.json()["chosen_url"] == escolhido
    assert escolha.json()["choice_reason"] == "endereço apontado por uma pessoa"


async def test_endereco_interno_e_recusado_antes_de_gravar_qualquer_coisa(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intake6@exemplo.com.br")
    recusado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert recusado.status_code == 422, recusado.text
    assert recusado.json()["error"]["code"] == "intake_fetch_refused"

    listagem = await client.get("/api/v1/admin/competition-intakes", headers=admin.auth_header)
    assert listagem.json()["total"] == 0


async def test_site_fora_do_ar_fica_registrado_com_o_motivo(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="intake7@exemplo.com.br")
    _rede(monkeypatch, {})

    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": "https://orgao.gov.br/sumiu"},
    )
    assert criado.status_code == 201, criado.text
    assert criado.json()["status"] == "FAILED"
    assert "404" in criado.json()["detail"]


async def test_descartar_exige_motivo(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="intake8@exemplo.com.br")
    await configure_ai(client, admin)
    _rede(monkeypatch, {URL_DO_PDF: _pdf()})
    criado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=admin.auth_header,
        json={"url": URL_DO_PDF, "auto_apply": False},
    )
    intake_id = criado.json()["public_id"]

    sem_motivo = await client.post(
        f"/api/v1/admin/competition-intakes/{intake_id}/reject",
        headers=admin.auth_header,
        json={"reason": ""},
    )
    assert sem_motivo.status_code == 422

    com_motivo = await client.post(
        f"/api/v1/admin/competition-intakes/{intake_id}/reject",
        headers=admin.auth_header,
        json={"reason": "É o edital do ano passado."},
    )
    assert com_motivo.status_code == 200, com_motivo.text
    assert com_motivo.json()["status"] == "REJECTED"
    assert com_motivo.json()["detail"] == "É o edital do ano passado."


async def test_candidato_comum_nao_cadastra_concurso_por_url(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="intake9@exemplo.com.br")
    negado = await client.post(
        "/api/v1/admin/competition-intakes",
        headers=user.auth_header,
        json={"url": URL_DO_PDF},
    )
    assert negado.status_code == 403


# --------------------------------------------------------------------------- #
# Subir o edital e o concurso sair cadastrado
# --------------------------------------------------------------------------- #
async def _subir(
    client: AsyncClient, admin: RegisteredUser, *, pdf: bytes | None = None, auto: bool = True
) -> dict[str, Any]:
    resposta = await client.post(
        "/api/v1/admin/competition-intakes/upload",
        headers=admin.auth_header,
        files={"file": ("edital-de-abertura.pdf", pdf or build_edital_pdf(), "application/pdf")},
        data={"auto_apply": "true" if auto else "false"},
    )
    assert resposta.status_code == 201, resposta.text
    return dict(resposta.json())


async def test_subir_o_edital_cadastra_o_concurso_inteiro_sem_ninguem_digitar(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    db_session: AsyncSession,
) -> None:
    """O pedido literal: sobe o PDF, o concurso aparece cadastrado."""
    admin = await create_admin(client, emails, email="upload1@exemplo.com.br")
    await configure_ai(client, admin)
    # O catálogo tem duas das três disciplinas do edital, com nome idêntico.
    await create_subject(client, admin, name="Língua Portuguesa")
    await create_subject(client, admin, name="Direito Penal")

    corpo = await _subir(client, admin)

    assert corpo["status"] == "APPLIED"
    assert corpo["auto_applied"] is True
    assert corpo["source_kind"] == "UPLOAD"
    assert corpo["source_url"] is None
    assert corpo["source_name"] == "edital-de-abertura.pdf"
    # Não houve link para escolher, e o serviço diz isso em vez de pontuar nada.
    assert corpo["candidates"] == []
    assert corpo["choice_reason"] == "o arquivo foi enviado direto"
    assert corpo["competition_public_id"]

    concurso = await client.get(
        f"/api/v1/admin/catalog/competitions/{corpo['competition_public_id']}",
        headers=admin.auth_header,
    )
    assert concurso.status_code == 200, concurso.text
    ficha = concurso.json()

    # A ficha do concurso, com o que o edital sustenta.
    assert ficha["name"] == "Concurso Público para o cargo de Agente de Polícia"
    # O ano saiu da data da prova conferida, não do calendário.
    assert ficha["year"] == 2026
    assert ficha["education_level"] == "SUPERIOR"
    assert ficha["vacancies_total"] == 1200
    assert ficha["salary_max_cents"] == 815700
    assert ficha["registration_start"] == "2026-01-20"
    assert ficha["registration_end"] == "2026-02-10"
    assert ficha["exam_date"] == "2026-03-15"
    # Cadastro novo não vai ao ar sozinho.
    assert ficha["is_published"] is False
    assert ficha["organization"]["name"] == "Polícia Civil do Distrito Federal"

    # O cargo, com os números da prova.
    assert len(ficha["positions"]) == 1
    cargo = ficha["positions"][0]
    assert cargo["name"] == "Agente de Polícia"
    assert cargo["vacancies"] == 1200
    assert cargo["salary_cents"] == 815700
    assert cargo["education_level"] == "SUPERIOR"
    assert cargo["questions_count"] == 120
    assert cargo["exam_duration_minutes"] == 240

    # A grade, montada das disciplinas do edital que existem no catálogo.
    grade = {item["subject"]["name"] for item in cargo["subjects"]}
    assert grade == {"Língua Portuguesa", "Direito Penal"}
    linhas = (
        (
            await db_session.execute(
                select(PositionSubject).join(Position).where(Position.name == "Agente de Polícia")
            )
        )
        .scalars()
        .all()
    )
    assert {linha.source for linha in linhas} == {"NOTICE"}
    assert all(linha.extra["raw_label"] for linha in linhas)

    # O edital ficou vinculado ao concurso.
    edital = (
        await db_session.execute(
            select(Notice).where(Notice.public_id == corpo["notice_public_id"])
        )
    ).scalar_one()
    assert edital.competition_id is not None


async def test_cadastrado_nao_quer_dizer_completo_e_as_lacunas_sao_nomeadas(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """O que o edital não sustenta fica em branco, com nome e motivo."""
    admin = await create_admin(client, emails, email="upload2@exemplo.com.br")
    await configure_ai(client, admin)
    await create_subject(client, admin, name="Língua Portuguesa")
    # "Direito Penal Militar" é parecido, não idêntico: não entra sozinho.
    await create_subject(client, admin, name="Direito Penal Militar")

    corpo = await _subir(client, admin)
    assert corpo["status"] == "APPLIED"
    lacunas = {item["code"] for item in corpo["gaps"]}

    # A sigla do órgão não existe no edital: foi derivada, e isso está dito.
    assert "SHORT_NAME_DERIVED" in lacunas
    sigla = next(item for item in corpo["gaps"] if item["code"] == "SHORT_NAME_DERIVED")
    assert "PCDF" in sigla["label"]

    # A banca aparece no edital mas não no catálogo: o concurso ficou sem banca,
    # e ninguém criou uma banca a partir de um nome escrito num PDF.
    assert "BOARD_NOT_FOUND" in lacunas
    banca = next(item for item in corpo["gaps"] if item["code"] == "BOARD_NOT_FOUND")
    assert "Cebraspe" in banca["label"]

    # Disciplina sem par exato no catálogo não entra na grade — e é nomeada.
    fora = [item for item in corpo["gaps"] if item["code"] == "SUBJECT_WITHOUT_CATALOG"]
    rotulos = " ".join(item["label"] for item in fora)
    assert "Direito Penal" in rotulos
    assert "Legislação Especial" in rotulos
    penal = next(item for item in fora if "Direito Penal" in item["label"])
    assert "Direito Penal Militar" in (penal["detail"] or "")
    assert "parecido não basta" in (penal["detail"] or "")

    # O campo que a IA só deduziu continua em branco, aqui também.
    campos = {item["field_path"]: item for item in corpo["proposal"]["fields"]}
    assert campos["exam.min_score_rule"]["applicable"] is False
    assert corpo["proposal"]["needs_typing"] >= 1


async def test_o_automatico_para_quando_o_concurso_ja_esta_no_catalogo(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """Cadastrar o mesmo concurso duas vezes é pior que não cadastrar."""
    admin = await create_admin(client, emails, email="upload3@exemplo.com.br")
    await configure_ai(client, admin)

    primeiro = await _subir(client, admin)
    assert primeiro["status"] == "APPLIED"

    segundo = await _subir(client, admin)
    assert segundo["status"] == "AWAITING_REVIEW"
    assert segundo["auto_applied"] is False
    assert segundo["competition_public_id"] is None
    assert "duplicata" in segundo["detail"]
    assert [item["code"] for item in segundo["gaps"]] == ["DUPLICATE"]
    # A ficha fica pronta na tela: o formulário de revisão continua ali.
    assert segundo["proposal"]["applicable"] >= 1
    assert segundo["matches"]["competitions"]


async def test_sem_nome_conferido_no_edital_o_automatico_devolve_a_decisao(
    client: AsyncClient,
    emails: CapturingDispatcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Citação inventada para o nome não vira cadastro."""
    admin = await create_admin(client, emails, email="upload4@exemplo.com.br")

    payload = deepcopy(EXTRACTION_PAYLOAD)
    payload["fields"]["competition.name"]["quote"] = "ISTO NÃO ESTÁ NO DOCUMENTO NENHUM LUGAR"
    provider = FakeProvider(completion_payload=payload)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    await configure_ai(client, admin)

    corpo = await _subir(client, admin)
    assert corpo["status"] == "AWAITING_REVIEW"
    assert corpo["auto_applied"] is False
    assert corpo["competition_public_id"] is None
    assert "nome do concurso" in corpo["detail"]
    # O campo aparece como inferido, não como oficial: a citação não bateu.
    campos = {item["field_path"]: item for item in corpo["proposal"]["fields"]}
    assert campos["competition.name"]["evidence_level"] == EvidenceLevel.INFERRED


async def test_desligar_o_automatico_devolve_a_ficha_para_revisao(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="upload5@exemplo.com.br")
    await configure_ai(client, admin)

    corpo = await _subir(client, admin, auto=False)
    assert corpo["status"] == "AWAITING_REVIEW"
    assert corpo["auto_applied"] is False
    assert corpo["gaps"] == []
    assert corpo["competition_public_id"] is None
    # O edital e o PDF já estão guardados: aplicar depois não baixa nada de novo.
    assert corpo["notice_public_id"]


async def test_arquivo_que_nao_e_pdf_e_recusado_antes_de_gastar_ia(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="upload6@exemplo.com.br")
    recusado = await client.post(
        "/api/v1/admin/competition-intakes/upload",
        headers=admin.auth_header,
        files={"file": ("edital.pdf", b"MZ\x90\x00 isto e um executavel", "application/pdf")},
    )
    assert recusado.status_code == 422, recusado.text
    # O nome do arquivo e o content-type vêm de quem envia: só o conteúdo vale.
    assert recusado.json()["error"]["code"] == "invalid_pdf"

    # Recusado antes de gravar a passagem e antes de qualquer chamada de IA.
    listagem = await client.get("/api/v1/admin/competition-intakes", headers=admin.auth_header)
    assert listagem.json()["total"] == 0


async def test_candidato_comum_nao_sobe_edital(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="upload7@exemplo.com.br")
    negado = await client.post(
        "/api/v1/admin/competition-intakes/upload",
        headers=user.auth_header,
        files={"file": ("edital.pdf", build_edital_pdf(), "application/pdf")},
    )
    assert negado.status_code == 403


async def test_sem_orgao_conferido_o_automatico_tambem_devolve_a_decisao(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um concurso é sempre de alguém: sem órgão não há ficha."""
    admin = await create_admin(client, emails, email="upload8@exemplo.com.br")

    payload = deepcopy(EXTRACTION_PAYLOAD)
    payload["fields"]["organization.name"]["quote"] = "FRASE QUE NAO APARECE NO DOCUMENTO"
    provider = FakeProvider(completion_payload=payload)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    await configure_ai(client, admin)

    corpo = await _subir(client, admin)
    assert corpo["status"] == "AWAITING_REVIEW"
    assert corpo["auto_applied"] is False
    assert corpo["competition_public_id"] is None
    assert "órgão" in corpo["detail"]
    assert [item["code"] for item in corpo["gaps"]] == ["NO_ORGANIZATION"]


# --------------------------------------------------------------------------- #
# Edital com vários cargos — o caso comum, não a exceção
# --------------------------------------------------------------------------- #
@pytest.fixture
def multicargo(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    provider = FakeProvider(completion_payload=EXTRACTION_MULTICARGO)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def test_edital_com_tres_cargos_cadastra_os_tres(
    client: AsyncClient,
    emails: CapturingDispatcher,
    multicargo: FakeProvider,
    db_session: AsyncSession,
) -> None:
    """Cadastrar um e descartar os outros apagaria quem estuda para eles."""
    admin = await create_admin(client, emails, email="multi1@exemplo.com.br")
    await configure_ai(client, admin)
    await create_subject(client, admin, name="Língua Portuguesa")
    await create_subject(client, admin, name="Direito Administrativo")
    await create_subject(client, admin, name="Banco de Dados")

    corpo = await _subir(client, admin, pdf=build_edital_pdf(pages=EDITAL_MULTICARGO_PAGES))
    assert corpo["status"] == "APPLIED", corpo.get("detail")

    concurso = await client.get(
        f"/api/v1/admin/catalog/competitions/{corpo['competition_public_id']}",
        headers=admin.auth_header,
    )
    assert concurso.status_code == 200, concurso.text
    cargos = {item["name"]: item for item in concurso.json()["positions"]}

    assert set(cargos) == {
        "Analista Judiciario - Area Administrativa",
        "Analista Judiciario - Area de Tecnologia",
        "Tecnico Judiciario - Area Administrativa",
    }

    # Cada cargo com os seus próprios números, não os do cargo principal.
    administrativa = cargos["Analista Judiciario - Area Administrativa"]
    assert administrativa["education_level"] == "SUPERIOR"
    assert administrativa["vacancies"] == 150
    assert administrativa["salary_cents"] == 1399478
    assert administrativa["workload_hours"] == 40

    tecnologia = cargos["Analista Judiciario - Area de Tecnologia"]
    assert tecnologia["vacancies"] == 40
    # Cadastro de reserva não é somado às vagas imediatas.
    assert tecnologia["cr_vacancies"] == 80

    tecnico = cargos["Tecnico Judiciario - Area Administrativa"]
    assert tecnico["education_level"] == "MEDIO"
    assert tecnico["vacancies"] == 300
    assert tecnico["salary_cents"] == 852965

    # O cargo extraído aponta para o cargo do catálogo — é o que permite a uma
    # retificação saber qual cargo mudou.
    extraidos = (
        (await db_session.execute(select(NoticePosition).order_by(NoticePosition.order_index)))
        .scalars()
        .all()
    )
    vinculados = [item for item in extraidos if item.position_id is not None]
    assert len(vinculados) == 3


async def test_cada_cargo_recebe_a_grade_comum_mais_a_propria(
    client: AsyncClient, emails: CapturingDispatcher, multicargo: FakeProvider
) -> None:
    """Disciplina sem cargo declarado vale para todos; com cargo, só para ele."""
    admin = await create_admin(client, emails, email="multi2@exemplo.com.br")
    await configure_ai(client, admin)
    await create_subject(client, admin, name="Língua Portuguesa")
    await create_subject(client, admin, name="Direito Administrativo")
    await create_subject(client, admin, name="Banco de Dados")

    corpo = await _subir(client, admin, pdf=build_edital_pdf(pages=EDITAL_MULTICARGO_PAGES))
    concurso = await client.get(
        f"/api/v1/admin/catalog/competitions/{corpo['competition_public_id']}",
        headers=admin.auth_header,
    )
    grades = {
        item["name"]: {link["subject"]["name"] for link in item["subjects"]}
        for item in concurso.json()["positions"]
    }

    # Português é comum: entra nos três.
    assert grades["Analista Judiciario - Area Administrativa"] == {
        "Língua Portuguesa",
        "Direito Administrativo",
    }
    assert grades["Analista Judiciario - Area de Tecnologia"] == {
        "Língua Portuguesa",
        "Banco de Dados",
    }
    # O técnico só tem a comum: a específica dele não está no catálogo.
    assert grades["Tecnico Judiciario - Area Administrativa"] == {"Língua Portuguesa"}

    # E a que ficou de fora é nomeada, com o motivo.
    fora = [item for item in corpo["gaps"] if item["code"] == "SUBJECT_WITHOUT_CATALOG"]
    assert any("Arquivologia" in item["label"] for item in fora)


async def test_cargo_com_citacao_inventada_nao_entra_e_fica_declarado(
    client: AsyncClient, emails: CapturingDispatcher, multicargo: FakeProvider
) -> None:
    """A regra de citação vale para cargo como vale para qualquer outro campo."""
    admin = await create_admin(client, emails, email="multi3@exemplo.com.br")
    await configure_ai(client, admin)

    corpo = await _subir(client, admin, pdf=build_edital_pdf(pages=EDITAL_MULTICARGO_PAGES))
    concurso = await client.get(
        f"/api/v1/admin/catalog/competitions/{corpo['competition_public_id']}",
        headers=admin.auth_header,
    )
    nomes = {item["name"] for item in concurso.json()["positions"]}

    # "Oficial de Justica" foi afirmado pelo modelo com citação que não existe
    # no PDF: não virou cargo.
    assert "Oficial de Justica" not in nomes

    recusados = [item for item in corpo["gaps"] if item["code"] == "POSITION_WITHOUT_EVIDENCE"]
    assert len(recusados) == 1
    assert "Oficial de Justica" in recusados[0]["label"]
    assert "não foi localizada no PDF" in (recusados[0]["detail"] or "")


async def test_edital_de_cargo_unico_continua_cadastrando_um(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """Quem tem um cargo só não ganha cargo nenhum a mais."""
    admin = await create_admin(client, emails, email="multi4@exemplo.com.br")
    await configure_ai(client, admin)

    corpo = await _subir(client, admin)
    concurso = await client.get(
        f"/api/v1/admin/catalog/competitions/{corpo['competition_public_id']}",
        headers=admin.auth_header,
    )
    cargos = concurso.json()["positions"]
    assert len(cargos) == 1
    assert cargos[0]["name"] == "Agente de Polícia"
    assert cargos[0]["vacancies"] == 1200
