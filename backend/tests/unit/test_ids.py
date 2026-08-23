"""Testes dos identificadores públicos."""

from __future__ import annotations

from app.core.ids import is_ulid, new_ulid


def test_ulid_format_and_uniqueness() -> None:
    values = {new_ulid() for _ in range(500)}
    assert len(values) == 500
    assert all(is_ulid(value) for value in values)


def test_ulids_are_time_ordered() -> None:
    first, second = new_ulid(), new_ulid()
    assert first[:10] <= second[:10]


def test_is_ulid_rejects_invalid() -> None:
    assert is_ulid("curto") is False
    assert is_ulid("U" * 26) is False  # 'U' não pertence ao alfabeto Crockford
