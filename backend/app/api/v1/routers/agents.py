"""Orquestrador de agentes — painel administrativo.

A ordem das rotas importa: ``/catalog`` vem antes de ``/{public_id}``, porque o
FastAPI casa na ordem de declaração e depois dela "catalog" seria lido como
identificador de execução.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.config import settings
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.domain.agents import AGENTS, STATUS_LABEL, StepView, execution_order
from app.models.agent_run import AgentRun, AgentStep
from app.models.user import User
from app.schemas.agents import (
    AgentAttemptRead,
    AgentCatalogRead,
    AgentLayersRead,
    AgentRunCreate,
    AgentRunRead,
    AgentStepRead,
    PrecheckRead,
    PreflightRead,
)
from app.services import agent_runners  # noqa: F401  (registra os agentes reais)
from app.services.orchestrator import OrchestratorService

logger = get_logger(__name__)

router = APIRouter(prefix="/admin/agents", tags=["admin · agentes"])

PageDep = Annotated[PageParams, Depends(page_params)]
AgentReader = Annotated[User, Depends(require_permissions(perms.AI_SETTINGS_READ))]
AgentWriter = Annotated[User, Depends(require_permissions(perms.AI_SETTINGS_WRITE))]


def _read(
    service: OrchestratorService, run: AgentRun, competition_public_id: str | None
) -> AgentRunRead:
    por_chave = {linha.agent_key: linha for linha in run.steps}
    return AgentRunRead(
        public_id=run.public_id,
        competition_public_id=competition_public_id,
        status=run.status,
        error=run.error,
        cost_cents=run.cost_cents,
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
        steps=[_step_read(step, por_chave.get(step.key)) for step in service.view(run)],
    )


def _step_read(step: StepView, linha: AgentStep | None) -> AgentStepRead:
    """O passo com o que a tela precisa para **agir**, não só para ler.

    O histórico de tentativas vem daqui: sem ele, um passo que falhou duas
    vezes por motivos diferentes só mostra o último, e a investigação do
    primeiro fica impossível.
    """
    return AgentStepRead(
        key=step.key,
        label=step.label,
        description=step.description,
        status=step.status,
        status_label=STATUS_LABEL.get(step.status, step.status),
        depends_on=list(step.depends_on),
        attempts=step.attempts,
        max_attempts=step.max_attempts,
        detail=step.detail,
        is_implemented=step.is_implemented,
        attempts_exhausted=step.attempts_exhausted,
        action=step.action,
        notes=[str(item) for item in ((linha.result or {}).get("notes") or [])] if linha else [],
        attempts_history=[
            AgentAttemptRead(
                number=tentativa.number,
                status=tentativa.status,
                detail=tentativa.detail,
                error_code=tentativa.error_code,
                request_id=tentativa.request_id,
                duration_ms=tentativa.duration_ms,
                cost_cents=tentativa.cost_cents,
                provider=tentativa.provider,
                model_slug=tentativa.model_slug,
                started_at=tentativa.started_at,
                finished_at=tentativa.finished_at,
            )
            for tentativa in (linha.tries if linha else [])
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
    rows, total = await service.list_runs(limit=params.page_size, offset=params.offset)
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


@router.get(
    "/{public_id}/preflight",
    response_model=PreflightRead,
    summary="Conferir pré-requisitos antes de executar",
)
async def preflight(public_id: str, _: AgentReader, db: DbSession) -> PreflightRead:
    """O que falta, com a ação de cada pendência. Não chama IA e não escreve."""
    service = OrchestratorService(db)
    checagens = await service.preflight(await service.get(public_id))
    return PreflightRead(
        ready=all(item.ok for item in checagens),
        checks=[
            PrecheckRead(
                key=item.key,
                label=item.label,
                ok=item.ok,
                detail=item.detail,
                action=item.action,
                resource_id=item.resource_id,
            )
            for item in checagens
        ],
    )


@router.post(
    "/{public_id}/cancel",
    response_model=AgentRunRead,
    summary="Cancelar a execução",
)
async def cancel_run(
    public_id: str, actor: AgentWriter, db: DbSession, ctx: RequestCtx
) -> AgentRunRead:
    """Para a execução preservando o que já terminou."""
    service = OrchestratorService(db)
    run = await service.cancel(await service.get(public_id), actor, ctx)
    return _read(service, run, await _competition_public_id(db, run))


@router.get("/{public_id}", response_model=AgentRunRead, summary="Acompanhar execução")
async def get_run(public_id: str, _: AgentReader, db: DbSession) -> AgentRunRead:
    service = OrchestratorService(db)
    run = await service.get(public_id)
    return _read(service, run, await _competition_public_id(db, run))


@router.post(
    "/{public_id}/run",
    response_model=AgentRunRead,
    summary="Executar tudo",
)
async def execute_run(
    public_id: str,
    actor: AgentWriter,
    db: DbSession,
    ctx: RequestCtx,
    background: Annotated[
        bool,
        Query(
            description=(
                "Enfileira a execução e devolve na hora. Falso roda dentro do "
                "pedido — útil em teste e para quem quer esperar."
            )
        ),
    ] = True,
) -> AgentRunRead:
    """Dispara os agentes.

    Por padrão o trabalho vai para a fila e o pedido devolve imediatamente: um
    job já aceito pelo servidor **não pode** morrer porque a aba fechou ou a
    sessão expirou, e era o que acontecia enquanto a execução rodava dentro da
    requisição. Quando a fila não está disponível, o pedido executa na hora e
    diz isso no lugar de fingir que enfileirou.
    """
    service = OrchestratorService(db)
    run = await service.get(public_id)

    # Sem broker (desenvolvimento/teste) roda na própria requisição, como já
    # faz a análise de edital: enfileirar para uma fila que não existe seria
    # aceitar um trabalho que nunca sairia.
    if background and not settings.celery_task_always_eager:
        try:
            run = await service.enqueue(run, actor, ctx)
        except Exception as exc:  # fila indisponível não impede o trabalho
            logger.warning("agents.enqueue_failed", run=public_id, error=str(exc))
        else:
            return _read(service, run, await _competition_public_id(db, run))

    run = await service.execute(run, actor, ctx)
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
