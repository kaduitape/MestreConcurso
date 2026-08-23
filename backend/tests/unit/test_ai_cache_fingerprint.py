"""A impressão digital do cache precisa ser estável e sensível ao conteúdo."""

from __future__ import annotations

from app.services.ai_cache import fingerprint


def _key(**kwargs: object) -> str:
    base = {
        "feature": "board.profile",
        "model_slug": "gpt-4o-mini",
        "prompt_version": "v1",
        "payload": {"board": "cespe", "subject": "penal"},
    }
    base.update(kwargs)
    return fingerprint(**base)  # type: ignore[arg-type]


def test_same_input_produces_same_key() -> None:
    assert _key() == _key()


def test_key_ignores_dict_ordering() -> None:
    assert _key(payload={"subject": "penal", "board": "cespe"}) == _key()


def test_key_changes_with_model_and_prompt_version() -> None:
    assert _key(model_slug="gpt-4o") != _key()
    assert _key(prompt_version="v2") != _key()


def test_key_changes_with_payload() -> None:
    assert _key(payload={"board": "fgv", "subject": "penal"}) != _key()
