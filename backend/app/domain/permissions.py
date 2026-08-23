"""Catálogo de permissões e papéis padrão.

Fonte única de verdade do RBAC: o seed do banco é gerado a partir daqui, e os
endpoints referenciam as constantes (nunca literais soltos).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionSpec:
    slug: str
    description: str

    @property
    def resource(self) -> str:
        return self.slug.split(":", 1)[0]

    @property
    def action(self) -> str:
        return self.slug.split(":", 1)[1]


# --- Permissões -------------------------------------------------------------
USERS_READ = "users:read"
USERS_WRITE = "users:write"
USERS_DELETE = "users:delete"
ROLES_READ = "roles:read"
ROLES_WRITE = "roles:write"
AUDIT_READ = "audit:read"
ADMIN_DASHBOARD_READ = "admin_dashboard:read"

PERMISSIONS: tuple[PermissionSpec, ...] = (
    PermissionSpec(USERS_READ, "Listar e visualizar usuários"),
    PermissionSpec(USERS_WRITE, "Criar e editar usuários, papéis e status"),
    PermissionSpec(USERS_DELETE, "Remover ou anonimizar contas"),
    PermissionSpec(ROLES_READ, "Visualizar papéis e permissões"),
    PermissionSpec(ROLES_WRITE, "Criar e editar papéis"),
    PermissionSpec(AUDIT_READ, "Consultar a trilha de auditoria"),
    PermissionSpec(ADMIN_DASHBOARD_READ, "Acessar o painel administrativo"),
)


# --- Papéis padrão ----------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RoleSpec:
    slug: str
    name: str
    description: str
    permissions: tuple[str, ...]


ROLE_ADMIN = "admin"
ROLE_STAFF = "staff"
ROLE_STUDENT = "student"

ROLES: tuple[RoleSpec, ...] = (
    RoleSpec(
        ROLE_ADMIN,
        "Administrador",
        "Acesso total ao painel administrativo",
        tuple(permission.slug for permission in PERMISSIONS),
    ),
    RoleSpec(
        ROLE_STAFF,
        "Equipe",
        "Suporte e curadoria de conteúdo",
        (USERS_READ, ROLES_READ, AUDIT_READ, ADMIN_DASHBOARD_READ),
    ),
    RoleSpec(
        ROLE_STUDENT,
        "Candidato",
        "Papel padrão de quem estuda na plataforma",
        (),
    ),
)

DEFAULT_ROLE = ROLE_STUDENT
