"""Geração de slugs estáveis para URLs e identificadores legíveis."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(value: str, *, max_length: int = 120) -> str:
    """Converte texto em slug: sem acentos, minúsculo e com hifens."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode().lower()
    slug = _NON_ALNUM.sub("-", ascii_text).strip("-")
    return slug[:max_length].strip("-")


def unique_slug(base: str, taken: set[str], *, max_length: int = 120) -> str:
    """Acrescenta sufixo numérico enquanto o slug já estiver em uso."""
    slug = slugify(base, max_length=max_length) or "item"
    if slug not in taken:
        return slug
    for suffix in range(2, 1000):
        candidate = f"{slug[: max_length - len(str(suffix)) - 1]}-{suffix}"
        if candidate not in taken:
            return candidate
    raise ValueError("Não foi possível gerar um slug único.")
