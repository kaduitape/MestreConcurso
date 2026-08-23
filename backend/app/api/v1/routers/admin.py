"""Painel administrativo — acesso controlado por permissões."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.user import User
from app.schemas.admin import (
    AdminOverview,
    AdminRolesAssign,
    AdminUserUpdate,
    AuditLogRead,
    PermissionRead,
    RoleRead,
)
from app.schemas.user import UserRead
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])

AdminReader = Annotated[User, Depends(require_permissions(perms.USERS_READ))]
AdminWriter = Annotated[User, Depends(require_permissions(perms.USERS_WRITE))]
AuditReader = Annotated[User, Depends(require_permissions(perms.AUDIT_READ))]
DashboardReader = Annotated[User, Depends(require_permissions(perms.ADMIN_DASHBOARD_READ))]
PageDep = Annotated[PageParams, Depends(page_params)]


@router.get("/overview", response_model=AdminOverview, summary="Indicadores do painel")
async def overview(_: DashboardReader, db: DbSession) -> AdminOverview:
    return await AdminService(db).overview()


@router.get("/users", response_model=Page[UserRead], summary="Listar usuários")
async def list_users(
    _: AdminReader,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=120)] = None,
    status: Annotated[str | None, Query(pattern="^(PENDING|ACTIVE|SUSPENDED|DELETED)$")] = None,
    role: Annotated[str | None, Query(max_length=50)] = None,
) -> Page[UserRead]:
    users, total = await AdminService(db).list_users(
        limit=params.page_size,
        offset=params.offset,
        search=search,
        status=status,
        role=role,
    )
    return Page.create([UserRead.model_validate(user) for user in users], total, params)


@router.get("/users/{public_id}", response_model=UserRead, summary="Detalhar usuário")
async def get_user(public_id: str, _: AdminReader, db: DbSession) -> UserRead:
    return UserRead.model_validate(await AdminService(db).get_user(public_id))


@router.patch("/users/{public_id}", response_model=UserRead, summary="Atualizar usuário")
async def update_user(
    public_id: str,
    payload: AdminUserUpdate,
    actor: AdminWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> UserRead:
    user = await AdminService(db).update_user(
        actor, public_id, status=payload.status, full_name=payload.full_name, context=ctx
    )
    return UserRead.model_validate(user)


@router.put(
    "/users/{public_id}/roles", response_model=UserRead, summary="Definir papéis do usuário"
)
async def assign_roles(
    public_id: str,
    payload: AdminRolesAssign,
    actor: AdminWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> UserRead:
    user = await AdminService(db).assign_roles(actor, public_id, payload.roles, ctx)
    return UserRead.model_validate(user)


@router.get("/roles", response_model=list[RoleRead], summary="Listar papéis")
async def list_roles(
    _: Annotated[User, Depends(require_permissions(perms.ROLES_READ))], db: DbSession
) -> list[RoleRead]:
    roles = await AdminService(db).roles.list_all()
    return [RoleRead.model_validate(role) for role in roles]


@router.get("/permissions", response_model=list[PermissionRead], summary="Listar permissões")
async def list_permissions(
    _: Annotated[User, Depends(require_permissions(perms.ROLES_READ))], db: DbSession
) -> list[PermissionRead]:
    items = await AdminService(db).permissions.list_all()
    return [PermissionRead.model_validate(item) for item in items]


@router.get("/audit-logs", response_model=Page[AuditLogRead], summary="Trilha de auditoria")
async def list_audit_logs(
    _: AuditReader,
    db: DbSession,
    params: PageDep,
    action: Annotated[str | None, Query(max_length=60)] = None,
    since_days: Annotated[int | None, Query(ge=1, le=365)] = None,
) -> Page[AuditLogRead]:
    logs, total = await AdminService(db).list_audit_logs(
        limit=params.page_size, offset=params.offset, action=action, since_days=since_days
    )
    return Page.create([AuditLogRead.model_validate(log) for log in logs], total, params)
