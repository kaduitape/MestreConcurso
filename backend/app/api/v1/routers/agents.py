"""Orquestrador de agentes — painel administrativo.

A ordem das rotas importa: ``/catalog`` vem antes de ``/{public_id}``, porque o
FastAPI casa na ordem de declaração e depois dela "catalog" seria lido como
identificador de execução.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.domain.agents import AGENTS, execution_order
from app.models.agent_run import AgentRun
from app.models.user import User
from app.schemas.agents import (
    AgentCatalogRead,
    AgentLayersRead,
    AgentRunCreate,
    AgentRunRead,
    AgentStepRead,
)
from app.services import agent_runners  # noqa: F401  (registra os agentes reais)
from app.services.orchestrator import OrchestratorService

router = APIRouter(prefix="/admin/agents", tags=["admin · agentes"])

PageDep = Annotated[PageParams, Depends(page_params)]
AgentReader = Annotated[User, Depends(require_permissions(perms.AI_SETTINGS_READ))]
AgentWriter = Annotated[User, Depends(require_permissions(perms.AI_SETTINGS_WRITE))]


def _read(
    service: OrchestratorService, run: AgentRun, competition_public_id: str | None
) -> AgentRunRead:
    return AgentRunRead(
        public_id=run.public_id,
        competition_public_id=competition_public_id,
        status=run.status,
        error=run.error,
        cost_cents=run.cost_cents,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        steps=[
            AgentStepRead(
                key=step.key,
                label=step.label,
                description=step.description,
                status=step.status,
                depends_on=list(step.depends_on),
                attempts=step.attempts,
                max_attempts=step.max_attempts,
                detail=step.detail,
                is_implemented=step.is_implemented,
            )
            for step in service.view(run)
        ],
    )


async def _competition_public_id(db: DbSession, run: AgentRun) -> str | None:
    from sqlalchemy import select

    from app.models.catalog import Competition

    if run.competition_id is None:
        return None
    found = (
        await db.execute(select(Competition).where(Competition.id == run.competition_id))
    ).scalar_one_or_none()
    return found.public_id if found else None


@router.get("/catalog", response_model=AgentLayersRead, summary="Catálogo e ordem dos agentes")
async def catalog(_: AgentReader) -> AgentLayersRead:
    """O que cada agente faz e quais podem rodar juntos."""
    return AgentLayersRead(
        layers=execution_order(),
        agents=[
            AgentCatalogRead(
                key=spec.key,
                label=spec.label,
                description=spec.description,
                depends_on=list(spec.depends_on),
                is_implemented=spec.is_implemented,
                pending_reason=spec.pending_reason,
            )
            for spec in AGENTS
        ],
    )


@router.get("", response_model=Page[AgentRunRead], summary="Execuções")
async def list_runs(_: AgentReader, db: DbSession, params: PageDep) -> Page[AgentRunRead]:
    service = OrchestratorService(db)
    rows, total = await service.list(limit=params.page_size, offset=params.offset)
    items = [_read(service, run, await _competition_public_id(db, run)) for run in rows]
    return Page.create(items, total, params)


@router.post(
    "",
    response_model=AgentRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Criar execução",
)
async def create_run(
    payload: AgentRunCreate, actor: AgentWriter, db: DbSession, ctx: RequestCtx
) -> AgentRunRead:
    service = OrchestratorService(db)
    run = await service.create(actor, ctx, competition_public_id=payload.competition_public_id)
    return _read(service, run, payload.competition_public_id)


@router.get("/{public_id}", response_model=AgentRunRead, summary="Acompanhar execução")
async def get_run(public_id: str, _: AgentReader, db: DbSession) -> AgentRunRead:
    service = OrchestratorService(db)
    run = await service.get(public_id)
    return _read(service, run, await _competition_public_id(db, run))


@router.post("/{public_id}/run", response_model=AgentRunRead, summary="Executar tudo")
async def execute_run(
    public_id: str, actor: AgentWriter, db: DbSession, ctx: RequestCtx
) -> AgentRunRead:
    service = OrchestratorService(db)
    run = await service.execute(await service.get(public_id), actor, ctx)
    return _read(service, run, await _competition_public_id(db, run))


@router.post(
    "/{public_id}/run/{agent_key}",
    response_model=AgentRunRead,
    summary="Executar um agente sozinho",
)
async def execute_one(
    public_id: str, agent_key: str, actor: AgentWriter, db: DbSession, ctx: RequestCtx
) -> AgentRunRead:
    """Insistir num passo que falhou sem refazer a execução inteira."""
    service = OrchestratorService(db)
    run = await service.execute_one(await service.get(public_id), agent_key, actor, ctx)
    return _read(service, run, await _competition_public_id(db, run))
