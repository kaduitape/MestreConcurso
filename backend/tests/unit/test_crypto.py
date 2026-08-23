"""Testes da criptografia de segredos."""

from __future__ import annotations

import pytest

from app.core.crypto import (
    SecretDecryptionError,
    decrypt_secret,
    encrypt_secret,
    secret_hint,
)


def test_encrypt_decrypt_roundtrip() -> None:
    secret = "sk-proj-chave-de-exemplo-1234567890"
    token = encrypt_secret(secret)
    assert secret not in token
    assert decrypt_secret(token) == secret


def test_ciphertext_is_not_deterministic() -> None:
    secret = "sk-proj-chave-de-exemplo-1234567890"
    assert encrypt_secret(secret) != encrypt_secret(secret)


def test_tampered_ciphertext_is_rejected() -> None:
    token = encrypt_secret("sk-proj-chave-de-exemplo-1234567890")
    with pytest.raises(SecretDecryptionError):
        decrypt_secret(token[:-4] + "AAAA")


def test_empty_secret_is_rejected() -> None:
    with pytest.raises(ValueError, match="vazio"):
        encrypt_secret("")


def test_hint_shows_only_the_edges() -> None:
    assert secret_hint("sk-proj-abcdefghijklmnop") == "sk-…mnop"
    assert secret_hint("curta") == "•••••"
