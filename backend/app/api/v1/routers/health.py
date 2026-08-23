"""Health e readiness."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession
from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import ping_redis
from app.schemas.common import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Liveness")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__, environment=settings.environment)


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness")
async def ready(db: DbSession, response: Response) -> ReadinessResponse:
    checks = {"database": False, "redis": False}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as exc:
        logger.warning("readiness.database_unavailable", error=str(exc))
    checks["redis"] = await ping_redis()

    ready_status = all(checks.values())
    if not ready_status:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if ready_status else "degraded", checks=checks)
