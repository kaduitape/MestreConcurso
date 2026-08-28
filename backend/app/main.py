"""Ponto de entrada da API do Concurso Mestre IA."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.api.v1.routers import health
from app.core.config import settings
from app.core.errors import AppError, RateLimitExceededError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.core.redis import close_redis
from app.db.session import dispose_engine, get_session_factory
from app.services.seed import sync_gamification, sync_rbac, sync_trap_patterns

logger = get_logger(__name__)

DESCRIPTION = """
API do **Concurso Mestre IA** — plataforma de preparação inteligente para concursos.

Fase 1 (fundação): autenticação, contas, sessões/dispositivos, RBAC, auditoria,
LGPD e painel administrativo. Os módulos de edital, estudo, questões e IA entram
nas fases seguintes.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level, settings.log_format)
    logger.info("app.starting", version=__version__, environment=settings.environment)
    try:
        factory = get_session_factory()
        async with factory() as session:
            await sync_rbac(session)
            await sync_trap_patterns(session)
            await sync_gamification(session)
    except Exception as exc:
        logger.warning("app.seed_sync_skipped", error=str(exc))
    yield
    await close_redis()
    await dispose_engine()
    logger.info("app.stopped")


def _error_payload(
    code: str, message: str, request: Request, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def create_app() -> FastAPI:
    configure_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        contact={"name": "Concurso Mestre IA"},
    )

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
        max_age=600,
    )
    if settings.allowed_hosts and settings.allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        headers = (
            {"Retry-After": str(exc.retry_after)}
            if isinstance(exc, RateLimitExceededError)
            else None
        )
        if exc.status_code >= 500:
            logger.error("app.error", code=exc.code, message=exc.message)
        else:
            logger.info("app.error", code=exc.code, message=exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.code, exc.message, request, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {
                "field": ".".join(str(part) for part in error["loc"][1:]),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "validation_error", "Dados inválidos.", request, {"fields": fields}
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {401: "unauthenticated", 403: "permission_denied", 404: "not_found"}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                codes.get(exc.status_code, "http_error"), str(exc.detail), request
            ),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("app.unhandled_error", error=str(exc))
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                "internal_error",
                "Erro interno. A equipe foi notificada.",
                request,
            ),
        )

    return app


app = create_app()
