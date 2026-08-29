"""Card compartilhável: os números do candidato, e só o que é verdade.

Um card sai da plataforma e vai para uma rede social, onde ninguém pode conferir
o contexto. Por isso ele é o lugar mais perigoso do produto para um número
inflado — e o mais fácil de inflar.

Três regras, então:

1. **Nenhuma estatística sem amostra mínima.** O que não tem base sai do card
   com o motivo, em vez de aparecer com um número bonito e frágil.
2. **Nenhuma frase de aprovação.** O card não afirma, não sugere e não insinua
   resultado em prova (item 40). Há uma verificação explícita para isso.
3. **O candidato escolhe o que entra.** Nada é publicado por padrão.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Amostras mínimas — as mesmas do rank, para o card não contar outra história.
MIN_ATTEMPTS = 30
MIN_REVIEWS = 20

#: Frases que jamais podem aparecer num card. A verificação é literal e burra
#: de propósito: ela existe para pegar regressão, não para julgar estilo.
FORBIDDEN_FRAGMENTS: tuple[str, ...] = (
    "aprovado",
    "aprovada",
    "aprovação garantida",
    "vai passar",
    "vou passar",
    "passou no concurso",
    "sucesso garantido",
    "chance de aprovação",
)


class ApprovalClaimError(ValueError):
    """O card tentou afirmar algo sobre aprovação."""


@dataclass(frozen=True, slots=True)
class CardStat:
    key: str
    label: str
    value: str
    #: Explica o número em uma linha (amostra, período, origem).
    detail: str


@dataclass(frozen=True, slots=True)
class CardInput:
    display_name: str
    level: int = 1
    rank_name: str = "Ferro"
    xp_total: int = 0
    current_streak: int = 0
    questions_answered: int = 0
    accuracy: float | None = None
    reviews: int = 0
    recall_rate: float | None = None
    coverage: float | None = None
    has_plan: bool = False


@dataclass(frozen=True, slots=True)
class ShareCard:
    display_name: str
    headline: str
    stats: list[CardStat] = field(default_factory=list)
    #: O que ficou de fora, com o motivo — o card não esconde as lacunas.
    omitted: list[str] = field(default_factory=list)
    footer: str = (
        "Números do meu progresso no Game of Concursos. Medem estudo e desempenho, "
        "não resultado em prova."
    )


def assert_no_approval_claim(*texts: str) -> None:
    """Barra qualquer promessa de aprovação antes de o card existir."""
    for text in texts:
        lowered = text.lower()
        for fragment in FORBIDDEN_FRAGMENTS:
            if fragment in lowered:
                raise ApprovalClaimError(
                    f"O card não pode afirmar nada sobre aprovação (trecho: “{fragment}”)."
                )


def build_card(data: CardInput, *, include: set[str] | None = None) -> ShareCard:
    """Monta o card com os campos escolhidos, descartando o que não tem amostra."""
    chosen = include if include is not None else {"level", "rank", "streak", "questions"}
    stats: list[CardStat] = []
    omitted: list[str] = []

    if "level" in chosen:
        stats.append(
            CardStat(
                key="level",
                label="Nível",
                value=str(data.level),
                detail=f"{data.xp_total} XP acumulados em estudo.",
            )
        )

    if "rank" in chosen:
        stats.append(
            CardStat(
                key="rank",
                label="Rank",
                value=data.rank_name,
                detail="Calculado sobre desempenho real; XP não entra na conta.",
            )
        )

    if "streak" in chosen:
        stats.append(
            CardStat(
                key="streak",
                label="Sequência",
                value=f"{data.current_streak} {'dia' if data.current_streak == 1 else 'dias'}",
                detail="Dias seguidos com estudo suficiente para contar.",
            )
        )

    if "questions" in chosen:
        stats.append(
            CardStat(
                key="questions",
                label="Questões",
                value=str(data.questions_answered),
                detail="Questões respondidas na plataforma.",
            )
        )

    if "accuracy" in chosen:
        if data.accuracy is not None and data.questions_answered >= MIN_ATTEMPTS:
            stats.append(
                CardStat(
                    key="accuracy",
                    label="Acerto",
                    value=f"{data.accuracy * 100:.0f}%",
                    detail=f"Sobre {data.questions_answered} respostas.",
                )
            )
        else:
            omitted.append(
                f"Taxa de acerto fica de fora: são precisas {MIN_ATTEMPTS} respostas e há "
                f"{data.questions_answered}."
            )

    if "retention" in chosen:
        if data.recall_rate is not None and data.reviews >= MIN_REVIEWS:
            stats.append(
                CardStat(
                    key="retention",
                    label="Retenção",
                    value=f"{data.recall_rate * 100:.0f}%",
                    detail=f"Sobre {data.reviews} revisões.",
                )
            )
        else:
            omitted.append(
                f"Retenção fica de fora: são precisas {MIN_REVIEWS} revisões e há {data.reviews}."
            )

    if "coverage" in chosen:
        if data.coverage is not None and data.has_plan:
            stats.append(
                CardStat(
                    key="coverage",
                    label="Edital coberto",
                    value=f"{data.coverage * 100:.0f}%",
                    detail="Do tempo planejado que já foi cumprido.",
                )
            )
        else:
            omitted.append("Cobertura fica de fora: não há plano de estudo ativo para medir.")

    headline = f"{data.display_name} · Nível {data.level} · {data.rank_name}"
    card = ShareCard(
        display_name=data.display_name,
        headline=headline,
        stats=stats,
        omitted=omitted,
    )
    assert_no_approval_claim(card.headline, card.footer, *(item.detail for item in card.stats))
    return card
