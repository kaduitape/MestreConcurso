"""Curva de níveis.

A curva cresce, mas não explode: o nível 100 precisa ser alcançável por quem
estuda a sério durante uma preparação inteira, e não por quem farma. Nível aqui
reconhece **volume de esforço útil acumulado** — quem mede competência é o rank.

Nenhum nível bloqueia conteúdo de estudo. Ele libera reconhecimento e
personalização, e nada mais.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_LEVEL = 100
BASE_XP = 500
# Cada nível exige ~8% a mais que o anterior — progressão sentida, sem muro.
GROWTH = 1.08


@dataclass(frozen=True, slots=True)
class LevelProgress:
    level: int
    xp_total: int
    xp_into_level: int
    xp_for_next: int | None
    # 0..1 dentro do nível atual.
    ratio: float
    is_max: bool


def xp_for_level(level: int) -> int:
    """XP necessário para sair do nível informado e ir ao seguinte."""
    if level < 1:
        return BASE_XP
    return int(round(BASE_XP * (GROWTH ** (level - 1)) / 10) * 10)


def cumulative_xp(level: int) -> int:
    """XP total acumulado para alcançar o início do nível informado."""
    return sum(xp_for_level(step) for step in range(1, level))


def level_for_xp(xp_total: int) -> LevelProgress:
    """Descobre o nível a partir do XP acumulado."""
    total = max(0, xp_total)
    level = 1
    consumed = 0

    while level < MAX_LEVEL:
        needed = xp_for_level(level)
        if total - consumed < needed:
            break
        consumed += needed
        level += 1

    into = total - consumed
    if level >= MAX_LEVEL:
        return LevelProgress(
            level=MAX_LEVEL,
            xp_total=total,
            xp_into_level=into,
            xp_for_next=None,
            ratio=1.0,
            is_max=True,
        )

    needed = xp_for_level(level)
    return LevelProgress(
        level=level,
        xp_total=total,
        xp_into_level=into,
        xp_for_next=needed,
        ratio=round(into / needed, 4) if needed else 0.0,
        is_max=False,
    )
