"""Fusão dos resultados de busca e a decisão de "não há base suficiente".

A recuperação combina duas listas — semântica (vetores) e léxica (palavras) —
com Reciprocal Rank Fusion. RRF usa só a *posição* de cada resultado, então não
exige que os dois scores estejam na mesma escala, que é justamente o problema de
misturar distância de cosseno com contagem de termos.

A porta de corte é explícita: sem trecho suficientemente próximo, a resposta
correta é dizer que não há base — nunca completar de memória.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Constante clássica do RRF; amortece a vantagem das primeiras posições.
RRF_K = 60

# Abaixo disto, o melhor trecho recuperado não sustenta uma resposta.
MIN_TOP_SCORE = 0.35
# E é preciso ter pelo menos este número de trechos aproveitáveis.
MIN_PASSAGES = 1


@dataclass(frozen=True, slots=True)
class Passage:
    """Um trecho recuperado, com tudo o que a citação vai precisar."""

    chunk_id: int
    content: str
    page_number: int
    char_start: int
    document_id: int
    document_title: str
    score: float = 0.0
    section: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalOutcome:
    passages: list[Passage] = field(default_factory=list)
    top_score: float = 0.0
    dense_count: int = 0
    lexical_count: int = 0
    # Motivo pelo qual não há base — a resposta ao candidato sai daqui.
    blocked_reason: str | None = None

    @property
    def has_base(self) -> bool:
        return self.blocked_reason is None and len(self.passages) >= MIN_PASSAGES


def reciprocal_rank_fusion(ranked_lists: list[list[int]], *, k: int = RRF_K) -> dict[int, float]:
    """Score de fusão por identificador de trecho, a partir das posições."""
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for position, chunk_id in enumerate(ranked):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + position + 1)
    return scores


def lexical_rank(keywords: list[str], candidates: list[Passage]) -> list[int]:
    """Ordena por quantos termos da pergunta aparecem no trecho.

    É busca léxica simples e local — suficiente para complementar a semântica sem
    depender de um índice BM25 externo, e honesta quanto ao que faz.
    """
    if not keywords:
        return []
    scored: list[tuple[int, int, int]] = []
    for passage in candidates:
        haystack = passage.content.lower()
        hits = sum(1 for word in keywords if word in haystack)
        if hits:
            scored.append((hits, -passage.chunk_id, passage.chunk_id))
    scored.sort(reverse=True)
    return [item[2] for item in scored]


def fuse(
    *,
    dense: list[Passage],
    lexical_order: list[int],
    limit: int = 8,
    min_top_score: float = MIN_TOP_SCORE,
) -> RetrievalOutcome:
    """Funde as duas listas e decide se há base para responder."""
    if not dense and not lexical_order:
        return RetrievalOutcome(
            blocked_reason=(
                "Não localizei nada sobre isso na sua base indexada. "
                "Envie o edital ou material relacionado para que eu possa responder com origem."
            )
        )

    top_score = max((item.score for item in dense), default=0.0)
    if dense and top_score < min_top_score:
        return RetrievalOutcome(
            top_score=top_score,
            dense_count=len(dense),
            lexical_count=len(lexical_order),
            blocked_reason=(
                "Encontrei trechos, mas nenhum próximo o suficiente da sua pergunta para eu "
                "afirmar algo com segurança. Prefiro dizer isso a arriscar uma resposta."
            ),
        )

    by_id = {item.chunk_id: item for item in dense}
    dense_order = [item.chunk_id for item in dense]
    fused = reciprocal_rank_fusion([dense_order, lexical_order])

    ordered = sorted(fused.items(), key=lambda item: (-item[1], item[0]))
    passages = [by_id[chunk_id] for chunk_id, _ in ordered if chunk_id in by_id][:limit]

    if not passages:
        return RetrievalOutcome(
            top_score=top_score,
            dense_count=len(dense),
            lexical_count=len(lexical_order),
            blocked_reason="Nenhum trecho recuperado pôde ser usado como origem.",
        )

    return RetrievalOutcome(
        passages=passages,
        top_score=top_score,
        dense_count=len(dense),
        lexical_count=len(lexical_order),
    )


def budget_passages(passages: list[Passage], *, max_chars: int) -> list[Passage]:
    """Corta o contexto pelo orçamento, mantendo a ordem de relevância.

    Nenhum trecho entra pela metade: um recorte no meio de uma frase quebraria a
    conferência literal da citação depois.
    """
    selected: list[Passage] = []
    used = 0
    for passage in passages:
        size = len(passage.content)
        if used + size > max_chars and selected:
            break
        selected.append(passage)
        used += size
    return selected
