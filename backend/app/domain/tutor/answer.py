"""Conferência da resposta do modelo: cada afirmação precisa de origem resolvível.

O modelo devolve a resposta quebrada em afirmações. Cada afirmação factual traz a
citação literal do trecho que a sustenta. Aqui a citação é conferida **contra o
texto recuperado**, com a mesma normalização usada na Fase 3.

O que não passa não é apagado em silêncio: vira uma afirmação marcada como
`SEM_ORIGEM`, e a interface a exibe como tal. Se nenhuma afirmação factual
sobreviver, a resposta inteira vira uma recusa explícita.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.evidence import MIN_QUOTE_LENGTH, normalize_for_match
from app.domain.tutor.fusion import Passage


class ClaimKind(StrEnum):
    FACT = "FACT"  # afirmação factual: exige citação conferida
    GUIDANCE = "GUIDANCE"  # orientação de estudo: não é fato sobre o edital
    STATISTIC = "STATISTIC"  # número calculado pelo Python e injetado no prompt


class ClaimStatus(StrEnum):
    CITED = "CITED"  # citação conferida no trecho
    COMPUTED = "COMPUTED"  # número veio do Python, não do modelo
    UNSOURCED = "UNSOURCED"  # afirmação factual sem origem conferida


@dataclass(frozen=True, slots=True)
class RawClaim:
    """Uma afirmação como o modelo a devolveu."""

    text: str
    kind: str = ClaimKind.FACT
    quote: str | None = None


@dataclass(frozen=True, slots=True)
class VerifiedClaim:
    text: str
    kind: str
    status: str
    quote: str | None = None
    chunk_id: int | None = None
    page_number: int | None = None
    document_title: str | None = None
    # Por que a afirmação não pôde ser confirmada, quando for o caso.
    note: str | None = None

    @property
    def is_resolvable(self) -> bool:
        return self.status in {ClaimStatus.CITED, ClaimStatus.COMPUTED}


@dataclass(frozen=True, slots=True)
class VerifiedAnswer:
    claims: list[VerifiedClaim] = field(default_factory=list)
    is_refusal: bool = False
    refusal_reason: str | None = None

    @property
    def cited_count(self) -> int:
        return sum(1 for claim in self.claims if claim.status == ClaimStatus.CITED)

    @property
    def unsourced_count(self) -> int:
        return sum(1 for claim in self.claims if claim.status == ClaimStatus.UNSOURCED)

    @property
    def text(self) -> str:
        return " ".join(claim.text for claim in self.claims).strip()

    def coverage(self) -> dict[str, int | float]:
        """Quanto da resposta tem origem resolvível — número, não impressão."""
        facts = [claim for claim in self.claims if claim.kind == ClaimKind.FACT]
        resolvable = sum(1 for claim in facts if claim.is_resolvable)
        return {
            "claims": len(self.claims),
            "facts": len(facts),
            "resolved": resolvable,
            "unsourced": len(facts) - resolvable,
            "ratio": round(resolvable / len(facts), 4) if facts else 1.0,
        }


def _find(quote: str, passages: list[Passage]) -> Passage | None:
    needle = normalize_for_match(quote)
    for passage in passages:
        if needle in normalize_for_match(passage.content):
            return passage
    return None


def verify_answer(
    claims: list[RawClaim], passages: list[Passage], *, refusal: str | None = None
) -> VerifiedAnswer:
    """Confere cada afirmação contra os trechos que realmente foram recuperados."""
    if refusal:
        return VerifiedAnswer(is_refusal=True, refusal_reason=refusal)

    verified: list[VerifiedClaim] = []
    for claim in claims:
        text = claim.text.strip()
        if not text:
            continue

        if claim.kind == ClaimKind.STATISTIC:
            # O número já veio calculado do Python; o modelo apenas o redigiu.
            verified.append(VerifiedClaim(text=text, kind=claim.kind, status=ClaimStatus.COMPUTED))
            continue

        if claim.kind == ClaimKind.GUIDANCE:
            verified.append(VerifiedClaim(text=text, kind=claim.kind, status=ClaimStatus.COMPUTED))
            continue

        quote = (claim.quote or "").strip()
        if len(quote) < MIN_QUOTE_LENGTH:
            verified.append(
                VerifiedClaim(
                    text=text,
                    kind=ClaimKind.FACT,
                    status=ClaimStatus.UNSOURCED,
                    note="sem citação suficiente para conferir",
                )
            )
            continue

        passage = _find(quote, passages)
        if passage is None:
            # A citação não existe no material recuperado: pode ter sido inventada.
            verified.append(
                VerifiedClaim(
                    text=text,
                    kind=ClaimKind.FACT,
                    status=ClaimStatus.UNSOURCED,
                    quote=quote,
                    note="a citação não foi localizada no material recuperado",
                )
            )
            continue

        verified.append(
            VerifiedClaim(
                text=text,
                kind=ClaimKind.FACT,
                status=ClaimStatus.CITED,
                quote=quote,
                chunk_id=passage.chunk_id,
                page_number=passage.page_number,
                document_title=passage.document_title,
            )
        )

    facts = [claim for claim in verified if claim.kind == ClaimKind.FACT]
    if facts and all(claim.status == ClaimStatus.UNSOURCED for claim in facts):
        # Nenhuma afirmação factual se sustentou: responder assim mesmo seria pior
        # do que admitir que não há base.
        return VerifiedAnswer(
            claims=verified,
            is_refusal=True,
            refusal_reason=(
                "Não consegui sustentar nenhuma afirmação desta resposta no seu material. "
                "Prefiro não responder a arriscar uma informação sem origem."
            ),
        )

    return VerifiedAnswer(claims=verified)
