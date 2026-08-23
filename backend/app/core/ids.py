"""Identificadores públicos (ULID) — ordenáveis por tempo e seguros de expor."""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32
_ULID_LENGTH = 26


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, remainder = divmod(value, 32)
        chars.append(_ALPHABET[remainder])
    return "".join(reversed(chars))


def new_ulid() -> str:
    """Gera um ULID de 26 caracteres (48 bits de tempo + 80 bits aleatórios)."""
    timestamp_ms = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(timestamp_ms, 10) + _encode(randomness, 16)


def is_ulid(value: str) -> bool:
    return len(value) == _ULID_LENGTH and all(char in _ALPHABET for char in value)
