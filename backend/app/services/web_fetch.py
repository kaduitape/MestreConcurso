"""Buscar um endereço que outra pessoa digitou — com as travas que isso exige.

Este é o único lugar do projeto onde o servidor faz uma requisição para um
endereço escolhido de fora. Isso merece cuidado específico, e não genérico: a
aplicação roda no mesmo host do banco e do Redis, e uma URL como
``http://169.254.169.254/latest/meta-data`` ou ``http://127.0.0.1:6379`` pediria
ao próprio servidor que buscasse os segredos dele e devolvesse na tela.

Quatro travas, todas conferidas em **cada salto** de redirecionamento:

1. esquema HTTP ou HTTPS, nada mais;
2. o nome **resolvido** não pode cair em faixa interna — a conferência é depois
   do DNS, porque ``interno.exemplo.com`` que aponta para ``127.0.0.1`` passaria
   por qualquer verificação feita só no texto do endereço;
3. teto de bytes, lido durante o download e não depois, para que um arquivo de
   dez gigabytes não vire dez gigabytes de memória;
4. tempo máximo, porque servidor de banca cai.

O conteúdo devolvido é **dado**. Nada dele é instrução, nem quando o HTML ou o
PDF contiver frases dirigidas a um modelo.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass

import anyio
import httpx

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.domain.intake import (
    MAX_PAGE_BYTES,
    AddressRefusedError,
    ensure_fetchable,
    is_private_address,
)

logger = get_logger(__name__)

#: Saltos de redirecionamento. Portais de banca redirecionam duas, três vezes;
#: mais do que isso é laço ou rastreador.
MAX_REDIRECTS = 5

#: Tempo total por salto. Servidor de banca é lento; esperar um minuto por um
#: deles seria segurar o pedido de quem está cadastrando.
TIMEOUT_SECONDS = 20.0

#: Identificação honesta. Esconder quem está buscando não ajudaria em nada e
#: impediria o administrador do site de falar com a gente se precisasse.
USER_AGENT = "GameOfConcursos/1.0 (cadastro de edital; contato pelo site)"


class FetchRefusedError(ValidationError):
    """O endereço não pôde ser buscado, e a mensagem diz por quê."""

    code = "intake_fetch_refused"


@dataclass(frozen=True, slots=True)
class FetchedResource:
    """O que voltou de um endereço, com a procedência registrada."""

    url: str
    #: Endereço final, depois dos redirecionamentos. Pode diferir do pedido.
    final_url: str
    content_type: str
    content: bytes

    @property
    def looks_like_pdf(self) -> bool:
        return self.content.startswith(b"%PDF-") or "pdf" in self.content_type.lower()

    @property
    def looks_like_html(self) -> bool:
        return "html" in self.content_type.lower() or self.content.lstrip()[
            :200
        ].lower().startswith((b"<!doctype", b"<html"))


async def _resolved_addresses(host: str, port: int) -> list[str]:
    """Os IPs para onde este nome aponta, agora."""

    def resolve() -> list[str]:
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except OSError as exc:  # nome que não resolve
            raise FetchRefusedError(f"Não foi possível resolver o endereço '{host}'.") from exc
        return [str(info[4][0]) for info in infos]

    return await anyio.to_thread.run_sync(resolve)


async def _guard(url: str) -> str:
    """Confere esquema, domínio e **IP resolvido**. Devolve a URL aceita."""
    try:
        limpa = ensure_fetchable(url)
    except AddressRefusedError as exc:
        raise FetchRefusedError(str(exc)) from exc

    parsed = httpx.URL(limpa)
    host = parsed.host
    porta = parsed.port or (443 if parsed.scheme == "https" else 80)
    for endereco in await _resolved_addresses(host, porta):
        if is_private_address(endereco):
            logger.warning("intake.fetch_blocked", host=host, resolved=endereco)
            raise FetchRefusedError(
                f"O endereço '{host}' aponta para a rede interna ({endereco}) "
                "e não pode ser buscado."
            )
    return limpa


def _client() -> httpx.AsyncClient:
    """O cliente HTTP, numa função só para servir de costura de teste.

    O teste injeta um transporte e exercita o **mesmo** caminho de travas,
    redirecionamentos e teto de bytes que a produção percorre — em vez de
    reimplementar o laço com um dublê.
    """
    return httpx.AsyncClient(
        follow_redirects=False,
        timeout=TIMEOUT_SECONDS,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*"},
    )


async def fetch(url: str, *, max_bytes: int = MAX_PAGE_BYTES) -> FetchedResource:
    """Busca uma página ou um PDF, seguindo redirecionamentos com as travas.

    Cada salto passa pelas mesmas conferências do primeiro: um site que
    responde ``302`` para ``http://127.0.0.1`` não ganha carona na permissão
    que o endereço original tinha.
    """
    atual = await _guard(url)
    async with _client() as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream("GET", atual) as resposta:
                    if resposta.is_redirect:
                        destino = resposta.headers.get("location")
                        if not destino:
                            raise FetchRefusedError(
                                "O site respondeu com redirecionamento sem destino."
                            )
                        atual = await _guard(str(httpx.URL(atual).join(destino)))
                        continue

                    if resposta.status_code >= 400:
                        raise FetchRefusedError(
                            f"O site respondeu {resposta.status_code} para este endereço."
                        )

                    pedacos = bytearray()
                    async for pedaco in resposta.aiter_bytes():
                        pedacos.extend(pedaco)
                        if len(pedacos) > max_bytes:
                            # Abortado durante o download: o teto existe para
                            # não trazer para a memória o que não cabe nela.
                            raise FetchRefusedError(
                                f"O arquivo passou do limite de {max_bytes // (1024 * 1024)} MB."
                            )
                    return FetchedResource(
                        url=url,
                        final_url=str(resposta.url),
                        content_type=resposta.headers.get("content-type", ""),
                        content=bytes(pedacos),
                    )
            except httpx.HTTPError as exc:
                raise FetchRefusedError(f"Não foi possível acessar o endereço: {exc}") from exc

    raise FetchRefusedError(f"O endereço redirecionou mais de {MAX_REDIRECTS} vezes.")
