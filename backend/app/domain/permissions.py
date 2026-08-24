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
CATALOG_READ = "catalog:read"
CATALOG_WRITE = "catalog:write"
NOTICES_READ = "notices:read"
NOTICES_WRITE = "notices:write"
QUESTIONS_READ = "questions:read"
QUESTIONS_WRITE = "questions:write"
AI_SETTINGS_READ = "ai_settings:read"
AI_SETTINGS_WRITE = "ai_settings:write"

PERMISSIONS: tuple[PermissionSpec, ...] = (
    PermissionSpec(USERS_READ, "Listar e visualizar usuários"),
    PermissionSpec(USERS_WRITE, "Criar e editar usuários, papéis e status"),
    PermissionSpec(USERS_DELETE, "Remover ou anonimizar contas"),
    PermissionSpec(ROLES_READ, "Visualizar papéis e permissões"),
    PermissionSpec(ROLES_WRITE, "Criar e editar papéis"),
    PermissionSpec(AUDIT_READ, "Consultar a trilha de auditoria"),
    PermissionSpec(ADMIN_DASHBOARD_READ, "Acessar o painel administrativo"),
    PermissionSpec(CATALOG_READ, "Consultar bancas, concursos, cargos e disciplinas"),
    PermissionSpec(CATALOG_WRITE, "Cadastrar e editar o catálogo de concursos"),
    PermissionSpec(NOTICES_READ, "Consultar editais e seus arquivos"),
    PermissionSpec(NOTICES_WRITE, "Cadastrar editais e enviar arquivos"),
    PermissionSpec(QUESTIONS_READ, "Consultar o banco de questões"),
    PermissionSpec(QUESTIONS_WRITE, "Cadastrar, importar e classificar questões"),
    PermissionSpec(AI_SETTINGS_READ, "Ver a configuração de provedores de IA"),
    PermissionSpec(AI_SETTINGS_WRITE, "Configurar provedores, chaves e modelos de IA"),
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
        (
            USERS_READ,
            ROLES_READ,
            AUDIT_READ,
            ADMIN_DASHBOARD_READ,
            CATALOG_READ,
            CATALOG_WRITE,
            NOTICES_READ,
            NOTICES_WRITE,
            QUESTIONS_READ,
            QUESTIONS_WRITE,
        ),
    ),
    RoleSpec(
        ROLE_STUDENT,
        "Candidato",
        "Papel padrão de quem estuda na plataforma",
        (),
    ),
)

DEFAULT_ROLE = ROLE_STUDENT
