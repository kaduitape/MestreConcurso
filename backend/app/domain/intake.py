"""Cadastro de concurso a partir de uma URL: as decisões que não dependem de I/O.

Duas coisas acontecem antes de qualquer IA, e as duas são determinísticas:

**Qual endereço pode ser buscado.** Buscar uma URL que alguém digitou é, do
ponto de vista do servidor, deixar um estranho escolher o destino de uma
requisição que sai de dentro da rede. Endereço interno, loopback, metadados de
nuvem e esquema que não seja HTTP ficam de fora — não como detalhe de segurança
genérico, mas porque este serviço roda no mesmo host do banco.

**Qual PDF é o edital.** Uma página de concurso traz dez links: abertura,
retificações, anexos, provas anteriores, gabaritos, resultado. Escolher "o
primeiro PDF" acertaria às vezes, e errar aqui significa analisar a prova de
2019 e cadastrar um concurso inteiro a partir dela. A escolha é por pontuação
explicada, e **quando nada se destaca o serviço recusa** e pede que uma pessoa
aponte o link — recusar é melhor que cadastrar concurso a partir do documento
errado.

O módulo é puro: sem rede, sem banco, sem IA.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urljoin, urlparse

#: Tamanho máximo do que se busca numa URL. Página de concurso é texto; PDF de
#: edital raramente passa de alguns megabytes, e o limite de upload do projeto
#: já governa o arquivo em si.
MAX_PAGE_BYTES = 4 * 1024 * 1024

#: Quantos candidatos a edital são considerados. Acima disso é lista de
#: documentos de um portal inteiro, não a página de um concurso.
MAX_CANDIDATES = 40

#: A partir desta pontuação o candidato é tratado como edital de abertura.
MIN_SCORE = 3

#: Distância mínima entre o primeiro e o segundo colocado. Empate técnico é
#: motivo de recusa: dois "editais" plausíveis significam que a página tem mais
#: de um concurso, ou que o nosso critério não serve ali.
MIN_MARGIN = 2


class RefusalReason(StrEnum):
    """Por que o serviço não escolheu sozinho. Sempre dito, nunca só contado."""

    NO_PDF = "NO_PDF"
    NOTHING_LOOKS_LIKE_A_NOTICE = "NOTHING_LOOKS_LIKE_A_NOTICE"
    TIE = "TIE"


#: O texto que vai para a tela de quem cadastra.
REFUSAL_LABEL: dict[str, str] = {
    RefusalReason.NO_PDF: "a página não tem nenhum link para PDF",
    RefusalReason.NOTHING_LOOKS_LIKE_A_NOTICE: (
        "nenhum PDF da página se parece com um edital de abertura"
    ),
    RefusalReason.TIE: (
        "dois ou mais PDFs são igualmente plausíveis como edital — aponte qual é o certo"
    ),
}


# --------------------------------------------------------------------------- #
# Que endereço pode ser buscado
# --------------------------------------------------------------------------- #
class AddressRefusedError(ValueError):
    """O endereço não pode ser buscado, e o motivo é legível."""


_PRIVATE_HOSTNAMES = frozenset(
    {"localhost", "localhost.localdomain", "metadata", "metadata.google.internal"}
)


def ensure_fetchable(url: str) -> str:
    """Devolve a URL normalizada, ou recusa com o motivo.

    A conferência de nome resolvido para IP acontece no cliente HTTP, que é
    quem conhece o DNS; aqui ficam as recusas que se decidem só pelo texto do
    endereço — e que, por serem puras, podem ser testadas sem rede.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise AddressRefusedError("Informe o endereço da página ou do PDF do edital.")

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"}:
        raise AddressRefusedError(
            "Só endereços http:// ou https:// são aceitos — "
            f"'{parsed.scheme or 'sem esquema'}' não é buscável."
        )
    host = (parsed.hostname or "").lower()
    if not host:
        raise AddressRefusedError("O endereço não tem domínio.")
    if host in _PRIVATE_HOSTNAMES or host.endswith(".localhost"):
        raise AddressRefusedError("Endereço interno não é buscável.")
    if is_private_address(host):
        raise AddressRefusedError("Endereço interno não é buscável.")
    return cleaned


def is_private_address(host: str) -> bool:
    """Verdadeiro quando o host é um IP de uso interno.

    Cobre loopback, redes privadas, link-local (onde vivem os metadados de
    nuvem), multicast e reservados. Nome que **resolve** para um IP desses é
    barrado no cliente HTTP, depois do DNS.
    """
    try:
        endereco = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        endereco.is_private
        or endereco.is_loopback
        or endereco.is_link_local
        or endereco.is_multicast
        or endereco.is_reserved
        or endereco.is_unspecified
    )


# --------------------------------------------------------------------------- #
# Qual PDF é o edital
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class LinkCandidate:
    """Um link para PDF encontrado na página."""

    url: str
    #: O texto do link, do jeito que apareceu. É dado, não instrução.
    text: str = ""


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    candidate: LinkCandidate
    score: int
    #: O que somou e o que subtraiu, em português, para a tela mostrar.
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def explanation(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "nenhum sinal encontrado"


@dataclass(frozen=True, slots=True)
class Choice:
    """A escolha, ou a recusa com o motivo."""

    ranked: tuple[ScoredCandidate, ...] = field(default_factory=tuple)
    chosen: ScoredCandidate | None = None
    refusal: str | None = None

    @property
    def refused(self) -> bool:
        return self.chosen is None


#: Sinais que aproximam o link de um edital de abertura.
_POSITIVE: tuple[tuple[str, int, str], ...] = (
    ("edital de abertura", 5, "o link diz 'edital de abertura'"),
    ("edital-de-abertura", 5, "o nome do arquivo diz 'edital-de-abertura'"),
    ("edital n", 3, "o link traz 'edital nº'"),
    ("edital", 3, "o link traz 'edital'"),
    ("abertura", 2, "o link traz 'abertura'"),
    ("concurso publico", 1, "o link menciona concurso público"),
    ("processo seletivo", 1, "o link menciona processo seletivo"),
)

#: Sinais que afastam: são documentos do mesmo concurso, mas não o de abertura.
_NEGATIVE: tuple[tuple[str, int, str], ...] = (
    ("retificacao", 4, "é retificação, não o edital de abertura"),
    ("rerratificacao", 4, "é rerratificação"),
    ("errata", 3, "é errata"),
    ("anexo", 3, "é anexo"),
    ("gabarito", 5, "é gabarito"),
    ("resultado", 4, "é resultado"),
    ("classificacao", 4, "é classificação"),
    ("convocacao", 3, "é convocação"),
    ("prova", 3, "é prova aplicada"),
    ("caderno", 3, "é caderno de questões"),
    ("recurso", 2, "trata de recursos"),
    ("cronograma", 2, "é cronograma"),
    ("homologacao", 3, "é homologação"),
    ("isencao", 2, "trata de isenção"),
)


def _normalized(value: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", value or "")
    sem_acento = "".join(ch for ch in sem_acento if not unicodedata.combining(ch))
    return re.sub(r"[\s_]+", " ", sem_acento).strip().lower()


def score_candidate(candidate: LinkCandidate) -> ScoredCandidate:
    """Pontua um link pelo texto e pelo nome do arquivo, dizendo o porquê."""
    alvo = f"{_normalized(candidate.text)} {_normalized(candidate.url)}"
    total = 0
    motivos: list[str] = []

    for termo, peso, motivo in _POSITIVE:
        if termo in alvo:
            total += peso
            motivos.append(f"+{peso}: {motivo}")
            # "edital de abertura" já contém "edital": não conta duas vezes.
            break

    for termo, peso, motivo in _NEGATIVE:
        if termo in alvo:
            total -= peso
            motivos.append(f"-{peso}: {motivo}")

    return ScoredCandidate(candidate=candidate, score=total, reasons=tuple(motivos))


def choose_notice(candidates: list[LinkCandidate]) -> Choice:
    """Escolhe o edital de abertura entre os PDFs da página, ou recusa.

    A recusa é parte do desenho: analisar o documento errado cadastraria um
    concurso inteiro a partir de uma prova antiga ou de uma retificação, e isso
    é mais caro de desfazer do que de evitar.
    """
    if not candidates:
        return Choice(refusal=REFUSAL_LABEL[RefusalReason.NO_PDF])

    pontuados = sorted(
        (score_candidate(item) for item in candidates[:MAX_CANDIDATES]),
        key=lambda item: (-item.score, item.candidate.url),
    )
    melhor = pontuados[0]
    if melhor.score < MIN_SCORE:
        return Choice(
            ranked=tuple(pontuados),
            refusal=REFUSAL_LABEL[RefusalReason.NOTHING_LOOKS_LIKE_A_NOTICE],
        )
    if len(pontuados) > 1 and melhor.score - pontuados[1].score < MIN_MARGIN:
        return Choice(ranked=tuple(pontuados), refusal=REFUSAL_LABEL[RefusalReason.TIE])
    return Choice(ranked=tuple(pontuados), chosen=melhor)


_HREF = re.compile(r"""<a\b[^>]*?href\s*=\s*["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


def pdf_links(html: str, *, base_url: str) -> list[LinkCandidate]:
    """Extrai os links para PDF de uma página.

    O HTML é **dado**: nada dele é executado, nada dele é instrução. A extração
    é por expressão regular de propósito — trazer um analisador de HTML
    completo para ler ``href`` aumentaria a superfície de ataque sem melhorar o
    resultado para o que esta função precisa.
    """
    encontrados: list[LinkCandidate] = []
    vistos: set[str] = set()
    for href, interno in _HREF.findall(html or ""):
        destino = urljoin(base_url, href.strip())
        sem_query = urlparse(destino).path.lower()
        if not sem_query.endswith(".pdf"):
            continue
        if destino in vistos:
            continue
        vistos.add(destino)
        texto = _TAGS.sub(" ", interno)
        encontrados.append(LinkCandidate(url=destino, text=re.sub(r"\s+", " ", texto).strip()))
    return encontrados
