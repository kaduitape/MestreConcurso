"""Dependências compartilhadas da API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    AccountInactiveError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitExceededError,
)
from app.core.logging import user_id_ctx
from app.core.rate_limit import RateLimitRule, check_rate_limit
from app.core.security import decode_token
from app.db.session import get_db_session
from app.models.audit import AuditAction
from app.models.user import User
from app.models.user_session import UserSession
from app.repositories.user import UserRepository
from app.repositories.user_session import UserSessionRepository
from app.services.audit import AuditService
from app.services.auth import RequestContext

bearer_scheme = HTTPBearer(auto_error=False, description="Access token JWT")

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_client_ip(request: Request) -> str | None:
    """IP do cliente considerando proxy reverso confiável."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def get_request_context(request: Request) -> RequestContext:
    return RequestContext(
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
    )


RequestCtx = Annotated[RequestContext, Depends(get_request_context)]


class AuthenticatedUser:
    """Usuário autenticado junto da sessão que originou o token."""

    __slots__ = ("session", "user")

    def __init__(self, user: User, session: UserSession) -> None:
        self.user = user
        self.session = session


async def get_current_principal(
    request: Request,
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedUser:
    """Valida o access token e confirma que a sessão continua ativa."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Token de acesso ausente.")

    payload = decode_token(credentials.credentials, expected_type="access")
    user_public_id = str(payload["sub"])
    session_public_id = str(payload.get("sid", ""))

    users = UserRepository(db)
    user = await users.get_by_public_id(user_public_id)
    if user is None:
        raise AuthenticationError("Usuário não encontrado.")
    if not user.is_active:
        raise AccountInactiveError

    sessions = UserSessionRepository(db)
    user_session = await sessions.get_by_public_id(session_public_id, user.id)
    if user_session is None or user_session.revoked_at is not None:
        raise AuthenticationError("Sessão encerrada. Faça login novamente.", code="session_revoked")
    expires_at = user_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise AuthenticationError("Sessão expirada. Faça login novamente.")

    user_id_ctx.set(user.public_id)
    request.state.user = user
    return AuthenticatedUser(user, user_session)


CurrentPrincipal = Annotated[AuthenticatedUser, Depends(get_current_principal)]


async def get_current_user(principal: CurrentPrincipal) -> User:
    return principal.user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permissions(
    *required: str,
) -> Callable[[AuthenticatedUser, AsyncSession, Request], Awaitable[User]]:
    """Dependência de autorização: exige todas as permissões informadas."""

    async def dependency(principal: CurrentPrincipal, db: DbSession, request: Request) -> User:
        user = principal.user
        missing = [perm for perm in required if not user.has_permission(perm)]
        if missing:
            await AuditService(db).record(
                AuditAction.PERMISSION_DENIED,
                actor=user,
                actor_ip=get_client_ip(request),
                resource_type="endpoint",
                resource_id=request.url.path,
                status="DENIED",
                meta={"required": list(required), "missing": missing},
            )
            await db.commit()
            raise PermissionDeniedError(details={"required": list(required)})
        return user

    return dependency


def rate_limit(
    expression: str | None = None, *, scope: str = "default", by_user: bool = False
) -> Callable[[Request, Response], Awaitable[None]]:
    """Aplica rate limit por IP (e opcionalmente por usuário autenticado)."""
    rule = RateLimitRule.parse(expression or settings.rate_limit_default)

    async def dependency(request: Request, response: Response) -> None:
        identifier = get_client_ip(request) or "unknown"
        if by_user:
            user = getattr(request.state, "user", None)
            if user is not None:
                identifier = f"user:{user.public_id}"
        result = await check_rate_limit(f"{scope}:{identifier}", rule)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(result.remaining, 0))
        if not result.allowed:
            raise RateLimitExceededError(result.retry_after)

    return dependency
