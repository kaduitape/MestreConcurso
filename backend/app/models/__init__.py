"""Modelos SQLAlchemy. Importar aqui garante o registro no metadata do Alembic."""

from app.models.audit import AuditLog, ConsentLog
from app.models.rbac import Permission, Role, role_permissions, user_roles
from app.models.token import AuthToken, AuthTokenType
from app.models.user import Profile, User, UserStatus
from app.models.user_session import UserSession

__all__ = [
    "AuditLog",
    "AuthToken",
    "AuthTokenType",
    "ConsentLog",
    "Permission",
    "Profile",
    "Role",
    "User",
    "UserSession",
    "UserStatus",
    "role_permissions",
    "user_roles",
]
