"""Tarefas pesadas de documento: análise de edital fora do ciclo HTTP."""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.repositories.notice import NoticeRepository
from app.services.auth import RequestContext
from app.services.notice_analysis import NoticeAnalysisService

logger = get_logger(__name__)


async def _analyze(notice_public_id: str) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        notice = await NoticeRepository(session).get_by_public_id(notice_public_id)
        if notice is None:
            logger.warning("notice.analysis.missing", notice=notice_public_id)
            return {"status": "NOT_FOUND"}

        service = NoticeAnalysisService(session)
        outcome = await service.analyze(notice, actor=None, context=RequestContext())
        return {
            "status": "OK",
            "chunks": outcome.chunk_count,
            "facts": outcome.facts_created,
            "subjects": outcome.subjects_created,
            "cached": outcome.cached,
        }


@shared_task(
    name="documents.analyze_notice",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    time_limit=1800,
    soft_time_limit=1740,
)
def analyze_notice_task(self: Any, notice_public_id: str) -> dict[str, Any]:
    """Executa o pipeline completo de análise de um edital."""
    result = asyncio.run(_analyze(notice_public_id))
    logger.info("notice.analysis.task_done", notice=notice_public_id, **result)
    return result
