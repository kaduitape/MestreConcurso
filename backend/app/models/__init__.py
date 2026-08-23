"""Modelos SQLAlchemy. Importar aqui garante o registro no metadata do Alembic."""

from app.models.ai import (
    AICacheEntry,
    AIFeature,
    AIFeatureBinding,
    AIModel,
    AIProviderConfig,
    AIProviderSlug,
    AIUsage,
)
from app.models.audit import AuditLog, ConsentLog
from app.models.board_knowledge import (
    BoardKnowledgeEntry,
    BoardKnowledgeKind,
    KnowledgeSource,
)
from app.models.catalog import (
    Competition,
    CompetitionStatus,
    EducationLevel,
    ExamBoard,
    GovernmentSphere,
    Organization,
    Position,
    PositionSubject,
    Subject,
    Topic,
)
from app.models.notice import Notice, NoticeFile, NoticeFileStatus, NoticeKind, NoticeStatus
from app.models.rbac import Permission, Role, role_permissions, user_roles
from app.models.token import AuthToken, AuthTokenType
from app.models.user import Profile, User, UserStatus
from app.models.user_session import UserSession

__all__ = [
    "AICacheEntry",
    "AIFeature",
    "AIFeatureBinding",
    "AIModel",
    "AIProviderConfig",
    "AIProviderSlug",
    "AIUsage",
    "AuditLog",
    "AuthToken",
    "AuthTokenType",
    "BoardKnowledgeEntry",
    "BoardKnowledgeKind",
    "Competition",
    "CompetitionStatus",
    "ConsentLog",
    "EducationLevel",
    "ExamBoard",
    "GovernmentSphere",
    "KnowledgeSource",
    "Notice",
    "NoticeFile",
    "NoticeFileStatus",
    "NoticeKind",
    "NoticeStatus",
    "Organization",
    "Permission",
    "Position",
    "PositionSubject",
    "Profile",
    "Role",
    "Subject",
    "Topic",
    "User",
    "UserSession",
    "UserStatus",
    "role_permissions",
    "user_roles",
]
