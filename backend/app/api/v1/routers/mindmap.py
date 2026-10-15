"""Mapas mentais: estúdio editorial e catálogo publicado.

A ordem das rotas importa: ``/panels`` vem antes de qualquer ``/{public_id}``,
porque o FastAPI casa na ordem de declaração e depois dela "panels" seria lido
como identificador de mapa.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.domain.mindmap import PANELS
from app.models.user import User
from app.schemas.mindmap import (
    MindMapContentUpdate,
    MindMapCreate,
    MindMapPanelSpecRead,
    MindMapRead,
)
from app.services.mindmap import MindMapService

map_router = APIRouter(prefix="/mindmaps", tags=["mapas mentais"])
admin_router = APIRouter(prefix="/admin/mindmaps", tags=["admin · mapas mentais"])

PageDep = Annotated[PageParams, Depends(page_params)]
MapReader = Annotated[User, Depends(require_permissions(perms.TRAINING_READ))]
MapWriter = Annotated[User, Depends(require_permissions(perms.TRAINING_WRITE))]


@map_router.get("", response_model=Page[MindMapRead], summary="Mapas mentais publicados")
async def list_published(_: CurrentUser, db: DbSession, params: PageDep) -> Page[MindMapRead]:
    rows, total = await MindMapService(db).list(
        limit=params.page_size, offset=params.offset, published_only=True
    )
    return Page.create([MindMapRead.model_validate(item) for item in rows], total, params)


@map_router.get("/{public_id}", response_model=MindMapRead, summary="Abrir mapa mental publicado")
async def open_published(public_id: str, _: CurrentUser, db: DbSession) -> MindMapRead:
    return MindMapRead.model_validate(await MindMapService(db).get(public_id, published_only=True))


@admin_router.get("/panels", response_model=list[MindMapPanelSpecRead], summary="Tipos de painel")
async def list_panels(_: MapWriter) -> list[MindMapPanelSpecRead]:
    """O catálogo fixo, para o editor dizer o que entra em cada painel."""
    return [
        MindMapPanelSpecRead(
            kind=item.kind,
            label=item.label,
            guidance=item.guidance,
            color_token=item.color_token,
            icon=item.icon,
        )
        for item in PANELS
    ]


@admin_router.get("", response_model=Page[MindMapRead], summary="Listar mapas do estúdio")
async def list_all(_: MapReader, db: DbSession, params: PageDep) -> Page[MindMapRead]:
    rows, total = await MindMapService(db).list(limit=params.page_size, offset=params.offset)
    return Page.create([MindMapRead.model_validate(item) for item in rows], total, params)


@admin_router.post(
    "",
    response_model=MindMapRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar mapa mental",
)
async def create_map(
    payload: MindMapCreate, actor: MapWriter, db: DbSession, ctx: RequestCtx
) -> MindMapRead:
    created = await MindMapService(db).create(
        actor,
        ctx,
        subject=payload.subject,
        topic=payload.topic,
        level=payload.level,
        max_panels=payload.max_panels,
        source_content=payload.source_content,
    )
    return MindMapRead.model_validate(created)


@admin_router.get("/{public_id}", response_model=MindMapRead, summary="Abrir mapa no editor")
async def open_map(public_id: str, _: MapReader, db: DbSession) -> MindMapRead:
    return MindMapRead.model_validate(await MindMapService(db).get(public_id))


@admin_router.post(
    "/{public_id}/generate", response_model=MindMapRead, summary="Gerar o mapa com IA"
)
async def generate_map(
    public_id: str, actor: MapWriter, db: DbSession, ctx: RequestCtx
) -> MindMapRead:
    """A IA estrutura o conteúdo; o mapa fica **pronto para revisão**, não publicado."""
    service = MindMapService(db)
    lesson = await service.get(public_id)
    return MindMapRead.model_validate(await service.generate(lesson, actor, ctx))


@admin_router.put("/{public_id}/content", response_model=MindMapRead, summary="Salvar a revisão")
async def save_content(
    public_id: str,
    payload: MindMapContentUpdate,
    actor: MapWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> MindMapRead:
    service = MindMapService(db)
    lesson = await service.get(public_id)
    saved = await service.save_content(
        lesson, actor, ctx, title=payload.title, content=payload.content
    )
    return MindMapRead.model_validate(saved)


@admin_router.post(
    "/{public_id}/publish", response_model=MindMapRead, summary="Publicar mapa mental"
)
async def publish_map(
    public_id: str, actor: MapWriter, db: DbSession, ctx: RequestCtx
) -> MindMapRead:
    service = MindMapService(db)
    lesson = await service.get(public_id)
    return MindMapRead.model_validate(await service.publish(lesson, actor, ctx))
