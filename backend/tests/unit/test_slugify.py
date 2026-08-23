"""Testes da geração de slugs."""

from __future__ import annotations

import pytest

from app.core.slugify import slugify, unique_slug


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Direito Constitucional", "direito-constitucional"),
        ("Raciocínio Lógico", "raciocinio-logico"),
        ("  PCDF — Agente 2026 ", "pcdf-agente-2026"),
        ("Língua Portuguesa/Redação", "lingua-portuguesa-redacao"),
    ],
)
def test_slugify(value: str, expected: str) -> None:
    assert slugify(value) == expected


def test_unique_slug_adds_suffix() -> None:
    taken = {"portugues", "portugues-2"}
    assert unique_slug("Português", taken) == "portugues-3"


def test_unique_slug_returns_base_when_free() -> None:
    assert unique_slug("Informática", set()) == "informatica"
