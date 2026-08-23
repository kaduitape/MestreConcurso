"""Armazenamento de arquivos enviados pelos usuários.

Regras de segurança aplicadas aqui: nome de arquivo gerado pela aplicação (nunca o
do usuário), verificação do conteúdo real (assinatura do arquivo, não a extensão),
limite de tamanho e diretório fora da árvore servida publicamente.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.ids import new_ulid
from app.core.logging import get_logger

logger = get_logger(__name__)

PDF_MAGIC = b"%PDF-"
ALLOWED_MIME_TYPES = {"application/pdf"}


@dataclass(frozen=True, slots=True)
class StoredFile:
    storage_key: str
    size_bytes: int
    checksum_sha256: str
    mime_type: str


class LocalFileStorage:
    """Backend local. O S3/MinIO entra como outra implementação da mesma interface."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_local_path)

    def _resolve(self, storage_key: str) -> Path:
        path = (self.root / storage_key).resolve()
        root = self.root.resolve()
        # Impede que um storage_key manipulado escape do diretório de uploads.
        if not str(path).startswith(str(root)):
            raise ValidationError("Caminho de arquivo inválido.", code="invalid_storage_key")
        return path

    def save(self, content: bytes, *, prefix: str, extension: str) -> StoredFile:
        storage_key = f"{prefix}/{new_ulid()}.{extension.lstrip('.')}"
        path = self._resolve(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(0o600)

        stored = StoredFile(
            storage_key=storage_key,
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            mime_type="application/pdf",
        )
        logger.info("storage.saved", key=storage_key, size=stored.size_bytes)
        return stored

    def read(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.exists():
            raise ValidationError("Arquivo não encontrado no armazenamento.", code="file_missing")
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self._resolve(storage_key)
        path.unlink(missing_ok=True)
        logger.info("storage.deleted", key=storage_key)


def validate_pdf(content: bytes, *, declared_mime: str | None) -> None:
    """Valida tamanho e conteúdo real do PDF antes de qualquer processamento."""
    limit = settings.max_upload_size_mb * 1024 * 1024
    if not content:
        raise ValidationError("Arquivo vazio.", code="empty_file")
    if len(content) > limit:
        raise ValidationError(
            f"O arquivo excede o limite de {settings.max_upload_size_mb} MB.",
            code="file_too_large",
            details={"max_bytes": limit, "size_bytes": len(content)},
        )
    if declared_mime and declared_mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            "Apenas arquivos PDF são aceitos.",
            code="unsupported_media_type",
            details={"received": declared_mime},
        )
    if not content.startswith(PDF_MAGIC):
        # Extensão e content-type são informados pelo cliente: só o conteúdo vale.
        raise ValidationError("O conteúdo enviado não é um PDF válido.", code="invalid_pdf")


def get_storage() -> LocalFileStorage:
    return LocalFileStorage()
