"""Retificação de edital — painel administrativo.

Comparar não muda nada: produz o registro do que mudou e do que isso atinge.
Apagar conteúdo órfão, regenerar o que falta — são decisões de uma pessoa, em
outras telas.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.catalog import Competition
from app.models.notice_diff import NoticeDiff
from app.models.user import User
from app.schemas.notice_diff import NoticeDiffCreate, NoticeDiffRead
from app.services.notice_diff import NoticeDiffService

router = APIRouter(prefix="/admin/notice-diffs", tags=["admin · retificações"])

PageDep = Annotated[PageParams, Depends(page_params)]
DiffReader = Annotated[User, Depends(require_permissions(perms.NOTICES_READ))]
DiffWriter = Annotated[User, Depends(require_permissions(perms.NOTICES_WRITE))]


async def _read(db: DbSession, registro: NoticeDiff) -> NoticeDiffRead:
    competition = (
        await db.execute(select(Competition).where(Competition.id == registro.competition_id))
    ).scalar_one_or_none()
    return NoticeDiffRead(
        public_id=registro.public_id,
        competition_public_id=competition.public_id if competition else None,
        from_notice_title=registro.from_notice_title,
        to_notice_title=registro.to_notice_title,
        changes=list(registro.changes or []),
        impacts=list(registro.impacts or []),
        summary=dict(registro.summary or {}),
        reviewed_at=registro.reviewed_at,
        created_at=registro.created_at,
    )


@router.post(
    "",
    response_model=NoticeDiffRead,
    status_code=status.HTTP_201_CREATED,
    summary="Comparar duas versões do edital",
)
async def compare(
    payload: NoticeDiffCreate, actor: DiffWriter, db: DbSession, ctx: RequestCtx
) -> NoticeDiffRead:
    """Sem as duas versões informadas, compara as duas análises mais recentes."""
    registro = await NoticeDiffService(db).compare(
        competition_public_id=payload.competition_public_id,
        from_public_id=payload.from_notice_public_id,
        to_public_id=payload.to_notice_public_id,
        actor=actor,
        context=ctx,
    )
    return await _read(db, registro)


@router.get("", response_model=Page[NoticeDiffRead], summary="Comparações")
async def list_diffs(
    _: DiffReader,
    db: DbSession,
    params: PageDep,
    competition_public_id: Annotated[str | None, Query()] = None,
) -> Page[NoticeDiffRead]:
    rows, total = await NoticeDiffService(db).list(
        competition_public_id=competition_public_id,
        limit=params.page_size,
        offset=params.offset,
    )
    return Page.create([await _read(db, row) for row in rows], total, params)


@router.get("/{public_id}", response_model=NoticeDiffRead, summary="Uma comparação")
async def get_diff(public_id: str, _: DiffReader, db: DbSession) -> NoticeDiffRead:
    return await _read(db, await NoticeDiffService(db).get(public_id))


@router.post("/{public_id}/reviewed", response_model=NoticeDiffRead, summary="Marcar como lida")
async def mark_reviewed(
    public_id: str, actor: DiffWriter, db: DbSession, ctx: RequestCtx
) -> NoticeDiffRead:
    """Retificação lida não some no meio das outras."""
    service = NoticeDiffService(db)
    registro = await service.mark_reviewed(await service.get(public_id), actor, ctx)
    return await _read(db, registro)
