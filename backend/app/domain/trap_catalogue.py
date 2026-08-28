"""Catálogo de padrões de pegadinha.

São **categorias de técnica de prova** — o nome do erro em que o candidato caiu —
e não afirmações sobre nenhuma banca específica. Quantas vezes alguém caiu em cada
padrão é conta feita sobre os erros que a própria pessoa classificou.

O catálogo é editorial e pode ser ajustado no painel; este arquivo é apenas o
ponto de partida sincronizado no seed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrapSpec:
    slug: str
    name: str
    category: str
    description: str
    detection_hint: str


TRAP_PATTERNS: tuple[TrapSpec, ...] = (
    TrapSpec(
        "generalizacao-indevida",
        "Generalização indevida",
        "REDACAO",
        "A alternativa transforma uma regra com exceções em regra absoluta.",
        "Procure por “sempre”, “nunca”, “em qualquer hipótese”, “todo”.",
    ),
    TrapSpec(
        "troca-de-prazo",
        "Troca de prazo ou número",
        "DETALHE",
        "O enunciado mantém a estrutura correta e altera um prazo, percentual ou quantidade.",
        "Confira cada número contra a letra da lei antes de marcar.",
    ),
    TrapSpec(
        "inversao-de-competencia",
        "Inversão de competência ou de sujeito",
        "DETALHE",
        "A atribuição correta é deslocada para outro órgão, autoridade ou sujeito.",
        "Releia quem pratica o ato e quem tem competência para autorizá-lo.",
    ),
    TrapSpec(
        "regra-e-excecao",
        "Exceção apresentada como regra",
        "REDACAO",
        "A alternativa apresenta a exceção legal como se fosse a regra geral (ou o contrário).",
        "Identifique o caput e o parágrafo: um traz a regra, o outro a exceção.",
    ),
    TrapSpec(
        "comando-negativo",
        "Comando negativo despercebido",
        "ENUNCIADO",
        "O comando pede a alternativa incorreta e o candidato responde a correta.",
        "Sublinhe “exceto”, “não”, “incorreto” antes de olhar as alternativas.",
    ),
    TrapSpec(
        "conceito-parecido",
        "Conceitos parecidos trocados",
        "CONTEUDO",
        "Dois institutos semelhantes têm suas definições trocadas entre si.",
        "Monte um quadro comparativo dos dois conceitos que costumam se confundir.",
    ),
    TrapSpec(
        "acrescimo-inexistente",
        "Requisito inexistente acrescentado",
        "CONTEUDO",
        "A alternativa acrescenta uma condição que a norma não exige.",
        "Confira se cada requisito citado está mesmo no texto legal.",
    ),
    TrapSpec(
        "literalidade-alterada",
        "Literalidade alterada",
        "REDACAO",
        "Uma palavra do texto legal é trocada por outra de sentido próximo, mas distinto.",
        "Compare a alternativa palavra a palavra com o dispositivo citado.",
    ),
)
