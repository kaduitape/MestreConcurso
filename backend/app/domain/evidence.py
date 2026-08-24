"""Verificação de prova: uma citação só vale se existir literalmente no documento.

É este módulo que impede a IA de "promover" a fato aquilo que ela deduziu. A saída
do modelo entra aqui; sai classificada como OFICIAL (citação conferida), INFERIDA
(sem citação válida) ou NÃO LOCALIZADA.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.models.notice_analysis import EvidenceLevel

_WHITESPACE = re.compile(r"\s+")
# Trechos muito curtos casam por acaso; exigimos um mínimo para valer como prova.
MIN_QUOTE_LENGTH = 12


@dataclass(frozen=True, slots=True)
class ChunkRef:
    """O mínimo que o validador precisa saber de um trecho indexado."""

    id: int
    content: str
    page_number: int
    char_start: int


@dataclass(frozen=True, slots=True)
class EvidenceMatch:
    level: str
    chunk_id: int | None = None
    page_number: int | None = None
    quote: str | None = None
    char_start: int | None = None
    char_end: int | None = None

    @property
    def is_official(self) -> bool:
        return self.level == EvidenceLevel.OFFICIAL


def normalize_for_match(text: str) -> str:
    """Normaliza para comparação: sem acento, sem caixa, espaços colapsados."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return _WHITESPACE.sub(" ", without_accents).strip().lower()


def verify_quote(quote: str | None, chunks: list[ChunkRef]) -> EvidenceMatch:
    """Procura a citação nos trechos extraídos do PDF.

    Só quando o texto é encontrado de fato o dado é marcado como OFICIAL — sem isso,
    é rebaixado a inferência, mesmo que o modelo tenha afirmado com convicção.
    """
    if not quote or not quote.strip():
        return EvidenceMatch(level=EvidenceLevel.NOT_FOUND)

    cleaned = quote.strip()
    if len(cleaned) < MIN_QUOTE_LENGTH:
        return EvidenceMatch(level=EvidenceLevel.INFERRED, quote=cleaned)

    needle = normalize_for_match(cleaned)
    for chunk in chunks:
        haystack = normalize_for_match(chunk.content)
        position = haystack.find(needle)
        if position >= 0:
            return EvidenceMatch(
                level=EvidenceLevel.OFFICIAL,
                chunk_id=chunk.id,
                page_number=chunk.page_number,
                quote=cleaned,
                char_start=chunk.char_start + position,
                char_end=chunk.char_start + position + len(needle),
            )

    return EvidenceMatch(level=EvidenceLevel.INFERRED, quote=cleaned)


def coverage_summary(levels: list[str]) -> dict[str, float | int]:
    """Resumo honesto da extração: quanto veio do documento e quanto foi deduzido."""
    total = len(levels)
    counts: dict[str, int] = {
        EvidenceLevel.OFFICIAL.value: 0,
        EvidenceLevel.CONFIRMED.value: 0,
        EvidenceLevel.INFERRED.value: 0,
        EvidenceLevel.NOT_FOUND.value: 0,
    }
    for level in levels:
        if level in counts:
            counts[level] += 1

    proven = counts[EvidenceLevel.OFFICIAL.value] + counts[EvidenceLevel.CONFIRMED.value]
    return {
        "total": total,
        "official": counts[EvidenceLevel.OFFICIAL.value],
        "confirmed": counts[EvidenceLevel.CONFIRMED.value],
        "inferred": counts[EvidenceLevel.INFERRED.value],
        "not_found": counts[EvidenceLevel.NOT_FOUND.value],
        "proven_ratio": round(proven / total, 4) if total else 0.0,
    }
