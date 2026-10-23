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
INTELLIGENCE_WRITE = "intelligence:write"
AI_SETTINGS_READ = "ai_settings:read"
AI_SETTINGS_WRITE = "ai_settings:write"
BILLING_READ = "billing:read"
BILLING_WRITE = "billing:write"
TRAINING_READ = "training:read"
TRAINING_WRITE = "training:write"
CONTENT_AUDIT_READ = "content_audit:read"
CONTENT_AUDIT_WRITE = "content_audit:write"
DECKS_READ = "decks:read"
DECKS_WRITE = "decks:write"
IMPROVEMENTS_READ = "improvements:read"
IMPROVEMENTS_WRITE = "improvements:write"

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
    PermissionSpec(
        INTELLIGENCE_WRITE,
        "Recalcular incidência, DNA da banca e padrões de pegadinha",
    ),
    PermissionSpec(AI_SETTINGS_READ, "Ver a configuração de provedores de IA"),
    PermissionSpec(AI_SETTINGS_WRITE, "Configurar provedores, chaves e modelos de IA"),
    PermissionSpec(BILLING_READ, "Ver planos, assinaturas e indicadores comerciais"),
    PermissionSpec(BILLING_WRITE, "Editar planos, limites, cupons e o provedor de pagamento"),
    PermissionSpec(TRAINING_READ, "Consultar treinamentos no Estúdio"),
    PermissionSpec(TRAINING_WRITE, "Criar, gerar, editar e publicar treinamentos"),
    PermissionSpec(CONTENT_AUDIT_READ, "Ver laudos de auditoria de conteúdo"),
    PermissionSpec(
        CONTENT_AUDIT_WRITE,
        "Rodar auditorias e configurar as regras que barram publicação",
    ),
    PermissionSpec(DECKS_READ, "Consultar os baralhos oficiais de flashcards"),
    PermissionSpec(
        DECKS_WRITE,
        "Criar, gerar, curar, publicar e arquivar baralhos oficiais de flashcards",
    ),
    PermissionSpec(IMPROVEMENTS_READ, "Ver os achados do analista de melhorias"),
    PermissionSpec(
        IMPROVEMENTS_WRITE,
        "Rodar a varredura, aceitar ou recusar achados e ajustar os limiares",
    ),
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
            INTELLIGENCE_WRITE,
            BILLING_READ,
            TRAINING_READ,
            TRAINING_WRITE,
            # Curadoria de baralho oficial é trabalho da equipe, e publicar um
            # baralho é o que o portão da Fase 3 confere de todo jeito.
            DECKS_READ,
            DECKS_WRITE,
            # A equipe precisa ver por que a publicação foi barrada; desligar
            # uma regra de bloqueio continua sendo decisão de administrador.
            CONTENT_AUDIT_READ,
            # Ver os achados ajuda a curadoria a saber o que consertar; aceitar,
            # recusar e mexer em limiar continua sendo de administrador.
            IMPROVEMENTS_READ,
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
