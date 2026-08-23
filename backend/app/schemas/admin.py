"""Schemas do painel administrativo."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AdminUserUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(PENDING|ACTIVE|SUSPENDED)$")
    full_name: str | None = Field(default=None, min_length=3, max_length=160)


class AdminRolesAssign(BaseModel):
    roles: list[str] = Field(description="Slugs dos papéis que o usuário deve possuir")


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    resource: str
    action: str
    description: str


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    description: str
    is_system: bool
    permissions: list[PermissionRead] = Field(default_factory=list)


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_email: str | None
    actor_ip: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    status: str
    meta: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None
    created_at: datetime


class AdminOverview(BaseModel):
    """Números do painel — todos calculados por SQL, nunca estimados."""

    users_total: int
    users_active: int
    users_pending: int
    users_suspended: int
    users_created_last_7_days: int
    sessions_active: int
    logins_last_24h: int
