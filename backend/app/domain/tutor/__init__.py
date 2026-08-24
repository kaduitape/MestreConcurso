"""Mestre IA — preparo da pergunta, fusão da busca e conferência da resposta."""

from app.domain.tutor.answer import (
    ClaimKind,
    ClaimStatus,
    RawClaim,
    VerifiedAnswer,
    VerifiedClaim,
    verify_answer,
)
from app.domain.tutor.fusion import (
    MIN_TOP_SCORE,
    Passage,
    RetrievalOutcome,
    budget_passages,
    fuse,
    lexical_rank,
    reciprocal_rank_fusion,
)
from app.domain.tutor.query import (
    ACRONYMS,
    Intent,
    PreparedQuery,
    detect_intents,
    expand_acronyms,
    normalize,
    prepare,
)

__all__ = [
    "ACRONYMS",
    "MIN_TOP_SCORE",
    "ClaimKind",
    "ClaimStatus",
    "Intent",
    "Passage",
    "PreparedQuery",
    "RawClaim",
    "RetrievalOutcome",
    "VerifiedAnswer",
    "VerifiedClaim",
    "budget_passages",
    "detect_intents",
    "expand_acronyms",
    "fuse",
    "lexical_rank",
    "normalize",
    "prepare",
    "reciprocal_rank_fusion",
    "verify_answer",
]
