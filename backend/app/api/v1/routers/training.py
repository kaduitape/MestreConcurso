"""Estúdio de Treinamento: criação editorial e catálogo publicado."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.user import User
from app.schemas.training import (
    TrainingCreate,
    TrainingMetricsRead,
    TrainingProgressRead,
    TrainingProgressUpdate,
    TrainingRead,
    TrainingScriptUpdate,
)
from app.services.training import TrainingService

training_router = APIRouter(prefix="/training", tags=["estúdio de treinamento"])
admin_router = APIRouter(prefix="/admin/training", tags=["admin · estúdio de treinamento"])
PageDep = Annotated[PageParams, Depends(page_params)]
TrainingReader = Annotated[User, Depends(require_permissions(perms.TRAINING_READ))]
TrainingWriter = Annotated[User, Depends(require_permissions(perms.TRAINING_WRITE))]


@training_router.get("", response_model=Page[TrainingRead], summary="Treinamentos publicados")
async def list_published(_: CurrentUser, db: DbSession, params: PageDep) -> Page[TrainingRead]:
    rows, total = await TrainingService(db).list(
        limit=params.page_size, offset=params.offset, published_only=True
    )
    return Page.create([TrainingRead.model_validate(item) for item in rows], total, params)


@training_router.get(
    "/{public_id}", response_model=TrainingRead, summary="Abrir treinamento publicado"
)
async def get_published(public_id: str, _: CurrentUser, db: DbSession) -> TrainingRead:
    return TrainingRead.model_validate(
        await TrainingService(db).get(public_id, published_only=True)
    )


@training_router.post(
    "/{public_id}/progress/start",
    response_model=TrainingProgressRead,
    summary="Iniciar ou retomar missão",
)
async def start_progress(public_id: str, user: CurrentUser, db: DbSession) -> TrainingProgressRead:
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return TrainingProgressRead.model_validate(await service.start(lesson, user))


@training_router.put(
    "/{public_id}/progress",
    response_model=TrainingProgressRead,
    summary="Salvar progresso da missão",
)
async def save_progress(
    public_id: str, payload: TrainingProgressUpdate, user: CurrentUser, db: DbSession
) -> TrainingProgressRead:
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return TrainingProgressRead.model_validate(
        await service.update_progress(lesson, user, current_scene=payload.current_scene)
    )


@training_router.post(
    "/{public_id}/complete",
    response_model=TrainingProgressRead,
    summary="Concluir missão e creditar XP",
)
async def complete_progress(
    public_id: str, user: CurrentUser, db: DbSession
) -> TrainingProgressRead:
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return TrainingProgressRead.model_validate(await service.complete(lesson, user))


@admin_router.get("", response_model=Page[TrainingRead], summary="Listar treinamentos do estúdio")
async def list_admin(_: TrainingReader, db: DbSession, params: PageDep) -> Page[TrainingRead]:
    rows, total = await TrainingService(db).list(limit=params.page_size, offset=params.offset)
    return Page.create([TrainingRead.model_validate(item) for item in rows], total, params)


@admin_router.post(
    "", response_model=TrainingRead, status_code=status.HTTP_201_CREATED, summary="Criar rascunho"
)
async def create_training(
    payload: TrainingCreate, actor: TrainingWriter, db: DbSession, ctx: RequestCtx
) -> TrainingRead:
    lesson = await TrainingService(db).create(actor, payload.model_dump(), ctx)
    return TrainingRead.model_validate(lesson)


@admin_router.get(
    "/{public_id}", response_model=TrainingRead, summary="Abrir treinamento no editor"
)
async def get_admin(public_id: str, _: TrainingReader, db: DbSession) -> TrainingRead:
    return TrainingRead.model_validate(await TrainingService(db).get(public_id))


@admin_router.get(
    "/{public_id}/metrics",
    response_model=TrainingMetricsRead,
    summary="Métricas reais do treinamento",
)
async def training_metrics(public_id: str, _: TrainingReader, db: DbSession) -> TrainingMetricsRead:
    service = TrainingService(db)
    return TrainingMetricsRead(**await service.metrics(await service.get(public_id)))


@admin_router.post(
    "/{public_id}/generate", response_model=TrainingRead, summary="Gerar roteiro com IA"
)
async def generate_training(
    public_id: str, actor: TrainingWriter, db: DbSession, ctx: RequestCtx
) -> TrainingRead:
    service = TrainingService(db)
    lesson = await service.generate(await service.get(public_id), actor, ctx)
    return TrainingRead.model_validate(lesson)


@admin_router.put(
    "/{public_id}/script", response_model=TrainingRead, summary="Salvar edição das cenas"
)
async def update_script(
    public_id: str,
    payload: TrainingScriptUpdate,
    actor: TrainingWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> TrainingRead:
    service = TrainingService(db)
    lesson = await service.update_script(
        await service.get(public_id),
        title=payload.title,
        script=payload.script,
        actor=actor,
        context=ctx,
    )
    return TrainingRead.model_validate(lesson)


@admin_router.post(
    "/{public_id}/publish", response_model=TrainingRead, summary="Publicar treinamento"
)
async def publish_training(
    public_id: str, actor: TrainingWriter, db: DbSession, ctx: RequestCtx
) -> TrainingRead:
    service = TrainingService(db)
    lesson = await service.publish(await service.get(public_id), actor, ctx)
    return TrainingRead.model_validate(lesson)
