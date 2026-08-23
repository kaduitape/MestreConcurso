"""Cadastro de editais e upload de arquivos — painel administrativo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.notice import NoticeCreate, NoticeFileRead, NoticeRead, NoticeUpdate
from app.services.notice import NoticeService

router = APIRouter(prefix="/admin/notices", tags=["admin · editais"])

NoticeReader = Annotated[User, Depends(require_permissions(perms.NOTICES_READ))]
NoticeWriter = Annotated[User, Depends(require_permissions(perms.NOTICES_WRITE))]
PageDep = Annotated[PageParams, Depends(page_params)]


@router.get("", response_model=Page[NoticeRead], summary="Listar editais")
async def list_notices(
    _: NoticeReader,
    db: DbSession,
    params: PageDep,
    status_filter: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> Page[NoticeRead]:
    notices, total = await NoticeService(db).list_notices(
        limit=params.page_size, offset=params.offset, status=status_filter
    )
    return Page.create([NoticeRead.model_validate(item) for item in notices], total, params)


@router.post(
    "", status_code=status.HTTP_201_CREATED, response_model=NoticeRead, summary="Cadastrar edital"
)
async def create_notice(
    payload: NoticeCreate, actor: NoticeWriter, db: DbSession, ctx: RequestCtx
) -> NoticeRead:
    notice = await NoticeService(db).create_notice(
        payload.model_dump(exclude_none=True, exclude={"competition_public_id"}),
        competition_public_id=payload.competition_public_id,
        actor=actor,
        context=ctx,
    )
    return NoticeRead.model_validate(notice)


@router.get("/{public_id}", response_model=NoticeRead, summary="Detalhar edital")
async def get_notice(public_id: str, _: NoticeReader, db: DbSession) -> NoticeRead:
    return NoticeRead.model_validate(await NoticeService(db).get_notice(public_id))


@router.patch("/{public_id}", response_model=NoticeRead, summary="Editar edital")
async def update_notice(
    public_id: str,
    payload: NoticeUpdate,
    actor: NoticeWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> NoticeRead:
    notice = await NoticeService(db).update_notice(
        public_id, payload.model_dump(exclude_unset=True), actor=actor, context=ctx
    )
    return NoticeRead.model_validate(notice)


@router.delete("/{public_id}", response_model=MessageResponse, summary="Remover edital")
async def delete_notice(
    public_id: str, actor: NoticeWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await NoticeService(db).delete_notice(public_id, actor=actor, context=ctx)
    return MessageResponse(message="Edital e arquivos removidos.")


@router.post(
    "/{public_id}/files",
    status_code=status.HTTP_201_CREATED,
    response_model=NoticeFileRead,
    summary="Enviar o PDF do edital",
)
async def upload_file(
    public_id: str,
    actor: NoticeWriter,
    db: DbSession,
    ctx: RequestCtx,
    file: Annotated[UploadFile, File(description="Arquivo PDF do edital")],
) -> NoticeFileRead:
    content = await file.read()
    stored = await NoticeService(db).upload_file(
        public_id,
        content=content,
        original_name=file.filename or "edital.pdf",
        declared_mime=file.content_type,
        actor=actor,
        context=ctx,
    )
    return NoticeFileRead.model_validate(stored)


@router.get(
    "/files/{file_public_id}/download",
    summary="Baixar o arquivo do edital",
    response_class=Response,
)
async def download_file(file_public_id: str, _: NoticeReader, db: DbSession) -> Response:
    file, content = await NoticeService(db).read_file(file_public_id)
    return Response(
        content=content,
        media_type=file.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file.original_name}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/files/{file_public_id}", response_model=MessageResponse, summary="Remover arquivo")
async def delete_file(
    file_public_id: str, actor: NoticeWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await NoticeService(db).delete_file(file_public_id, actor=actor, context=ctx)
    return MessageResponse(message="Arquivo removido.")
