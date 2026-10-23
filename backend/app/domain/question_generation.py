"""O que se pode conferir numa questão **antes** de ela existir no banco.

Este módulo é a parte honesta da expressão "gabarito validado na origem", e vale
dizer com precisão o que ela significa — porque ela promete menos do que parece.

**O que é conferido aqui, de forma determinística:**

* a questão tem **exatamente um** gabarito;
* o gabarito vem acompanhado de uma **citação literal do material**, conferida
  caractere a caractere depois de normalizar espaços e acentos;
* a justificativa existe, e cada alternativa errada diz por que erra;
* as alternativas não se repetem, não estão vazias e são em número de prova;
* o enunciado não se **apresenta como questão de banca** — nem pelo nome da
  banca, nem por ano de prova, nem por "conforme prova anterior".

**O que NÃO é conferido aqui, e nenhum código pode conferir:** se o gabarito
está *certo*. Um modelo pode copiar um trecho verdadeiro do material e marcar a
alternativa errada como correta. A citação prova que existe **respaldo
declarado** no material, não que a leitura dele foi correta.

Por isso a questão gerada nasce ``DRAFT`` e só é publicada por uma pessoa, com o
portão da Fase 3 no caminho. O que este módulo faz é jogar fora, sem custo
humano, tudo o que já é demonstravelmente ruim — para que a revisão humana gaste
atenção no que ela é a única capaz de julgar.

O módulo é puro: sem I/O, sem banco, sem IA.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.evidence import MIN_QUOTE_LENGTH, normalize_for_match

#: Enunciado abaixo disto é recorte perdido, não questão. É o mesmo mínimo da
#: regra ``question.statement_too_short`` do auditor, de propósito: duas réguas
#: diferentes para a mesma coisa acabariam divergindo.
MIN_STATEMENT_CHARS = 40

#: Alternativas de prova de concurso. Menos de quatro não é questão objetiva de
#: concurso; mais de cinco não existe em banca nenhuma do país.
MIN_ALTERNATIVES = 4
MAX_ALTERNATIVES = 5

#: Letras aceitas, na ordem em que precisam aparecer.
LETTERS = ("A", "B", "C", "D", "E")

#: Alternativas que transformam a questão num teste de interpretação do próprio
#: enunciado. Banca usa; questão gerada por IA, não — o erro de uma delas
#: contamina as outras e o candidato não aprende nada do conteúdo.
_FORBIDDEN_ALTERNATIVES = (
    "todas as anteriores",
    "nenhuma das anteriores",
    "todas as alternativas",
    "nenhuma das alternativas",
    "n.d.a",
)

#: "(CESPE/2023)", "FGV - 2019", "CESPE 2021" e companhia.
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
#: O formato clássico de atribuição de prova: parênteses no começo do enunciado
#: com um ano dentro. Ele é barrado mesmo quando a banca não está no catálogo —
#: uma instalação nova não tem banca cadastrada, e seria justamente ali que o
#: enunciado com cara de prova passaria sem ninguém notar.
_LEADING_PARENS = re.compile(r"^\s*[\(\[]([^)\]]{2,80})[\)\]]")
#: Referência normativa dentro dos parênteses não é atribuição de prova:
#: "(Lei nº 8.112/1990)" é citação legítima e precisa continuar passando.
_NORMATIVE_WORDS = (
    "lei",
    "decreto",
    "art",
    "artigo",
    "súmula",
    "sumula",
    "constituição",
    "constituicao",
    "emenda",
    "portaria",
    "resolução",
    "resolucao",
    "instrução",
    "instrucao",
    "código",
    "codigo",
    "estatuto",
    "inciso",
    "cf/",
    "clt",
)
#: Frases que atribuem a questão a uma prova sem nomear banca.
_PROVENANCE_PHRASES = (
    "conforme prova",
    "segundo a prova",
    "questão adaptada",
    "adaptada de prova",
    "em prova anterior",
    "prova aplicada",
    "concurso anterior",
)

_WHITESPACE = re.compile(r"\s+")


class RejectionReason(StrEnum):
    """Por que o rascunho foi jogado fora. Sempre dito, nunca só contado."""

    STATEMENT_TOO_SHORT = "STATEMENT_TOO_SHORT"
    ALTERNATIVE_COUNT = "ALTERNATIVE_COUNT"
    LETTERS_OUT_OF_ORDER = "LETTERS_OUT_OF_ORDER"
    ALTERNATIVE_EMPTY = "ALTERNATIVE_EMPTY"
    ALTERNATIVE_REPEATED = "ALTERNATIVE_REPEATED"
    FORBIDDEN_ALTERNATIVE = "FORBIDDEN_ALTERNATIVE"
    NO_SINGLE_ANSWER = "NO_SINGLE_ANSWER"
    #: A citação não existe literalmente no material.
    QUOTE_NOT_IN_MATERIAL = "QUOTE_NOT_IN_MATERIAL"
    QUOTE_TOO_SHORT = "QUOTE_TOO_SHORT"
    EXPLANATION_MISSING = "EXPLANATION_MISSING"
    WRONG_WITHOUT_FEEDBACK = "WRONG_WITHOUT_FEEDBACK"
    #: O enunciado se apresenta como questão de banca ou de prova aplicada.
    FABRICATED_PROVENANCE = "FABRICATED_PROVENANCE"
    #: O enunciado entrega a resposta, ou a correta repete o enunciado.
    ANSWER_IN_STATEMENT = "ANSWER_IN_STATEMENT"


#: O texto que vai para a tela de quem gerou. Cada motivo diz o que fazer com
#: ele: material melhor, prompt melhor, ou nada (descarte normal).
REASON_LABEL: dict[str, str] = {
    RejectionReason.STATEMENT_TOO_SHORT: (
        f"enunciado com menos de {MIN_STATEMENT_CHARS} caracteres"
    ),
    RejectionReason.ALTERNATIVE_COUNT: (
        f"número de alternativas fora de {MIN_ALTERNATIVES} a {MAX_ALTERNATIVES}"
    ),
    RejectionReason.LETTERS_OUT_OF_ORDER: "letras das alternativas fora de ordem ou repetidas",
    RejectionReason.ALTERNATIVE_EMPTY: "alternativa sem texto",
    RejectionReason.ALTERNATIVE_REPEATED: "duas alternativas com o mesmo texto",
    RejectionReason.FORBIDDEN_ALTERNATIVE: '"todas"/"nenhuma das anteriores" entre as alternativas',
    RejectionReason.NO_SINGLE_ANSWER: "gabarito ausente ou mais de uma alternativa correta",
    RejectionReason.QUOTE_NOT_IN_MATERIAL: "a citação do gabarito não existe no material",
    RejectionReason.QUOTE_TOO_SHORT: (
        f"citação com menos de {MIN_QUOTE_LENGTH} caracteres não sustenta o gabarito"
    ),
    RejectionReason.EXPLANATION_MISSING: "gabarito sem justificativa",
    RejectionReason.WRONG_WITHOUT_FEEDBACK: "alternativa errada sem explicação do erro",
    RejectionReason.FABRICATED_PROVENANCE: "o enunciado se apresenta como questão de banca",
    RejectionReason.ANSWER_IN_STATEMENT: "o enunciado já contém a alternativa correta",
}


@dataclass(frozen=True, slots=True)
class DraftAlternative:
    letter: str
    content: str
    is_correct: bool
    feedback: str | None = None


@dataclass(frozen=True, slots=True)
class DraftQuestion:
    """O que o modelo propôs, antes de qualquer conferência."""

    statement: str
    alternatives: tuple[DraftAlternative, ...]
    explanation: str
    quote: str
    difficulty: str = "MEDIUM"

    @property
    def correct(self) -> DraftAlternative | None:
        corretas = [item for item in self.alternatives if item.is_correct]
        return corretas[0] if len(corretas) == 1 else None


@dataclass(frozen=True, slots=True)
class Verdict:
    """O resultado da conferência de um rascunho."""

    draft: DraftQuestion
    rejections: tuple[str, ...] = field(default_factory=tuple)

    @property
    def accepted(self) -> bool:
        return not self.rejections

    @property
    def summary(self) -> str:
        """Os motivos em português, para a tela e para o registro."""
        return "; ".join(REASON_LABEL.get(item, item) for item in self.rejections)


def _normalized(value: str) -> str:
    return _WHITESPACE.sub(" ", value).strip().lower()


def validate(
    draft: DraftQuestion,
    *,
    material: str,
    board_names: Sequence[str] = (),
) -> Verdict:
    """Confere o rascunho contra o material e contra as regras de forma.

    ``board_names`` são os nomes e siglas de banca conhecidos do catálogo. Eles
    entram por parâmetro porque o catálogo é I/O e este módulo é puro — e porque
    a lista cresce: inventar aqui uma lista fixa de bancas faria a regra
    envelhecer no primeiro concurso novo.
    """
    motivos: list[str] = []
    enunciado = draft.statement.strip()

    if len(enunciado) < MIN_STATEMENT_CHARS:
        motivos.append(RejectionReason.STATEMENT_TOO_SHORT)

    if not (MIN_ALTERNATIVES <= len(draft.alternatives) <= MAX_ALTERNATIVES):
        motivos.append(RejectionReason.ALTERNATIVE_COUNT)

    letras = [item.letter.strip().upper() for item in draft.alternatives]
    if letras != list(LETTERS[: len(letras)]):
        motivos.append(RejectionReason.LETTERS_OUT_OF_ORDER)

    textos = [_normalized(item.content) for item in draft.alternatives]
    if any(not texto for texto in textos):
        motivos.append(RejectionReason.ALTERNATIVE_EMPTY)
    if len(set(textos)) != len(textos):
        motivos.append(RejectionReason.ALTERNATIVE_REPEATED)
    if any(proibida in texto for texto in textos for proibida in _FORBIDDEN_ALTERNATIVES):
        motivos.append(RejectionReason.FORBIDDEN_ALTERNATIVE)

    correta = draft.correct
    if correta is None:
        motivos.append(RejectionReason.NO_SINGLE_ANSWER)

    if not draft.explanation.strip():
        motivos.append(RejectionReason.EXPLANATION_MISSING)
    if any(not (item.feedback or "").strip() for item in draft.alternatives if not item.is_correct):
        motivos.append(RejectionReason.WRONG_WITHOUT_FEEDBACK)

    citacao = draft.quote.strip()
    if len(citacao) < MIN_QUOTE_LENGTH:
        motivos.append(RejectionReason.QUOTE_TOO_SHORT)
    elif normalize_for_match(citacao) not in normalize_for_match(material):
        motivos.append(RejectionReason.QUOTE_NOT_IN_MATERIAL)

    if _claims_provenance(enunciado, board_names):
        motivos.append(RejectionReason.FABRICATED_PROVENANCE)

    if correta is not None and _answer_leaks(enunciado, correta.content):
        motivos.append(RejectionReason.ANSWER_IN_STATEMENT)

    return Verdict(draft=draft, rejections=tuple(motivos))


#: Abaixo deste tamanho, a alternativa correta pode aparecer no enunciado sem
#: entregar nada ("Sim", "Apenas I", "Dez dias"). Exigir ausência total daria
#: descarte por coincidência de palavra curta.
MIN_LEAK_CHARS = 20


def _answer_leaks(statement: str, answer: str) -> bool:
    """Verdadeiro quando o enunciado já contém o texto da alternativa correta.

    A comparação ignora a pontuação das pontas: um ponto final a mais não pode
    ser a diferença entre barrar e deixar passar uma questão cuja resposta está
    escrita no próprio enunciado.
    """
    resposta = _normalized(answer).strip(" .;:,!?")
    if len(resposta) < MIN_LEAK_CHARS:
        return False
    return resposta in _normalized(statement)


def _claims_provenance(statement: str, board_names: Sequence[str]) -> bool:
    """Verdadeiro quando o enunciado se apresenta como questão de prova.

    Três formas são barradas: abrir o enunciado com parênteses contendo um ano
    (o formato clássico de atribuição de prova), citar uma banca conhecida do
    catálogo junto de um ano, e usar uma das frases que afirmam origem em prova
    aplicada. Referência normativa entre parênteses — "(Lei nº 8.112/1990)" —
    continua passando: ela é citação legítima, não procedência inventada. Questão inédita que se
    veste de questão oficial é o pior defeito possível aqui — ela mentiria para
    o candidato sobre o que ele está treinando, e nenhuma revisão humana por
    amostragem pegaria isso de forma confiável.
    """
    texto = _normalized(statement)
    if any(frase in texto for frase in _PROVENANCE_PHRASES):
        return True

    inicio = _LEADING_PARENS.match(statement)
    if inicio is not None:
        dentro = _normalized(inicio.group(1))
        if _YEAR.search(dentro) and not any(palavra in dentro for palavra in _NORMATIVE_WORDS):
            return True

    if not _YEAR.search(statement):
        return False
    return any(
        nome.strip() and _normalized(nome) in texto for nome in board_names if len(nome.strip()) > 2
    )


def summarize(verdicts: Sequence[Verdict]) -> dict[str, int]:
    """Quantos rascunhos cada motivo derrubou. Derivado, nunca acumulado."""
    contagem: dict[str, int] = {}
    for verdict in verdicts:
        for motivo in verdict.rejections:
            contagem[motivo] = contagem.get(motivo, 0) + 1
    return contagem
