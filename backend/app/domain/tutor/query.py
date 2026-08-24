"""Preparo da pergunta antes de qualquer chamada ao modelo.

Normalização e expansão de siglas saem de um **dicionário**, não de um LLM: o
mesmo texto sempre gera a mesma busca, e ninguém paga token para expandir "LEP".

O roteamento de intenção também é regra, não escolha do modelo. Isso é
deliberado: se o modelo pudesse escolher a ferramenta, poderia inventar uma
chamada e, com ela, um número. Aqui o Python decide o que buscar, calcula o que
for estatística e entrega pronto — ao modelo resta redigir.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)

# Siglas do universo de concursos. Expandir aqui é barato e determinístico.
ACRONYMS: dict[str, str] = {
    "lep": "Lei de Execução Penal",
    "cf": "Constituição Federal",
    "cf88": "Constituição Federal de 1988",
    "cp": "Código Penal",
    "cpp": "Código de Processo Penal",
    "cc": "Código Civil",
    "cpc": "Código de Processo Civil",
    "clt": "Consolidação das Leis do Trabalho",
    "ctn": "Código Tributário Nacional",
    "cdc": "Código de Defesa do Consumidor",
    "eca": "Estatuto da Criança e do Adolescente",
    "lia": "Lei de Improbidade Administrativa",
    "lrf": "Lei de Responsabilidade Fiscal",
    "taf": "teste de aptidão física",
    "tj": "Tribunal de Justiça",
    "stf": "Supremo Tribunal Federal",
    "stj": "Superior Tribunal de Justiça",
}

# Palavras que não ajudam a recuperar trecho nenhum.
STOPWORDS = {
    "a",
    "as",
    "ao",
    "aos",
    "com",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "essa",
    "esse",
    "esta",
    "este",
    "eu",
    "isso",
    "meu",
    "minha",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "pelo",
    "pela",
    "por",
    "qual",
    "quais",
    "que",
    "quem",
    "se",
    "sobre",
    "um",
    "uma",
    "voce",
    "vc",
}


class Intent(StrEnum):
    """O que a pergunta pede. Define quais dados o Python vai anexar."""

    NOTICE = "NOTICE"  # o que o edital diz
    PERFORMANCE = "PERFORMANCE"  # como o candidato vai
    BOARD = "BOARD"  # como a banca cobra
    PRIORITY = "PRIORITY"  # o que estudar agora
    CONCEPT = "CONCEPT"  # explicar um conteúdo


# Cada intenção tem gatilhos explícitos; a ordem resolve empate.
_INTENT_TRIGGERS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (
        Intent.PERFORMANCE,
        (
            "meu desempenho",
            "meus erros",
            "errei",
            "acertei",
            "minha taxa",
            "meu acerto",
            "como estou",
            "meu resultado",
            "meu historico",
        ),
    ),
    (
        Intent.PRIORITY,
        (
            "o que estudar",
            "por onde comeco",
            "prioridade",
            "estudar agora",
            "estudar primeiro",
            "meu plano",
            "o que faco hoje",
        ),
    ),
    (
        Intent.BOARD,
        (
            "a banca",
            "como a banca",
            "cespe",
            "cebraspe",
            "fgv",
            "vunesp",
            "fcc",
            "costuma cobrar",
            "incidencia",
            "cai mais",
        ),
    ),
    (
        Intent.NOTICE,
        (
            "edital",
            "inscricao",
            "prova objetiva",
            "vagas",
            "salario",
            "requisito",
            "data da prova",
            "cronograma",
            "nota minima",
            "eliminado",
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class PreparedQuery:
    original: str
    normalized: str
    expanded: str
    keywords: list[str] = field(default_factory=list)
    intents: list[Intent] = field(default_factory=list)

    @property
    def primary_intent(self) -> Intent:
        return self.intents[0] if self.intents else Intent.CONCEPT


def normalize(text: str) -> str:
    """Sem acento, sem pontuação, sem caixa, espaços colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = _PUNCTUATION.sub(" ", without_accents)
    return _WHITESPACE.sub(" ", cleaned).strip().lower()


def expand_acronyms(normalized: str) -> str:
    """Acrescenta a forma extensa das siglas conhecidas, sem remover a original."""
    words = normalized.split()
    extra: list[str] = []
    for word in words:
        expansion = ACRONYMS.get(word)
        if expansion and normalize(expansion) not in normalized:
            extra.append(normalize(expansion))
    if not extra:
        return normalized
    return f"{normalized} {' '.join(extra)}"


def keywords(expanded: str, *, limit: int = 24) -> list[str]:
    """Termos úteis para a busca léxica, na ordem em que aparecem."""
    seen: list[str] = []
    for word in expanded.split():
        if len(word) < 3 or word in STOPWORDS or word in seen:
            continue
        seen.append(word)
        if len(seen) >= limit:
            break
    return seen


def detect_intents(normalized: str) -> list[Intent]:
    """Quais dados o Python precisa anexar. Vazio significa "explicar conteúdo"."""
    found: list[Intent] = []
    for intent, triggers in _INTENT_TRIGGERS:
        if any(trigger in normalized for trigger in triggers):
            found.append(intent)
    return found


def prepare(question: str) -> PreparedQuery:
    normalized = normalize(question)
    expanded = expand_acronyms(normalized)
    return PreparedQuery(
        original=question.strip(),
        normalized=normalized,
        expanded=expanded,
        keywords=keywords(expanded),
        intents=detect_intents(normalized),
    )
