"""Geração em massa por tópico — painel administrativo.

O plano é montado, mostrado com a estimativa e **só roda depois que uma pessoa
confirma**. A confirmação é uma rota separada de propósito: disparar centenas de
chamadas de IA não pode ser efeito colateral de abrir uma tela.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.catalog import Competition
from app.models.generation import GenerationPlan
from app.models.user import User
from app.schemas.generation import (
    GenerationItemRead,
    GenerationPlanCreate,
    GenerationPlanRead,
)
from app.services.generation import GenerationService
from app.workers.tasks.generation import run_generation_plan_task

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/generation", tags=["admin · geração em massa"])

PageDep = Annotated[PageParams, Depends(page_params)]
GenerationReader = Annotated[User, Depends(require_permissions(perms.TRAINING_READ))]
GenerationWriter = Annotated[User, Depends(require_permissions(perms.TRAINING_WRITE))]


async def _read(db: DbSession, plan: GenerationPlan) -> GenerationPlanRead:
    competition = (
        await db.execute(select(Competition).where(Competition.id == plan.competition_id))
    ).scalar_one_or_none()
    progresso = GenerationService(db).progress(plan)
    return GenerationPlanRead(
        public_id=plan.public_id,
        competition_public_id=competition.public_id if competition else None,
        status=plan.status,
        kinds=list(plan.kinds or []),
        options=dict(plan.options or {}),
        estimate_cents=plan.estimate_cents,
        estimate_is_known=plan.estimate_is_known,
        estimate_basis=dict(plan.estimate_basis or {}),
        spent_cents=plan.spent_cents,
        confirmed_at=plan.confirmed_at,
        finished_at=plan.finished_at,
        created_at=plan.created_at,
        items=[
            GenerationItemRead(
                topic_name=item.topic_name,
                subject_name=item.subject_name,
                kind=item.kind,
                decision=item.decision,
                status=item.status,
                reason=item.reason,
                target_public_id=item.target_public_id,
                cost_cents=item.cost_cents,
            )
            for item in plan.items
        ],
        progress={
            "total": progresso.total,  # type: ignore[attr-defined]
            "pending": progresso.pending,  # type: ignore[attr-defined]
            "done": progresso.done,  # type: ignore[attr-defined]
            "reused": progresso.reused,  # type: ignore[attr-defined]
            "failed": progresso.failed,  # type: ignore[attr-defined]
            "blocked": progresso.blocked,  # type: ignore[attr-defined]
        },
    )


@router.post(
    "",
    response_model=GenerationPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Montar um plano",
)
async def create_plan(
    payload: GenerationPlanCreate, actor: GenerationWriter, db: DbSession, ctx: RequestCtx
) -> GenerationPlanRead:
    """Monta o plano e calcula a estimativa. **Não dispara nada.**"""
    plan = await GenerationService(db).create_plan(
        competition_public_id=payload.competition_public_id,
        kinds=payload.kinds,
        options={
            "character_name": payload.character_name,
            "level": payload.level,
            "style": payload.style,
            "target_duration_minutes": payload.target_duration_minutes,
            "max_panels": payload.max_panels,
        },
        actor=actor,
        context=ctx,
    )
    return await _read(db, plan)


@router.get("", response_model=Page[GenerationPlanRead], summary="Planos")
async def list_plans(
    _: GenerationReader, db: DbSession, params: PageDep
) -> Page[GenerationPlanRead]:
    rows, total = await GenerationService(db).list(limit=params.page_size, offset=params.offset)
    return Page.create([await _read(db, row) for row in rows], total, params)


@router.get("/{public_id}", response_model=GenerationPlanRead, summary="Acompanhar um plano")
async def get_plan(public_id: str, _: GenerationReader, db: DbSession) -> GenerationPlanRead:
    return await _read(db, await GenerationService(db).get(public_id))


@router.post(
    "/{public_id}/confirm",
    response_model=GenerationPlanRead,
    summary="Confirmar e disparar",
)
async def confirm_plan(
    public_id: str, actor: GenerationWriter, db: DbSession, ctx: RequestCtx
) -> GenerationPlanRead:
    """A confirmação é o único ponto onde a geração começa a gastar."""
    service = GenerationService(db)
    plan = await service.confirm(await service.get(public_id), actor, ctx)
    try:
        run_generation_plan_task.apply_async(kwargs={"plan_public_id": public_id}, retry=False)
    except Exception as exc:  # fila indisponível não desfaz a confirmação
        # O plano já está confirmado no banco. Perder o enfileiramento atrasa a
        # geração, não a cancela: o agente Professor executa planos confirmados.
        logger.warning("generation.enqueue_failed", plan=public_id, error=str(exc))
    return await _read(db, plan)


@router.post("/{public_id}/cancel", response_model=GenerationPlanRead, summary="Cancelar")
async def cancel_plan(
    public_id: str, actor: GenerationWriter, db: DbSession, ctx: RequestCtx
) -> GenerationPlanRead:
    service = GenerationService(db)
    plan = await service.cancel(await service.get(public_id), actor, ctx)
    return await _read(db, plan)
