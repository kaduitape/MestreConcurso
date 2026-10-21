"""Auditoria de conteúdo — painel administrativo.

A ordem das rotas importa: ``/rules`` vem antes de ``/{public_id}``, porque o
FastAPI casa na ordem de declaração e depois dela "rules" viraria identificador
de laudo.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.content_audit import ContentAudit
from app.models.user import User
from app.schemas.content_audit import (
    AuditRuleRead,
    AuditRuleUpdate,
    AuditRunRequest,
    ContentAuditRead,
)
from app.services.content_audit import ContentAuditService

router = APIRouter(prefix="/admin/content-audit", tags=["admin · auditoria de conteúdo"])

PageDep = Annotated[PageParams, Depends(page_params)]
AuditReader = Annotated[User, Depends(require_permissions(perms.CONTENT_AUDIT_READ))]
AuditWriter = Annotated[User, Depends(require_permissions(perms.CONTENT_AUDIT_WRITE))]


def _read(record: ContentAudit) -> ContentAuditRead:
    return ContentAuditRead(
        public_id=record.public_id,
        target_kind=record.target_kind,
        target_public_id=record.target_public_id,
        verdict=record.verdict,
        trigger=record.trigger,
        blocked_publication=record.blocked_publication,
        findings=list(record.findings or []),
        summary=dict(record.summary or {}),
        created_at=record.created_at,
    )


@router.get("/rules", response_model=list[AuditRuleRead], summary="Regras do auditor")
async def list_rules(_: AuditReader, db: DbSession) -> list[AuditRuleRead]:
    """O que cada regra cobra, e como ela está configurada agora."""
    return [
        AuditRuleRead(
            key=rule.key,
            label=rule.label,
            description=rule.description,
            applies_to=list(rule.applies_to),
            default_severity=rule.default_severity,
            severity=rule.severity,
            is_enabled=rule.is_enabled,
            config=rule.config,
        )
        for rule in await ContentAuditService(db).rules()
    ]


@router.put("/rules/{key}", response_model=AuditRuleRead, summary="Configurar uma regra")
async def update_rule(
    key: str, payload: AuditRuleUpdate, actor: AuditWriter, db: DbSession, ctx: RequestCtx
) -> AuditRuleRead:
    """Severidade e limiar vivem no banco — nunca no código."""
    rule = await ContentAuditService(db).set_rule(
        key,
        is_enabled=payload.is_enabled,
        severity=payload.severity,
        config=payload.config,
        actor=actor,
        context=ctx,
    )
    return AuditRuleRead(
        key=rule.key,
        label=rule.label,
        description=rule.description,
        applies_to=list(rule.applies_to),
        default_severity=rule.default_severity,
        severity=rule.severity,
        is_enabled=rule.is_enabled,
        config=rule.config,
    )


@router.post("/run", response_model=ContentAuditRead, summary="Conferir um conteúdo agora")
async def run_audit(
    payload: AuditRunRequest, actor: AuditWriter, db: DbSession, ctx: RequestCtx
) -> ContentAuditRead:
    record = await ContentAuditService(db).audit_target(
        kind=payload.target_kind,
        public_id=payload.target_public_id,
        actor=actor,
        context=ctx,
    )
    return _read(record)


@router.get("", response_model=Page[ContentAuditRead], summary="Histórico de laudos")
async def list_audits(
    _: AuditReader,
    db: DbSession,
    params: PageDep,
    target_kind: Annotated[str | None, Query()] = None,
    target_public_id: Annotated[str | None, Query()] = None,
) -> Page[ContentAuditRead]:
    """Cada conferência é uma linha nova: o histórico mostra o defeito sumindo."""
    rows, total = await ContentAuditService(db).history(
        target_kind=target_kind,
        target_public_id=target_public_id,
        limit=params.page_size,
        offset=params.offset,
    )
    return Page.create([_read(row) for row in rows], total, params)


@router.get("/{public_id}", response_model=ContentAuditRead, summary="Um laudo")
async def get_audit(public_id: str, _: AuditReader, db: DbSession) -> ContentAuditRead:
    return _read(await ContentAuditService(db).get(public_id))
