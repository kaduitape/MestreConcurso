"""Primitivas de segurança: hash de senha, JWT e tokens opacos."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import InvalidTokenError, ValidationError

TokenType = Literal["access", "refresh", "ws_ticket"]

_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SYMBOL = re.compile(r"[^A-Za-z0-9]")


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Gera hash Argon2id da senha."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica a senha em tempo constante (Argon2)."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def validate_password_strength(password: str) -> None:
    """Política mínima de senha. Levanta ValidationError com a lista de problemas."""
    problems: list[str] = []
    if len(password) < settings.password_min_length:
        problems.append(f"mínimo de {settings.password_min_length} caracteres")
    if not _UPPER.search(password):
        problems.append("ao menos uma letra maiúscula")
    if not _LOWER.search(password):
        problems.append("ao menos uma letra minúscula")
    if not _DIGIT.search(password):
        problems.append("ao menos um número")
    if not _SYMBOL.search(password):
        problems.append("ao menos um símbolo")
    if problems:
        raise ValidationError(
            "A senha não atende à política de segurança.",
            code="weak_password",
            details={"requirements": problems},
        )


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_access_token(
    subject: str,
    *,
    session_id: str,
    scopes: list[str] | None = None,
    expires_delta: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """Cria o access token. Retorna (token, expiração)."""
    now = datetime.now(UTC)
    expires_at = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject,
        "sid": session_id,
        "type": "access",
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(16),
        "scopes": scopes or [],
    }
    if extra:
        payload.update(extra)
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_token(token: str, *, expected_type: TokenType = "access") -> dict[str, Any]:
    """Decodifica e valida um JWT. Levanta InvalidTokenError em qualquer falha."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token expirado.", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token inválido.") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError("Tipo de token inesperado.")
    return payload


# --------------------------------------------------------------------------- #
# Tokens opacos (refresh, verificação de e-mail, reset de senha)
# --------------------------------------------------------------------------- #
def generate_opaque_token(nbytes: int = 48) -> str:
    """Token aleatório seguro, entregue ao cliente uma única vez."""
    return secrets.token_urlsafe(nbytes)


def hash_opaque_token(token: str) -> str:
    """Guarda apenas o hash: vazamento do banco não permite reuso do token."""
    return hashlib.sha256(f"{token}{settings.secret_key}".encode()).hexdigest()


def compare_token_hash(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_opaque_token(token), token_hash)
