"""Testes das primitivas de segurança."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.errors import InvalidTokenError, ValidationError
from app.core.security import (
    compare_token_hash,
    create_access_token,
    decode_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    validate_password_strength,
    verify_password,
)


def test_hash_password_uses_argon2id_and_is_salted() -> None:
    first = hash_password("Senha@Forte123")
    second = hash_password("Senha@Forte123")
    assert first.startswith("$argon2id$")
    assert first != second, "hashes devem usar salt aleatório"


def test_verify_password() -> None:
    stored = hash_password("Senha@Forte123")
    assert verify_password("Senha@Forte123", stored) is True
    assert verify_password("outra-senha", stored) is False
    assert verify_password("Senha@Forte123", "hash-invalido") is False


@pytest.mark.parametrize(
    "password",
    ["curta1!A", "semmaiuscula1!", "SEMMINUSCULA1!", "SemNumero!!", "SemSimbolo123"],
)
def test_weak_passwords_are_rejected(password: str) -> None:
    with pytest.raises(ValidationError) as exc:
        validate_password_strength(password)
    assert exc.value.code == "weak_password"
    assert exc.value.details["requirements"]


def test_strong_password_is_accepted() -> None:
    validate_password_strength("Senha@Forte123")


def test_access_token_roundtrip() -> None:
    token, expires_at = create_access_token("01ABC", session_id="SESSION1")
    payload = decode_token(token)
    assert payload["sub"] == "01ABC"
    assert payload["sid"] == "SESSION1"
    assert payload["type"] == "access"
    assert expires_at.timestamp() == pytest.approx(payload["exp"], abs=1)


def test_expired_token_is_rejected() -> None:
    token, _ = create_access_token("01ABC", session_id="S1", expires_delta=timedelta(seconds=-10))
    with pytest.raises(InvalidTokenError) as exc:
        decode_token(token)
    assert exc.value.code == "token_expired"


def test_token_type_mismatch_is_rejected() -> None:
    token, _ = create_access_token("01ABC", session_id="S1")
    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type="refresh")


def test_tampered_token_is_rejected() -> None:
    token, _ = create_access_token("01ABC", session_id="S1")
    with pytest.raises(InvalidTokenError):
        decode_token(token[:-2] + "xy")


def test_opaque_token_is_stored_only_as_hash() -> None:
    token = generate_opaque_token()
    digest = hash_opaque_token(token)
    assert token not in digest
    assert len(digest) == 64
    assert compare_token_hash(token, digest) is True
    assert compare_token_hash("outro-token", digest) is False
