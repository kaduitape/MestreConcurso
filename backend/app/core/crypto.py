"""Criptografia simétrica para segredos guardados no banco.

A chave é derivada do ``SECRET_KEY`` por HKDF, com contexto próprio para segredos
de provedores de IA. Trocar o ``SECRET_KEY`` invalida os segredos já gravados —
nesse caso as chaves precisam ser cadastradas novamente pelo painel.
"""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings
from app.core.errors import AppError

_CONTEXT = b"mestre-concurso/ai-provider-secrets/v1"


class SecretDecryptionError(AppError):
    status_code = 500
    code = "secret_decryption_failed"
    message = "Não foi possível ler o segredo armazenado. Cadastre a chave novamente."


def _fernet() -> Fernet:
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_CONTEXT,
    ).derive(settings.secret_key.encode())
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret(value: str) -> str:
    """Cifra um segredo para persistência."""
    if not value:
        raise ValueError("Segredo vazio não pode ser cifrado.")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    """Decifra um segredo previamente gravado."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise SecretDecryptionError from exc


def secret_hint(value: str) -> str:
    """Trecho exibível da chave — nunca devolvemos o segredo inteiro pela API."""
    cleaned = value.strip()
    if len(cleaned) <= 8:
        return "•" * len(cleaned)
    return f"{cleaned[:3]}…{cleaned[-4:]}"
