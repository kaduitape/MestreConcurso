"""Validação e armazenamento de arquivos enviados."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.services.storage import LocalFileStorage, validate_pdf

PDF = b"%PDF-1.7\nconteudo\n%%EOF"


def test_accepts_real_pdf() -> None:
    validate_pdf(PDF, declared_mime="application/pdf")


def test_rejects_file_that_only_pretends_to_be_pdf() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_pdf(b"<?php system($_GET[0]); ?>", declared_mime="application/pdf")
    assert exc.value.code == "invalid_pdf"


def test_rejects_unsupported_mime() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_pdf(PDF, declared_mime="image/png")
    assert exc.value.code == "unsupported_media_type"


def test_rejects_empty_file() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_pdf(b"", declared_mime="application/pdf")
    assert exc.value.code == "empty_file"


def test_rejects_oversized_file(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import storage as module

    monkeypatch.setattr(module.settings, "max_upload_size_mb", 1)
    with pytest.raises(ValidationError) as exc:
        validate_pdf(PDF + b"x" * (1024 * 1024), declared_mime="application/pdf")
    assert exc.value.code == "file_too_large"


def test_storage_roundtrip(tmp_path: Path) -> None:
    storage = LocalFileStorage(str(tmp_path))
    stored = storage.save(PDF, prefix="notices", extension="pdf")

    assert stored.storage_key.startswith("notices/")
    assert stored.size_bytes == len(PDF)
    assert storage.read(stored.storage_key) == PDF

    storage.delete(stored.storage_key)
    with pytest.raises(ValidationError):
        storage.read(stored.storage_key)


def test_storage_blocks_path_traversal(tmp_path: Path) -> None:
    storage = LocalFileStorage(str(tmp_path))
    with pytest.raises(ValidationError) as exc:
        storage.read("../../etc/passwd")
    assert exc.value.code == "invalid_storage_key"


def test_saved_file_is_not_world_readable(tmp_path: Path) -> None:
    storage = LocalFileStorage(str(tmp_path))
    stored = storage.save(PDF, prefix="notices", extension="pdf")
    mode = (tmp_path / stored.storage_key).stat().st_mode & 0o777
    assert mode == 0o600
