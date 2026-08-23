"""Trilha de auditoria e registro de consentimentos (LGPD)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin
from app.db.types import JsonType


class AuditAction(StrEnum):
    USER_REGISTERED = "user.registered"
    USER_LOGIN = "user.login"
    USER_LOGIN_FAILED = "user.login_failed"
    USER_LOGOUT = "user.logout"
    USER_LOGOUT_ALL = "user.logout_all"
    USER_EMAIL_VERIFIED = "user.email_verified"
    USER_PASSWORD_CHANGED = "user.password_changed"
    USER_PASSWORD_RESET = "user.password_reset"
    USER_PROFILE_UPDATED = "user.profile_updated"
    USER_DATA_EXPORTED = "user.data_exported"
    USER_ACCOUNT_DELETED = "user.account_deleted"
    SESSION_REVOKED = "session.revoked"
    SESSION_REUSE_DETECTED = "session.reuse_detected"
    ADMIN_USER_UPDATED = "admin.user_updated"
    AI_PROVIDER_CREATED = "ai.provider_created"
    AI_PROVIDER_UPDATED = "ai.provider_updated"
    AI_PROVIDER_KEY_SET = "ai.provider_key_set"
    AI_PROVIDER_KEY_REMOVED = "ai.provider_key_removed"
    AI_PROVIDER_TESTED = "ai.provider_tested"
    AI_MODELS_SYNCED = "ai.models_synced"
    AI_BINDING_UPDATED = "ai.binding_updated"
    AI_CACHE_PURGED = "ai.cache_purged"
    CATALOG_CREATED = "catalog.created"
    CATALOG_UPDATED = "catalog.updated"
    CATALOG_DELETED = "catalog.deleted"
    CATALOG_IMPORTED = "catalog.imported"
    NOTICE_CREATED = "notice.created"
    NOTICE_UPDATED = "notice.updated"
    NOTICE_FILE_UPLOADED = "notice.file_uploaded"
    NOTICE_FILE_DELETED = "notice.file_deleted"
    NOTICE_ANALYZED = "notice.analyzed"
    NOTICE_FACT_REVIEWED = "notice.fact_reviewed"
    NOTICE_CONFIRMED = "notice.confirmed"
    BOARD_KNOWLEDGE_SAVED = "board.knowledge_saved"
    BOARD_KNOWLEDGE_DELETED = "board.knowledge_deleted"
    ADMIN_ROLES_ASSIGNED = "admin.roles_assigned"
    PERMISSION_DENIED = "permission.denied"


class ConsentKind(StrEnum):
    TOS = "TOS"
    PRIVACY = "PRIVACY"
    MARKETING = "MARKETING"
    AI_TRAINING = "AI_TRAINING"


class AuditLog(IdMixin, Base):
    """Registro append-only de ações sensíveis."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_user_id_created_at", "actor_user_id", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
    )

    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_email: Mapped[str | None] = mapped_column(String(255))
    actor_ip: Mapped[str | None] = mapped_column(String(45))
    action: Mapped[str] = mapped_column(String(60), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(40))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    meta: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ConsentLog(IdMixin, Base):
    """Histórico de consentimentos — exigido pela LGPD."""

    __tablename__ = "consent_logs"
    __table_args__ = (Index("ix_consent_logs_user_id_kind", "user_id", "kind", "created_at"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    version: Mapped[str] = mapped_column(String(20))
    granted: Mapped[bool] = mapped_column(Boolean, default=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
