"""Analista de melhorias (Agente 8) — painel administrativo.

Nenhuma rota aqui aplica nada. A varredura **grava achado**; o administrador
aceita ou recusa; a correção é feita nas telas que já existem (questões, geração
em massa, painel de IA). O limite L3 do desenho é exatamente isto: nada se
aplica sozinho, nem o que o próprio analista propôs.

Também não existe rota que feche um achado: ``RESOLVED`` só acontece quando o
detector deixa de achá-lo, na varredura seguinte.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.domain import permissions as perms
from app.domain.improvements import DETECTOR_BY_KEY
from app.models.audit import AuditAction
from app.models.improvement import ImprovementFinding
from app.models.user import User
from app.schemas.game import (
    ImprovementDetectorRead,
    ImprovementDetectorReport,
    ImprovementDetectorUpdate,
    ImprovementFindingDecision,
    ImprovementFindingRead,
    ImprovementRunRead,
)
from app.services.audit import AuditService
from app.services.improvements import DetectorView, ImprovementService

router = APIRouter(prefix="/admin/improvements", tags=["admin · melhorias"])

Reader = Annotated[User, Depends(require_permissions(perms.IMPROVEMENTS_READ))]
Writer = Annotated[User, Depends(require_permissions(perms.IMPROVEMENTS_WRITE))]


def _detector_read(view: DetectorView) -> ImprovementDetectorRead:
    row = view.row
    return ImprovementDetectorRead(
        key=view.spec.key,
        label=view.spec.label,
        description=view.spec.description,
        scope=view.spec.scope,
        destination=view.spec.destination,
        is_enabled=bool(row.is_enabled) if row is not None else True,
        config=view.config,
        defaults=dict(view.spec.defaults),
        last_run_at=row.last_run_at if row else None,
        last_status=row.last_status if row else None,
        last_detail=row.last_detail if row else None,
        last_found=row.last_found if row else 0,
    )


def _finding_read(row: ImprovementFinding) -> ImprovementFindingRead:
    spec = DETECTOR_BY_KEY.get(row.detector)
    return ImprovementFindingRead(
        public_id=row.public_id,
        detector=row.detector,
        detector_label=spec.label if spec else row.detector,
        status=row.status,
        severity=row.severity,
        destination=row.destination,
        title=row.title,
        detail=row.detail,
        proposal=row.proposal,
        evidence=row.evidence or {},
        target_kind=row.target_kind,
        target_public_id=row.target_public_id,
        measured_waste_cents=row.measured_waste_cents,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        seen_count=row.seen_count,
        decided_at=row.decided_at,
        decision_reason=row.decision_reason,
        muted_until=row.muted_until,
        resolved_at=row.resolved_at,
        reopened_count=row.reopened_count,
    )


@router.get(
    "/detectors",
    response_model=list[ImprovementDetectorRead],
    summary="Detectores, limiares e o que a última passada viu",
)
async def list_detectors(_: Reader, db: DbSession) -> list[ImprovementDetectorRead]:
    return [_detector_read(item) for item in await ImprovementService(db).detectors()]


@router.patch(
    "/detectors/{key}",
    response_model=ImprovementDetectorRead,
    summary="Ligar, desligar ou ajustar os limiares de um detector",
)
async def update_detector(
    key: str,
    payload: ImprovementDetectorUpdate,
    actor: Writer,
    db: DbSession,
    ctx: RequestCtx,
) -> ImprovementDetectorRead:
    view = await ImprovementService(db).set_detector(
        key,
        is_enabled=payload.is_enabled,
        config=payload.config,
        actor=actor,
        context=ctx,
    )
    return _detector_read(view)


@router.get(
    "/findings",
    response_model=list[ImprovementFindingRead],
    summary="Achados do analista",
)
async def list_findings(
    _: Reader,
    db: DbSession,
    status: Annotated[str | None, Query(description="OPEN, ACCEPTED, REJECTED ou RESOLVED")] = None,
    detector: Annotated[str | None, Query(description="Filtra por detector")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ImprovementFindingRead]:
    rows = await ImprovementService(db).findings(status=status, detector=detector, limit=limit)
    return [_finding_read(row) for row in rows]


@router.post(
    "/run",
    response_model=ImprovementRunRead,
    summary="Rodar a varredura agora",
)
async def run_scan(actor: Writer, db: DbSession, ctx: RequestCtx) -> ImprovementRunRead:
    """Roda os detectores ligados. Grava achado; não aplica nada.

    A trilha de auditoria é gravada aqui, com a credencial da aplicação: a
    varredura em si roda na credencial restrita, que não pode escrever em
    ``audit_logs`` — e não deve poder.
    """
    await AuditService(db).record(
        AuditAction.IMPROVEMENT_SCAN_STARTED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="improvement_scan",
        resource_id=actor.public_id,
        meta={},
    )
    await db.commit()

    report = await ImprovementService(db).run()
    return ImprovementRunRead(
        isolation=report.isolation,
        detectors=[
            ImprovementDetectorReport(
                key=item.key,
                label=item.label,
                status=item.status,
                detail=item.detail,
                found=item.found,
            )
            for item in report.detectors
        ],
        opened=report.opened,
        updated=report.updated,
        resolved=report.resolved,
        reopened=report.reopened,
        muted=report.muted,
    )


@router.patch(
    "/findings/{public_id}",
    response_model=ImprovementFindingRead,
    summary="Aceitar ou recusar um achado",
)
async def decide_finding(
    public_id: str,
    payload: ImprovementFindingDecision,
    actor: Writer,
    db: DbSession,
    ctx: RequestCtx,
) -> ImprovementFindingRead:
    row = await ImprovementService(db).decide(
        public_id,
        status=payload.status,
        reason=payload.reason,
        actor=actor,
        context=ctx,
    )
    return _finding_read(row)
