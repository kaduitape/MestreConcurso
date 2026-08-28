"""Temporadas: um período fechado, com placar próprio e recompensa declarada.

A temporada mede **esforço no período** — XP acumulado entre duas datas. Ela não
mede domínio, e a interface diz isso: quem quiser saber se está aprendendo olha o
rank, que continua saindo de desempenho e não é tocado por nada daqui.

Não há recompensa aleatória (item 34 do pedido). Cada prêmio tem critério
verificável e **utilidade escrita**, e nenhum deles desbloqueia conteúdo de
estudo (itens 3 e 24): temporada não é paywall com outro nome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Oito semanas: longo o bastante para o esforço aparecer, curto o bastante para
# recomeçar não parecer inalcançável.
SEASON_LENGTH_DAYS = 56

# Abaixo disso a participação não rende selo: um dia solto não é temporada.
MIN_QUALIFIED_DAYS = 5

# Quantas posições do topo da divisão recebem o escudo.
SHIELD_POSITIONS = 3


@dataclass(frozen=True, slots=True)
class SeasonReward:
    slug: str
    label: str
    #: Para que serve, em texto. Prêmio sem utilidade declarada não entra.
    utility: str
    #: O que precisa acontecer para ganhá-lo.
    criterion: str


REWARDS: tuple[SeasonReward, ...] = (
    SeasonReward(
        slug="escudo-extra",
        label="Escudo de sequência",
        utility="Protege um dia perdido da sua sequência no mês seguinte.",
        criterion=f"Terminar a temporada entre os {SHIELD_POSITIONS} primeiros da sua divisão.",
    ),
    SeasonReward(
        slug="selo-temporada",
        label="Selo da temporada",
        utility=(
            "Marca visual no seu perfil. Não altera o rank, não rende XP e não "
            "desbloqueia nenhum conteúdo."
        ),
        criterion=f"Concluir a temporada com pelo menos {MIN_QUALIFIED_DAYS} dias qualificados.",
    ),
)

REWARDS_BY_SLUG: dict[str, SeasonReward] = {item.slug: item for item in REWARDS}


@dataclass(frozen=True, slots=True)
class SeasonWindow:
    name: str
    starts_on: date
    ends_on: date

    def contains(self, day: date) -> bool:
        return self.starts_on <= day <= self.ends_on

    def total_days(self) -> int:
        return (self.ends_on - self.starts_on).days + 1

    def days_left(self, today: date) -> int:
        return max(0, (self.ends_on - today).days)

    def progress(self, today: date) -> float:
        """0 antes de começar, 1 depois de encerrada."""
        total = self.total_days()
        if total <= 0 or today < self.starts_on:
            return 0.0
        elapsed = (today - self.starts_on).days + 1
        return round(min(1.0, elapsed / total), 4)


@dataclass(frozen=True, slots=True)
class SeasonStanding:
    """O que o candidato fez na temporada. Tudo somado do razão de XP."""

    seasonal_xp: int = 0
    qualified_days: int = 0
    questions: int = 0
    challenges: int = 0
    position: int | None = None
    participants: int = 0


@dataclass(frozen=True, slots=True)
class SeasonOutcome:
    standing: SeasonStanding
    rewards: list[SeasonReward] = field(default_factory=list)
    #: Prêmios que existem mas não foram alcançados, com o critério à vista.
    missed: list[SeasonReward] = field(default_factory=list)
    note: str = (
        "A temporada mede o esforço do período. Quem mede aprendizado é o rank, "
        "e nada da temporada entra nele."
    )


def rewards_for(standing: SeasonStanding) -> SeasonOutcome:
    """Confere os prêmios por critério verificável — nunca por sorteio."""
    earned: list[SeasonReward] = []
    missed: list[SeasonReward] = []

    shield = REWARDS_BY_SLUG["escudo-extra"]
    if standing.position is not None and standing.position <= SHIELD_POSITIONS:
        earned.append(shield)
    else:
        missed.append(shield)

    badge = REWARDS_BY_SLUG["selo-temporada"]
    if standing.qualified_days >= MIN_QUALIFIED_DAYS:
        earned.append(badge)
    else:
        missed.append(badge)

    return SeasonOutcome(standing=standing, rewards=earned, missed=missed)
