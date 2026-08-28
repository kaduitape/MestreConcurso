"""Planos e direitos de uso — e a regra que governa a fase: **limite é dado**.

O pedido é explícito: os recursos e limites **não podem ficar hardcoded**. Aqui
o código define apenas a *forma* de um direito de uso e o catálogo de fábrica
que semeia o banco na primeira subida. Depois disso, quem manda é a tabela:
mudar um limite é um `UPDATE`, não um deploy.

A distinção que sustenta o resto do módulo é entre **não ter direito** e **ter
direito ilimitado**. As duas coisas costumam ser representadas por ``None`` em
sistemas apressados, e aí um bug de comparação libera tudo para quem não pagou.
Aqui `limit=None` significa ilimitado e `enabled=False` significa sem acesso —
campos separados, sem ambiguidade possível.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FeatureKey(StrEnum):
    """Recursos que um plano pode liberar ou limitar.

    Só entram aqui ações que **o candidato executa**. Análise de edital e
    classificação de questões são operações administrativas: colocá-las num
    plano criaria um limite que nunca se aplica — um recurso decorativo, que é
    o que esta plataforma não faz.
    """

    AI_TUTOR = "ai.tutor"
    AI_FLASHCARDS = "ai.flashcards"
    SIMULATIONS = "simulations"
    CHALLENGES = "challenges"
    ANALYTICS = "analytics"
    SHARE_CARDS = "share_cards"


class Period(StrEnum):
    """Janela em que um limite se renova."""

    DAY = "DAY"
    MONTH = "MONTH"
    #: Sem renovação: o limite vale para a assinatura inteira.
    TOTAL = "TOTAL"


FEATURE_LABEL: dict[str, str] = {
    FeatureKey.AI_TUTOR: "Perguntas ao Mestre IA",
    FeatureKey.AI_FLASHCARDS: "Flashcards gerados por IA",
    FeatureKey.SIMULATIONS: "Simulados",
    FeatureKey.CHALLENGES: "Rodadas de desafio",
    FeatureKey.ANALYTICS: "Analytics e Mestre Score",
    FeatureKey.SHARE_CARDS: "Cards compartilháveis",
}


@dataclass(frozen=True, slots=True)
class Entitlement:
    """O que um plano concede em um recurso."""

    feature: str
    #: Falso = sem acesso. Diferente de acesso ilimitado.
    enabled: bool = True
    #: ``None`` = sem teto. Só faz sentido com ``enabled`` verdadeiro.
    limit: int | None = None
    period: str = Period.MONTH

    @property
    def is_unlimited(self) -> bool:
        return self.enabled and self.limit is None

    @property
    def label(self) -> str:
        return FEATURE_LABEL.get(self.feature, self.feature)

    def describe(self) -> str:
        if not self.enabled:
            return f"{self.label}: não incluído neste plano."
        if self.limit is None:
            return f"{self.label}: sem limite."
        janela = {"DAY": "por dia", "MONTH": "por mês", "TOTAL": "no total"}[self.period]
        return f"{self.label}: até {self.limit} {janela}."


@dataclass(frozen=True, slots=True)
class PlanSpec:
    """Plano de fábrica. A tabela `plans` vence sobre isto."""

    slug: str
    name: str
    description: str
    price_cents: int
    #: Dias de teste. Zero significa sem teste.
    trial_days: int = 0
    is_public: bool = True
    sort_order: int = 0
    entitlements: tuple[Entitlement, ...] = ()

    @property
    def is_free(self) -> bool:
        return self.price_cents == 0


DEFAULT_PLANS: tuple[PlanSpec, ...] = (
    PlanSpec(
        slug="gratuito",
        name="Gratuito",
        description=(
            "Todo o conteúdo de estudo, com a IA em volume reduzido. Nenhuma "
            "funcionalidade de estudo fica atrás do pagamento."
        ),
        price_cents=0,
        sort_order=0,
        entitlements=(
            Entitlement(FeatureKey.AI_TUTOR, limit=10, period=Period.MONTH),
            Entitlement(FeatureKey.AI_FLASHCARDS, limit=20, period=Period.MONTH),
            Entitlement(FeatureKey.SIMULATIONS, limit=4, period=Period.MONTH),
            Entitlement(FeatureKey.CHALLENGES, limit=3, period=Period.DAY),
            Entitlement(FeatureKey.ANALYTICS),
            Entitlement(FeatureKey.SHARE_CARDS, limit=3, period=Period.MONTH),
        ),
    ),
    PlanSpec(
        slug="mestre",
        name="Mestre",
        description="A plataforma inteira, com a IA em volume de uso diário.",
        price_cents=4990,
        trial_days=7,
        sort_order=1,
        entitlements=(
            Entitlement(FeatureKey.AI_TUTOR, limit=300, period=Period.MONTH),
            Entitlement(FeatureKey.AI_FLASHCARDS, limit=500, period=Period.MONTH),
            Entitlement(FeatureKey.SIMULATIONS),
            Entitlement(FeatureKey.CHALLENGES),
            Entitlement(FeatureKey.ANALYTICS),
            Entitlement(FeatureKey.SHARE_CARDS),
        ),
    ),
    PlanSpec(
        slug="mestre-anual",
        name="Mestre anual",
        description="O plano Mestre com pagamento anual.",
        price_cents=47900,
        trial_days=7,
        sort_order=2,
        entitlements=(
            Entitlement(FeatureKey.AI_TUTOR, limit=300, period=Period.MONTH),
            Entitlement(FeatureKey.AI_FLASHCARDS, limit=500, period=Period.MONTH),
            Entitlement(FeatureKey.SIMULATIONS),
            Entitlement(FeatureKey.CHALLENGES),
            Entitlement(FeatureKey.ANALYTICS),
            Entitlement(FeatureKey.SHARE_CARDS),
        ),
    ),
)

PLANS_BY_SLUG: dict[str, PlanSpec] = {item.slug: item for item in DEFAULT_PLANS}

#: O plano de quem não assinou nada. Existe para que "sem assinatura" tenha
#: direitos definidos, em vez de virar uma sequência de `if` espalhados.
FALLBACK_PLAN_SLUG = "gratuito"


@dataclass(frozen=True, slots=True)
class EntitlementSet:
    """Os direitos vigentes de um candidato, já resolvidos."""

    plan_slug: str
    plan_name: str
    items: dict[str, Entitlement] = field(default_factory=dict)

    def get(self, feature: str) -> Entitlement:
        """Recurso desconhecido é negado, nunca liberado por omissão."""
        return self.items.get(feature, Entitlement(feature=feature, enabled=False, limit=0))
