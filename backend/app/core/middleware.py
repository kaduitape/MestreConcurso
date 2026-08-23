"""Middlewares transversais: request-id, tempo de resposta, cabeçalhos de segurança."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"

_CSP = (
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self' https:; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Injeta request-id, mede latência e registra o acesso em log estruturado."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "http.request.failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms}"
        if request.url.path not in {"/health", "/ready", "/metrics"}:
            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client=request.client.host if request.client else None,
                request_id=request_id,
            )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Aplica cabeçalhos de segurança em todas as respostas."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # A documentação interativa precisa de CDN/script inline próprios.
        if not request.url.path.startswith(("/docs", "/redoc")):
            headers.setdefault("Content-Security-Policy", _CSP)
        if settings.is_production:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
