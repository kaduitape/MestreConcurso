"""Casar texto livre com o catálogo de disciplinas e tópicos.

A aula e o mapa mental nasceram guardando disciplina e tópico como **texto
livre**. Questão e flashcard sempre tiveram chave estrangeira. Essa diferença
quebra o reprocessamento incremental: quando um edital é retificado, não dá
para saber quais aulas pertencem ao tópico que mudou.

Este módulo propõe o vínculo que falta. Três regras governam o que está aqui:

*A sugestão nunca se aplica sozinha.* O módulo ordena candidatos e explica a
nota. Quem decide é uma pessoa, no painel. Casar "Direito Constitucional" com
"Direito Administrativo" porque as duas começam igual seria pior do que não
casar nada — o conteúdo iria para o tópico errado e o aluno estudaria a coisa
errada achando que está no lugar certo.

*A nota é derivada do texto, não de IA.* Comparar dois nomes é trabalho
determinístico. Pedir isso a um modelo custaria token, variaria entre execuções
e não seria auditável. Aqui a mesma entrada dá sempre a mesma saída, e a razão
da nota é legível.

*Não casar é um resultado válido.* Conteúdo sem vínculo continua funcionando
exatamente como hoje.

O módulo é puro: sem I/O, sem banco, sem IA.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

#: Abaixo disso o candidato não é nem mostrado: ruído atrapalha mais que ajuda.
MIN_SCORE = 0.30

#: Acima disso a interface pode destacar como provável — **sem** aplicar.
STRONG_SCORE = 0.80

#: Quantos candidatos no máximo. Lista longa não é revisada, é aceita no reflexo.
MAX_CANDIDATES = 5

#: Palavras que não distinguem uma disciplina de outra. "Noções de Direito
#: Administrativo" e "Direito Administrativo" são a mesma coisa para quem
#: estuda; manter essas palavras faria a nota cair sem motivo.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "para",
        "por",
        "basica",
        "basicas",
        "basico",
        "basicos",
        "conhecimentos",
        "elementos",
        "fundamentos",
        "geral",
        "gerais",
        "introducao",
        "nocao",
        "nocoes",
        "parte",
        "topicos",
    }
)


class MatchReason(StrEnum):
    """Por que o candidato recebeu a nota. Vai para a tela, em português."""

    EXACT = "EXACT"
    CONTAINS = "CONTAINS"
    OVERLAP = "OVERLAP"


REASON_LABEL: dict[str, str] = {
    MatchReason.EXACT: "nome idêntico",
    MatchReason.CONTAINS: "um nome contém o outro",
    MatchReason.OVERLAP: "palavras em comum",
}


def normalize(value: str) -> str:
    """Tira acento, caixa e pontuação. É a forma comparável do nome."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^0-9a-zA-Z\s]+", " ", text.lower())
    return " ".join(text.split())


def tokens(value: str) -> frozenset[str]:
    """Palavras que distinguem o nome, já sem as que não distinguem nada."""
    words = {word for word in normalize(value).split() if word not in STOPWORDS}
    # Nome formado só por palavras vazias ("Noções Gerais") perderia tudo; aí
    # vale mais comparar o que foi escrito do que comparar nada.
    return frozenset(words or set(normalize(value).split()))


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Uma disciplina ou tópico do catálogo, do jeito que o casamento precisa."""

    public_id: str
    name: str
    #: Caminho do tópico na árvore, quando houver. Entra só na exibição.
    path: str = ""


@dataclass(frozen=True, slots=True)
class MatchCandidate:
    entry: CatalogEntry
    score: float
    reason: str

    @property
    def is_strong(self) -> bool:
        return self.score >= STRONG_SCORE

    @property
    def reason_label(self) -> str:
        return REASON_LABEL.get(self.reason, self.reason)


@dataclass(frozen=True, slots=True)
class MatchResult:
    """O que a tela recebe: candidatos ordenados e nada decidido."""

    query: str
    candidates: list[MatchCandidate] = field(default_factory=list)

    @property
    def best(self) -> MatchCandidate | None:
        return self.candidates[0] if self.candidates else None

    @property
    def is_decided(self) -> bool:
        """Nunca. Existe para deixar explícito que a decisão é humana."""
        return False


def score_pair(query: str, name: str) -> tuple[float, str]:
    """Nota de 0 a 1 entre dois nomes, com o motivo.

    A escada é deliberada: igualdade vale mais que continência, que vale mais
    que palavras em comum. Uma nota alta por motivo fraco enganaria quem revisa.
    """
    left, right = normalize(query), normalize(name)
    if not left or not right:
        return 0.0, MatchReason.OVERLAP
    if left == right:
        return 1.0, MatchReason.EXACT

    left_tokens, right_tokens = tokens(query), tokens(name)
    if not left_tokens or not right_tokens:
        return 0.0, MatchReason.OVERLAP

    if left_tokens == right_tokens:
        # Mesmas palavras distintivas, ordem ou ruído diferente.
        return 0.95, MatchReason.EXACT

    if left_tokens <= right_tokens or right_tokens <= left_tokens:
        # "Direito Administrativo" dentro de "Direito Administrativo e Penal".
        menor, maior = sorted((len(left_tokens), len(right_tokens)))
        return 0.70 + 0.20 * (menor / maior), MatchReason.CONTAINS

    comum = left_tokens & right_tokens
    if not comum:
        return 0.0, MatchReason.OVERLAP
    jaccard = len(comum) / len(left_tokens | right_tokens)
    return round(0.65 * jaccard, 4), MatchReason.OVERLAP


def suggest(query: str, entries: list[CatalogEntry]) -> MatchResult:
    """Ordena os candidatos do catálogo para um texto livre.

    Devolve lista vazia quando nada chega perto. Lista vazia é resposta: quer
    dizer "o catálogo não tem isso", e quem revisa precisa poder ver isso em vez
    de receber o item menos ruim como se fosse o certo.
    """
    if not normalize(query):
        return MatchResult(query=query)

    scored: list[MatchCandidate] = []
    for entry in entries:
        score, reason = score_pair(query, entry.name)
        if score >= MIN_SCORE:
            scored.append(MatchCandidate(entry=entry, score=round(score, 4), reason=reason))

    # Nota desc; empate decidido pelo nome, para a ordem não variar entre leituras.
    scored.sort(key=lambda item: (-item.score, item.entry.name))
    return MatchResult(query=query, candidates=scored[:MAX_CANDIDATES])
