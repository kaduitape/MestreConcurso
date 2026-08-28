"""Análise de edital: disparo, acompanhamento ao vivo, revisão e Raio-X."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.config import settings
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain import permissions as perms
from app.models.notice import Notice, NoticeStatus
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.notice import (
    AnalysisStartedResponse,
    AnalysisStateRead,
    AnalysisStepRead,
    FactRead,
    FactReviewInput,
    NoticeRead,
    RadiographyRead,
)
from app.services.analysis_progress import initial_steps
from app.services.notice_analysis import NoticeAnalysisService
from app.services.radiography import RadiographyService

router = APIRouter(prefix="/admin/notices", tags=["admin · editais"])
logger = get_logger(__name__)

NoticeReader = Annotated[User, Depends(require_permissions(perms.NOTICES_READ))]
NoticeWriter = Annotated[User, Depends(require_permissions(perms.NOTICES_WRITE))]

TERMINAL_STATUSES = {
    NoticeStatus.AWAITING_CONFIRMATION,
    NoticeStatus.CONFIRMED,
    NoticeStatus.FAILED,
}
STREAM_POLL_SECONDS = 1.0
STREAM_TIMEOUT_SECONDS = 900


async def _get_notice(db: DbSession, public_id: str) -> Notice:
    from app.repositories.notice import NoticeRepository

    notice = await NoticeRepository(db).get_by_public_id(public_id)
    if notice is None:
        raise NotFoundError("Edital não encontrado.")
    return notice


def _analysis_state(notice: Notice) -> AnalysisStateRead:
    analysis: dict[str, Any] = dict((notice.extra or {}).get("analysis") or {})
    steps = analysis.get("steps") or initial_steps()
    return AnalysisStateRead(
        notice_public_id=notice.public_id,
        status=notice.status,
        steps=[AnalysisStepRead.model_validate(step) for step in steps],
        started_at=analysis.get("started_at"),
        finished_at=analysis.get("finished_at"),
        error=analysis.get("error"),
        coverage=(notice.extra or {}).get("coverage") or {},
    )


@router.post(
    "/{public_id}/analyze",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=AnalysisStartedResponse,
    summary="Analisar o edital (PDF → texto → IA → prova)",
)
async def analyze_notice(
    public_id: str, actor: NoticeWriter, db: DbSession, ctx: RequestCtx
) -> AnalysisStartedResponse:
    notice = await _get_notice(db, public_id)

    if settings.celery_task_always_eager:
        # Sem broker (desenvolvimento/teste): roda na própria requisição.
        outcome = await NoticeAnalysisService(db).analyze(notice, actor=actor, context=ctx)
        return AnalysisStartedResponse(
            notice_public_id=outcome.notice_public_id,
            status=NoticeStatus.AWAITING_CONFIRMATION,
            message=(
                f"Análise concluída: {outcome.facts_created} campos, "
                f"{outcome.subjects_created} disciplinas."
            ),
            executed_inline=True,
        )

    from app.workers.tasks.documents import analyze_notice_task

    notice.status = NoticeStatus.QUEUED
    await db.commit()
    analyze_notice_task.apply_async(kwargs={"notice_public_id": public_id}, retry=False)
    return AnalysisStartedResponse(
        notice_public_id=public_id,
        status=NoticeStatus.QUEUED,
        message="Análise enfileirada. Acompanhe o progresso em tempo real.",
        executed_inline=False,
    )


@router.get(
    "/{public_id}/analysis",
    response_model=AnalysisStateRead,
    summary="Estado atual da análise",
)
async def analysis_state(public_id: str, _: NoticeReader, db: DbSession) -> AnalysisStateRead:
    return _analysis_state(await _get_notice(db, public_id))


@router.get(
    "/{public_id}/analysis/stream",
    summary="Acompanhamento em tempo real (SSE)",
    response_class=StreamingResponse,
)
async def analysis_stream(public_id: str, request: Request, _: NoticeReader) -> StreamingResponse:
    """Fluxo de eventos do processamento.

    O worker roda em outro processo, então a fonte de verdade é o banco: o stream
    relê o estado e emite só quando algo muda. Assim o acompanhamento sobrevive a
    recarregar a página no meio do processamento.
    """

    async def event_source() -> AsyncIterator[str]:
        factory = get_session_factory()
        last_payload: str | None = None
        elapsed = 0.0

        while elapsed < STREAM_TIMEOUT_SECONDS:
            if await request.is_disconnected():
                return

            async with factory() as session:
                notice = await _get_notice(session, public_id)
                state = _analysis_state(notice)

            payload = state.model_dump_json()
            if payload != last_payload:
                yield f"event: progress\ndata: {payload}\n\n"
                last_payload = payload

            if state.status in TERMINAL_STATUSES and state.finished_at:
                yield f"event: done\ndata: {json.dumps({'status': state.status})}\n\n"
                return

            await asyncio.sleep(STREAM_POLL_SECONDS)
            elapsed += STREAM_POLL_SECONDS

        yield f"event: timeout\ndata: {json.dumps({'status': 'TIMEOUT'})}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/{public_id}/radiography",
    response_model=RadiographyRead,
    summary="Raio-X do edital",
)
async def radiography(public_id: str, _: NoticeReader, db: DbSession) -> RadiographyRead:
    notice = await _get_notice(db, public_id)
    result = await RadiographyService(db).build(notice)
    return RadiographyRead.model_validate(result, from_attributes=True)


@router.patch(
    "/{public_id}/facts/{fact_id}",
    response_model=FactRead,
    summary="Corrigir ou confirmar um campo extraído",
)
async def review_fact(
    public_id: str,
    fact_id: int,
    payload: FactReviewInput,
    actor: NoticeWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> FactRead:
    notice = await _get_notice(db, public_id)
    fact = await NoticeAnalysisService(db).review_fact(
        notice, fact_id, value=payload.value, actor=actor, context=ctx
    )
    return FactRead(
        id=fact.id,
        field_path=fact.field_path,
        label=fact.label,
        value=(fact.value or {}).get("raw"),
        evidence_level=fact.evidence_level,
        confidence=float(fact.confidence) if fact.confidence else None,
        page_number=fact.page_number,
        quote=fact.quote,
        extracted_by=fact.extracted_by,
        model_slug=fact.model_slug,
        prompt_version=fact.prompt_version,
    )


@router.post(
    "/{public_id}/confirm",
    response_model=NoticeRead,
    summary="Confirmar a análise do edital",
)
async def confirm_notice(
    public_id: str, actor: NoticeWriter, db: DbSession, ctx: RequestCtx
) -> NoticeRead:
    notice = await _get_notice(db, public_id)
    confirmed = await NoticeAnalysisService(db).confirm(notice, actor=actor, context=ctx)
    return NoticeRead.model_validate(confirmed)


@router.post(
    "/{public_id}/reset-analysis",
    response_model=MessageResponse,
    summary="Voltar o edital para rascunho",
)
async def reset_analysis(public_id: str, _: NoticeWriter, db: DbSession) -> MessageResponse:
    notice = await _get_notice(db, public_id)
    notice.status = NoticeStatus.DRAFT
    extra = dict(notice.extra or {})
    extra.pop("analysis", None)
    notice.extra = extra
    await db.commit()
    return MessageResponse(message="Análise reiniciada. O edital voltou para rascunho.")
