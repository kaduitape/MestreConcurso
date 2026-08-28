"""Ligas: comparação entre candidatos do **mesmo contexto**, e desligável.

O item 21 do pedido é explícito: nada de ranking global indiscriminado. Comparar
um candidato a delegado com alguém estudando para nível médio não informa nada —
só desanima. Aqui a liga é o grupo que disputa a mesma coisa, dividido em faixas
de tamanho parecido para que a tabela caiba na tela e faça sentido.

Duas proteções vêm de fábrica:

*Anonimato por padrão.* Ninguém aparece com nome para os outros a menos que
tenha escolhido aparecer. Quem não escolheu vira "Candidato #N" — visível como
posição, não como pessoa.

*Grupo pequeno não vira tabela.* Com menos de cinco participantes, a posição não
diz nada, e a tela informa isso em vez de exibir um pódio de três pessoas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tamanho máximo de uma divisão. Acima disso, o grupo é fatiado.
DIVISION_SIZE = 30

# Abaixo disto não há tabela: posição entre poucos não significa nada.
MIN_LEAGUE_SIZE = 5


@dataclass(frozen=True, slots=True)
class LeagueEntry:
    """Um participante, já filtrado por contexto e por quem não optou por sair."""

    user_key: str
    seasonal_xp: int
    active_days: int = 0
    #: Preenchido só por quem escolheu aparecer com nome.
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class LeagueMember:
    position: int
    label: str
    seasonal_xp: int
    active_days: int
    is_you: bool
    is_named: bool


@dataclass(frozen=True, slots=True)
class League:
    context_label: str
    participants: int
    division_index: int = 0
    division_label: str = ""
    members: list[LeagueMember] = field(default_factory=list)
    your_position: int | None = None
    your_division_position: int | None = None
    empty_reason: str | None = None
    note: str = (
        "A liga compara o esforço de quem disputa o mesmo cargo no período da "
        "temporada. Ela não mede domínio, e sair dela não afeta nada do seu estudo."
    )


def _sorted(entries: list[LeagueEntry]) -> list[LeagueEntry]:
    """Mais XP primeiro; empate desempatado por dias ativos e depois pela chave.

    O último critério não é justiça, é determinismo: sem ele, dois candidatos
    empatados trocariam de posição a cada carregamento da tela.
    """
    return sorted(entries, key=lambda item: (-item.seasonal_xp, -item.active_days, item.user_key))


def build_league(entries: list[LeagueEntry], *, you_key: str, context_label: str) -> League:
    """Monta a divisão do candidato dentro do grupo do mesmo contexto."""
    ranked = _sorted(entries)
    total = len(ranked)

    if total < MIN_LEAGUE_SIZE:
        return League(
            context_label=context_label,
            participants=total,
            empty_reason=(
                f"São {total} candidato(s) neste contexto. A partir de {MIN_LEAGUE_SIZE} a "
                "tabela passa a dizer alguma coisa."
            ),
        )

    positions = {entry.user_key: index + 1 for index, entry in enumerate(ranked)}
    your_position = positions.get(you_key)
    if your_position is None:
        return League(
            context_label=context_label,
            participants=total,
            empty_reason=(
                "Você não está participando desta liga. A comparação é opcional e pode ser "
                "ligada quando quiser."
            ),
        )

    division_index = (your_position - 1) // DIVISION_SIZE
    start = division_index * DIVISION_SIZE
    chunk = ranked[start : start + DIVISION_SIZE]

    members = [
        LeagueMember(
            position=start + offset + 1,
            label=entry.display_name or f"Candidato #{start + offset + 1}",
            seasonal_xp=entry.seasonal_xp,
            active_days=entry.active_days,
            is_you=entry.user_key == you_key,
            is_named=entry.display_name is not None,
        )
        for offset, entry in enumerate(chunk)
    ]

    return League(
        context_label=context_label,
        participants=total,
        division_index=division_index,
        division_label=f"Divisão {division_index + 1}",
        members=members,
        your_position=your_position,
        your_division_position=your_position - start,
    )
