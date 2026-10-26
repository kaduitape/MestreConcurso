"""Cadastro por URL: as duas decisões que não dependem de rede."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai.schemas import EDUCATION_LEVELS, ExtractedPosition, NoticeExtraction
from app.domain.intake import (
    AddressRefusedError,
    LinkCandidate,
    choose_notice,
    ensure_fetchable,
    is_private_address,
    pdf_links,
    score_candidate,
)
from app.models.catalog import EducationLevel
from app.services.intake import ProposedField, _derived_short_name, _year_from
from app.services.notice_analysis import _fallback_position

PAGINA = """
<html><body>
  <ul>
    <li><a href="/arquivos/edital-de-abertura-01-2026.pdf">Edital de Abertura nº 1/2026</a></li>
    <li><a href="/arquivos/retificacao-01.pdf">Retificação nº 1</a></li>
    <li><a href="/arquivos/anexo-ii-conteudo.pdf">Anexo II — Conteúdo Programático</a></li>
    <li><a href="/arquivos/prova-2019.pdf">Prova aplicada em 2019</a></li>
    <li><a href="https://outro.exemplo/inscricoes">Inscrições</a></li>
  </ul>
</body></html>
"""


# --------------------------------------------------------------------------- #
# Que endereço pode ser buscado
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/edital.pdf",
        "https://localhost/edital.pdf",
        "https://painel.localhost/edital.pdf",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/edital.pdf",
        "http://192.168.1.1/edital.pdf",
        "http://[::1]/edital.pdf",
        "http://metadata.google.internal/computeMetadata/v1/",
        "file:///etc/passwd",
        "gopher://exemplo.com.br/edital",
        "   ",
    ],
)
def test_enderecos_que_nao_saem_da_rede_sao_recusados(url: str) -> None:
    with pytest.raises(AddressRefusedError):
        ensure_fetchable(url)


def test_endereco_publico_passa_e_volta_normalizado() -> None:
    assert ensure_fetchable("  https://www.pciconcursos.com.br/edital.pdf  ") == (
        "https://www.pciconcursos.com.br/edital.pdf"
    )


def test_nome_de_dominio_nao_e_confundido_com_ip_interno() -> None:
    # O nome só é barrado depois do DNS, no cliente HTTP. Aqui ele passa.
    assert is_private_address("www.in.gov.br") is False
    assert is_private_address("127.0.0.1") is True


# --------------------------------------------------------------------------- #
# Qual PDF é o edital
# --------------------------------------------------------------------------- #
def test_extrai_somente_os_links_de_pdf_com_endereco_absoluto() -> None:
    encontrados = pdf_links(PAGINA, base_url="https://orgao.gov.br/concursos/agente/")
    urls = [item.url for item in encontrados]
    assert urls == [
        "https://orgao.gov.br/arquivos/edital-de-abertura-01-2026.pdf",
        "https://orgao.gov.br/arquivos/retificacao-01.pdf",
        "https://orgao.gov.br/arquivos/anexo-ii-conteudo.pdf",
        "https://orgao.gov.br/arquivos/prova-2019.pdf",
    ]
    assert encontrados[0].text == "Edital de Abertura nº 1/2026"


def test_escolhe_o_edital_de_abertura_e_diz_por_que() -> None:
    escolha = choose_notice(pdf_links(PAGINA, base_url="https://orgao.gov.br/concursos/agente/"))
    assert escolha.refused is False
    assert escolha.chosen is not None
    assert escolha.chosen.candidate.url.endswith("edital-de-abertura-01-2026.pdf")
    assert "edital de abertura" in escolha.chosen.explanation
    # A explicação de cada descartado também fica registrada.
    por_url = {item.candidate.url.rsplit("/", 1)[-1]: item for item in escolha.ranked}
    assert "retificação" in por_url["retificacao-01.pdf"].explanation
    assert por_url["prova-2019.pdf"].score < por_url["edital-de-abertura-01-2026.pdf"].score


def test_pagina_sem_pdf_e_recusa_com_motivo() -> None:
    escolha = choose_notice([])
    assert escolha.refused is True
    assert escolha.refusal is not None
    assert "nenhum link para PDF" in escolha.refusal


def test_quando_nada_parece_edital_o_servico_recusa_em_vez_de_chutar() -> None:
    escolha = choose_notice(
        [
            LinkCandidate(url="https://orgao.gov.br/manual-do-candidato.pdf", text="Manual"),
            LinkCandidate(url="https://orgao.gov.br/perguntas.pdf", text="Perguntas frequentes"),
        ]
    )
    assert escolha.refused is True
    assert escolha.refusal is not None
    assert "se parece com um edital" in escolha.refusal
    # Mesmo recusando, a pontuação de cada candidato fica à vista.
    assert len(escolha.ranked) == 2


def test_empate_tecnico_entre_dois_editais_tambem_e_recusa() -> None:
    escolha = choose_notice(
        [
            LinkCandidate(url="https://orgao.gov.br/edital-1-2026.pdf", text="Edital nº 1/2026"),
            LinkCandidate(url="https://orgao.gov.br/edital-2-2026.pdf", text="Edital nº 2/2026"),
        ]
    )
    assert escolha.refused is True
    assert escolha.refusal is not None
    assert "aponte qual" in escolha.refusal


def test_acento_e_maiuscula_nao_mudam_a_pontuacao() -> None:
    com_acento = score_candidate(
        LinkCandidate(url="https://orgao.gov.br/a.pdf", text="RETIFICAÇÃO DO EDITAL")
    )
    sem_acento = score_candidate(
        LinkCandidate(url="https://orgao.gov.br/a.pdf", text="retificacao do edital")
    )
    assert com_acento.score == sem_acento.score


def test_um_sinal_positivo_nao_conta_duas_vezes() -> None:
    # "edital de abertura" contém "edital" e "abertura": vale 5, não 10.
    pontuado = score_candidate(
        LinkCandidate(url="https://orgao.gov.br/edital-de-abertura.pdf", text="Edital de Abertura")
    )
    assert pontuado.score == 5


# --------------------------------------------------------------------------- #
# As derivações do cadastro automático
# --------------------------------------------------------------------------- #
def _campo(path: str, value: object) -> ProposedField:
    return ProposedField(
        field_path=path,
        label=path,
        value=value,
        evidence_level="OFFICIAL",
        quote="citação conferida",
        page_number=1,
    )


def test_o_ano_sai_da_data_da_prova_quando_ela_existe() -> None:
    aplicaveis = {
        "exam.date": _campo("exam.date", "2027-03-15"),
        "registration.start_date": _campo("registration.start_date", "2026-11-01"),
    }
    # A prova é a data mais específica do concurso: é dela que o ano sai.
    assert _year_from(aplicaveis) == 2027


def test_sem_data_de_prova_o_ano_cai_para_as_inscricoes() -> None:
    assert _year_from({"registration.start_date": _campo("x", "2026-01-20")}) == 2026
    assert _year_from({"registration.end_date": _campo("x", "2025-12-30")}) == 2025


def test_sem_nenhuma_data_conferida_nao_ha_ano() -> None:
    """Chutar o ano corrente seria inventar — melhor devolver a decisão."""
    assert _year_from({}) is None
    assert _year_from({"exam.date": _campo("exam.date", "em breve")}) is None
    assert _year_from({"exam.date": _campo("exam.date", None)}) is None


@pytest.mark.parametrize(
    ("nome", "sigla"),
    [
        ("Polícia Civil do Distrito Federal", "PCDF"),
        ("Tribunal de Justiça do Estado de São Paulo", "TJESP"),
        ("Instituto Nacional do Seguro Social", "INSS"),
        ("Banco do Brasil", "BB"),
    ],
)
def test_a_sigla_do_orgao_sai_das_iniciais_ignorando_preposicoes(nome: str, sigla: str) -> None:
    assert _derived_short_name(nome) == sigla


def test_nome_curto_demais_para_render_sigla_vira_o_proprio_nome() -> None:
    # Uma inicial só não é sigla; melhor mostrar o nome do que uma letra solta.
    assert _derived_short_name("Prefeitura") == "Prefeitura"
    assert _derived_short_name("") == "ORG"


# --------------------------------------------------------------------------- #
# O contrato de extração dos cargos
# --------------------------------------------------------------------------- #
def test_as_duas_listas_de_escolaridade_continuam_iguais() -> None:
    """A cópia na camada de IA só é honesta enquanto este teste passar.

    ``app.ai.schemas`` não importa modelos, então a lista de escolaridades está
    repetida lá. Repetição que ninguém confere viraria divergência silenciosa:
    o catálogo ganharia um nível novo e a extração passaria a descartá-lo.
    """
    assert {item.value for item in EducationLevel} == EDUCATION_LEVELS


def test_escolaridade_fora_da_lista_e_descartada_em_vez_de_virar_palpite() -> None:
    assert ExtractedPosition(name="Analista", education_level="superior").education_level == (
        "SUPERIOR"
    )
    assert ExtractedPosition(name="Analista", education_level="mestrado").education_level is None
    assert ExtractedPosition(name="Analista").education_level is None


def test_cadastro_de_reserva_e_campo_proprio_e_nao_entra_nas_vagas() -> None:
    cargo = ExtractedPosition(name="Analista", vacancies=40, cr_vacancies=80)
    assert cargo.vacancies == 40
    assert cargo.cr_vacancies == 80


def test_nome_de_cargo_curto_demais_nao_vira_cargo() -> None:
    with pytest.raises(ValidationError):
        ExtractedPosition(name="A")


def test_edital_sem_lista_de_cargos_usa_o_cargo_principal() -> None:
    """Edital de cargo único — e resposta de cache da v1 do prompt."""
    extracao = NoticeExtraction.model_validate(
        {
            "fields": {
                "position.name": {
                    "value": "Agente de Polícia",
                    "quote": "para o cargo de Agente de Polícia",
                    "page": 1,
                },
                "position.education_level": {"value": "SUPERIOR"},
                "position.vacancies": {"value": 1200},
                "position.salary_cents": {"value": 815700},
                "exam.questions_count": {"value": 120},
                "exam.duration_minutes": {"value": 240},
            }
        }
    )
    assert extracao.positions == []

    principal = _fallback_position(extracao)
    assert principal is not None
    assert principal.name == "Agente de Polícia"
    assert principal.education_level == "SUPERIOR"
    assert principal.vacancies == 1200
    assert principal.salary_cents == 815700
    assert principal.questions_count == 120
    assert principal.exam_duration_minutes == 240
    # A citação é a do campo que nomeia o cargo: é ela que será conferida no PDF.
    assert principal.quote == "para o cargo de Agente de Polícia"


def test_sem_nome_de_cargo_nenhum_nao_ha_cargo_principal() -> None:
    assert _fallback_position(NoticeExtraction()) is None
    assert (
        _fallback_position(
            NoticeExtraction.model_validate({"fields": {"position.name": {"value": None}}})
        )
        is None
    )
