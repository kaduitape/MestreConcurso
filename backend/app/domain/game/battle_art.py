"""Quais peças de arte a Batalha RPG aceita — e o que acontece sem elas.

O catálogo é **derivado do que já existe**: as espécies do bestiário, as classes
do guerreiro e um cenário por espécie. Nada aqui inventa uma peça que a batalha
não usaria.

A regra que sustenta o módulo: **toda peça é opcional**. Sem arte cadastrada a
tela desenha a silhueta em SVG, como sempre desenhou. Uma tela que só funciona
depois de alguém subir dez imagens seria uma tela quebrada esperando favor.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.game.battle import BESTIARY, CLASSES


class AssetKind(StrEnum):
    MONSTER = "MONSTER"
    PLAYER = "PLAYER"
    SCENERY = "SCENERY"


#: Chave usada quando não há peça específica para aquela espécie ou classe.
DEFAULT_SLUG = "default"


@dataclass(frozen=True, slots=True)
class AssetSlot:
    """Um lugar de arte: o que é, para quem, e o que aparece sem ele."""

    kind: str
    slug: str
    label: str
    #: O que a tela faz enquanto ninguém cadastrar nada aqui.
    fallback: str


def catalogue() -> list[AssetSlot]:
    """Os lugares de arte que a batalha sabe usar, na ordem em que ela os usa."""
    slots: list[AssetSlot] = [
        AssetSlot(
            AssetKind.PLAYER,
            DEFAULT_SLUG,
            "Guerreiro — arte padrão",
            "Usa o personagem do Estúdio de Treinamento.",
        )
    ]
    slots += [
        AssetSlot(
            AssetKind.PLAYER,
            item.slug,
            f"Guerreiro — {item.name}",
            "Usa a arte padrão do guerreiro.",
        )
        for item in CLASSES
    ]
    slots += [
        AssetSlot(
            AssetKind.MONSTER,
            item.slug,
            f"Monstro — {item.name}",
            "Usa a silhueta em SVG desta espécie.",
        )
        for item in BESTIARY
    ]
    slots.append(
        AssetSlot(
            AssetKind.SCENERY,
            DEFAULT_SLUG,
            "Cenário — padrão",
            "Usa o fundo do tema, sem imagem.",
        )
    )
    slots += [
        AssetSlot(
            AssetKind.SCENERY,
            item.slug,
            f"Cenário — {item.name}",
            "Usa o cenário padrão.",
        )
        for item in BESTIARY
    ]
    return slots


CATALOGUE_BY_KEY: dict[tuple[str, str], AssetSlot] = {
    (item.kind, item.slug): item for item in catalogue()
}


def is_known(kind: str, slug: str) -> bool:
    """Chave fora do catálogo não é cadastrável: arte solta ninguém veria."""
    return (kind, slug) in CATALOGUE_BY_KEY


def resolve(assets: dict[tuple[str, str], str], kind: str, slug: str) -> str | None:
    """A URL da peça, caindo para o padrão da categoria e depois para nada.

    A cadeia é curta de propósito: peça da espécie, peça padrão, silhueta. Mais
    níveis do que isso tornariam impossível responder "por que apareceu isto?".
    """
    return assets.get((kind, slug)) or assets.get((kind, DEFAULT_SLUG))
