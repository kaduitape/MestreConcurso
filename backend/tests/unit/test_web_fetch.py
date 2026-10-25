"""As travas do único lugar onde o servidor busca um endereço escolhido de fora.

Os testes injetam um transporte em memória pela costura ``_client``: o caminho
de travas, redirecionamentos e teto de bytes é o de produção, só a rede é que
não existe.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from app.services import web_fetch
from app.services.web_fetch import FetchRefusedError, fetch

PUBLICO = ["200.160.2.3"]


@pytest.fixture
def dns_publico(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo nome resolve para um IP público, menos os que o teste disser."""

    async def resolve(host: str, port: int) -> list[str]:
        return {"interno.exemplo.com.br": ["127.0.0.1"]}.get(host, PUBLICO)

    monkeypatch.setattr(web_fetch, "_resolved_addresses", resolve)


def _instalar(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    transporte = httpx.MockTransport(handler)  # type: ignore[arg-type]

    def build() -> httpx.AsyncClient:
        return httpx.AsyncClient(follow_redirects=False, transport=transporte)

    monkeypatch.setattr(web_fetch, "_client", build)


async def test_busca_um_pdf_e_registra_o_endereco_final(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"%PDF-1.7 conteudo", headers={"content-type": "application/pdf"}
        )

    _instalar(monkeypatch, handler)
    recurso = await fetch("https://orgao.gov.br/edital.pdf")
    assert recurso.looks_like_pdf is True
    assert recurso.looks_like_html is False
    assert recurso.final_url == "https://orgao.gov.br/edital.pdf"
    assert recurso.content.startswith(b"%PDF-")


async def test_reconhece_html_mesmo_sem_content_type(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<!DOCTYPE html><html></html>", headers={})

    _instalar(monkeypatch, handler)
    recurso = await fetch("https://orgao.gov.br/concursos")
    assert recurso.looks_like_html is True


async def test_cada_salto_de_redirecionamento_passa_pelas_mesmas_travas(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    """Um 302 para a rede interna não ganha carona na permissão do original."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/edital.pdf":
            return httpx.Response(302, headers={"location": "http://interno.exemplo.com.br/x.pdf"})
        return httpx.Response(200, content=b"%PDF-1.7")

    _instalar(monkeypatch, handler)
    with pytest.raises(FetchRefusedError) as erro:
        await fetch("https://orgao.gov.br/edital.pdf")
    assert "rede interna" in erro.value.message
    assert "127.0.0.1" in erro.value.message


async def test_redirecionamento_bom_e_seguido_ate_o_destino(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/edital":
            return httpx.Response(301, headers={"location": "/arquivos/edital.pdf"})
        return httpx.Response(200, content=b"%PDF-1.7", headers={"content-type": "application/pdf"})

    _instalar(monkeypatch, handler)
    recurso = await fetch("https://orgao.gov.br/edital")
    assert recurso.url == "https://orgao.gov.br/edital"
    assert recurso.final_url == "https://orgao.gov.br/arquivos/edital.pdf"


async def test_laco_de_redirecionamento_para_no_limite(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://orgao.gov.br/outra"})

    _instalar(monkeypatch, handler)
    with pytest.raises(FetchRefusedError) as erro:
        await fetch("https://orgao.gov.br/edital")
    assert "redirecionou mais de" in erro.value.message


async def test_teto_de_bytes_aborta_durante_o_download(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    """O limite é lido enquanto desce, não depois: 10 MB não viram 10 MB de RAM."""
    entregues = 0

    async def corpo() -> AsyncIterator[bytes]:
        nonlocal entregues
        for _ in range(100):
            entregues += 1
            yield b"x" * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=corpo(), headers={"content-type": "application/pdf"})

    _instalar(monkeypatch, handler)
    with pytest.raises(FetchRefusedError) as erro:
        await fetch("https://orgao.gov.br/enorme.pdf", max_bytes=4 * 1024)
    assert "passou do limite" in erro.value.message
    assert entregues < 100


async def test_erro_do_site_vira_recusa_legivel(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    _instalar(monkeypatch, handler)
    with pytest.raises(FetchRefusedError) as erro:
        await fetch("https://orgao.gov.br/sumiu.pdf")
    assert "respondeu 404" in erro.value.message


async def test_endereco_interno_nao_chega_a_sair(
    monkeypatch: pytest.MonkeyPatch, dns_publico: None
) -> None:
    chamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal chamadas
        chamadas += 1
        return httpx.Response(200, content=b"%PDF-1.7")

    _instalar(monkeypatch, handler)
    with pytest.raises(FetchRefusedError):
        await fetch("http://127.0.0.1:6379/edital.pdf")
    assert chamadas == 0
