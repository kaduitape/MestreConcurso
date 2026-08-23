"""Taxonomia de erros da aplicação e envelope único de resposta."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Erro de negócio conhecido. Sempre vira resposta HTTP previsível."""

    status_code: int = 400
    code: str = "bad_request"
    message: str = "Requisição inválida."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self, request_id: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "request_id": request_id,
            }
        }


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Dados inválidos."


class AuthenticationError(AppError):
    status_code = 401
    code = "unauthenticated"
    message = "Credenciais inválidas ou ausentes."


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    message = "E-mail ou senha incorretos."


class AccountLockedError(AuthenticationError):
    status_code = 423
    code = "account_locked"
    message = "Conta temporariamente bloqueada por excesso de tentativas."


class EmailNotVerifiedError(AuthenticationError):
    status_code = 403
    code = "email_not_verified"
    message = "Confirme seu e-mail antes de entrar."


class AccountInactiveError(AuthenticationError):
    status_code = 403
    code = "account_inactive"
    message = "Esta conta não está ativa."


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"
    message = "Você não tem permissão para executar esta ação."


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Recurso não encontrado."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Conflito com o estado atual do recurso."


class EmailAlreadyRegisteredError(ConflictError):
    code = "email_already_registered"
    message = "Já existe uma conta com este e-mail."


class InvalidTokenError(AppError):
    status_code = 400
    code = "invalid_token"
    message = "Token inválido ou expirado."


class RateLimitExceededError(AppError):
    status_code = 429
    code = "rate_limit_exceeded"
    message = "Muitas requisições. Tente novamente em instantes."

    def __init__(self, retry_after: int, **kwargs: Any) -> None:
        super().__init__(details={"retry_after_seconds": retry_after}, **kwargs)
        self.retry_after = retry_after


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"
    message = "Serviço temporariamente indisponível."
