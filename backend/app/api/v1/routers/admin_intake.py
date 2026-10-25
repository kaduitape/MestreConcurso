"""Cadastro de concurso a partir de uma URL — painel administrativo.

As rotas seguem o caminho da passagem: ``POST`` para jogar o endereço,
``/choose`` quando o serviço recusou escolher o PDF, e ``/apply`` ou
``/reject`` para a decisão humana. Aplicar exige as duas permissões de escrita
— edital e catálogo — porque é o que a rota cria.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.intake import CompetitionIntake
from app.models.user import User
from app.schemas.catalog import CompetitionRead
from app.schemas.intake import (
    IntakeApply,
    IntakeChoose,
    IntakeRead,
    IntakeReject,
    IntakeStart,
)
from app.services.intake import CompetitionIntakeService

router = APIRouter(prefix="/admin/competition-intakes", tags=["admin · cadastro por URL"])

IntakeReader = Annotated[User, Depends(require_permissions(perms.CATALOG_READ))]
IntakeWriter = Annotated[
    User, Depends(require_permissions(perms.CATALOG_WRITE, perms.NOTICES_WRITE))
]
PageDep = Annotated[PageParams, Depends(page_params)]


def _read(intake: CompetitionIntake) -> IntakeRead:
    """Acrescenta os identificadores públicos do que a passagem produziu."""
    return IntakeRead.model_validate(intake).model_copy(
        update={
            "notice_public_id": intake.notice.public_id if intake.notice else None,
            "competition_public_id": (intake.competition.public_id if intake.competition else None),
        }
    )


@router.get("", response_model=Page[IntakeRead], summary="Listar cadastros por URL")
async def list_intakes(
    _: IntakeReader,
    db: DbSession,
    params: PageDep,
    status_filter: Annotated[str | None, Query(alias="status", max_length=30)] = None,
) -> Page[IntakeRead]:
    rows, total = await CompetitionIntakeService(db).list_intakes(
        limit=params.page_size, offset=params.offset, status=status_filter
    )
    return Page.create([_read(item) for item in rows], total, params)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=IntakeRead,
    summary="Cadastrar um concurso a partir de uma URL",
)
async def start_intake(
    payload: IntakeStart, actor: IntakeWriter, db: DbSession, ctx: RequestCtx
) -> IntakeRead:
    intake = await CompetitionIntakeService(db).start(
        url=payload.url, auto_apply=payload.auto_apply, actor=actor, context=ctx
    )
    return _read(intake)


@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=IntakeRead,
    summary="Subir o PDF do edital e cadastrar o concurso",
)
async def upload_intake(
    actor: IntakeWriter,
    db: DbSession,
    ctx: RequestCtx,
    file: Annotated[UploadFile, File(description="Arquivo PDF do edital")],
    auto_apply: Annotated[bool, Form(description="Cadastrar o que o edital sustentar")] = True,
) -> IntakeRead:
    """A entrada mais curta: o arquivo já é o edital, não há link para escolher."""
    content = await file.read()
    intake = await CompetitionIntakeService(db).start_from_upload(
        content=content,
        filename=file.filename or "edital.pdf",
        declared_mime=file.content_type,
        auto_apply=auto_apply,
        actor=actor,
        context=ctx,
    )
    return _read(intake)


@router.get("/{public_id}", response_model=IntakeRead, summary="Detalhar cadastro por URL")
async def get_intake(public_id: str, _: IntakeReader, db: DbSession) -> IntakeRead:
    return _read(await CompetitionIntakeService(db).get(public_id))


@router.post(
    "/{public_id}/choose",
    response_model=IntakeRead,
    summary="Apontar qual PDF é o edital",
)
async def choose_pdf(
    public_id: str,
    payload: IntakeChoose,
    actor: IntakeWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> IntakeRead:
    service = CompetitionIntakeService(db)
    intake = await service.get(public_id)
    return _read(
        await service.choose(
            intake, url=payload.url, auto_apply=payload.auto_apply, actor=actor, context=ctx
        )
    )


@router.post(
    "/{public_id}/apply",
    response_model=CompetitionRead,
    summary="Aplicar a proposta e cadastrar o concurso",
)
async def apply_intake(
    public_id: str,
    payload: IntakeApply,
    actor: IntakeWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> CompetitionRead:
    service = CompetitionIntakeService(db)
    intake = await service.get(public_id)
    competition = await service.apply(
        intake,
        name=payload.name,
        year=payload.year,
        organization_public_id=payload.organization_public_id,
        organization_name=payload.organization_name,
        organization_short_name=payload.organization_short_name,
        exam_board_public_id=payload.exam_board_public_id,
        fields=payload.fields,
        position=payload.position,
        actor=actor,
        context=ctx,
    )
    return CompetitionRead.model_validate(competition)


@router.post(
    "/{public_id}/reject",
    response_model=IntakeRead,
    summary="Descartar a proposta",
)
async def reject_intake(
    public_id: str,
    payload: IntakeReject,
    actor: IntakeWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> IntakeRead:
    service = CompetitionIntakeService(db)
    intake = await service.get(public_id)
    return _read(await service.reject(intake, reason=payload.reason, actor=actor, context=ctx))
