"""Casos de uso da conta do próprio usuário (perfil, LGPD)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_ulid
from app.models.audit import AuditAction
from app.models.user import Profile, User, UserStatus
from app.repositories.audit import AuditLogRepository, ConsentLogRepository
from app.repositories.user import ProfileRepository, UserRepository
from app.repositories.user_session import UserSessionRepository
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.data_export import DataExportService


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.profiles = ProfileRepository(session)
        self.sessions = UserSessionRepository(session)
        self.consents = ConsentLogRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.audit = AuditService(session)

    async def update_account(
        self,
        user: User,
        *,
        full_name: str | None,
        profile_data: dict[str, Any],
        context: RequestContext,
    ) -> User:
        changed: list[str] = []
        if full_name and full_name.strip() != user.full_name:
            user.full_name = full_name.strip()
            changed.append("full_name")

        profile = user.profile
        if profile is None:
            profile = Profile(user_id=user.id)
            self.session.add(profile)
            await self.session.flush()
            user.profile = profile

        for field, value in profile_data.items():
            if value is None:
                continue
            if getattr(profile, field, None) != value:
                setattr(profile, field, value)
                changed.append(f"profile.{field}")

        if changed:
            await self.audit.record(
                AuditAction.USER_PROFILE_UPDATED,
                actor=user,
                actor_ip=context.ip_address,
                resource_type="user",
                resource_id=user.public_id,
                meta={"fields": changed},
            )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def export_data(self, user: User, context: RequestContext) -> dict[str, Any]:
        """Exportação LGPD: tudo o que a plataforma guarda sobre a conta."""
        sessions = await self.sessions.list_active(user.id)
        consents = await self.consents.list_for_user(user.id)
        logs, _ = await self.audit_logs.search(limit=500, offset=0, actor_user_id=user.id)

        payload: dict[str, Any] = {
            "exported_at": datetime.now(UTC).isoformat(),
            "account": {
                "public_id": user.public_id,
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status,
                "email_verified_at": _iso(user.email_verified_at),
                "last_login_at": _iso(user.last_login_at),
                "created_at": _iso(user.created_at),
                "roles": [role.slug for role in user.roles],
            },
            "profile": _profile_dict(user.profile),
            "sessions": [
                {
                    "public_id": item.public_id,
                    "device_label": item.device_label,
                    "user_agent": item.user_agent,
                    "ip_address": item.ip_address,
                    "created_at": _iso(item.created_at),
                    "last_used_at": _iso(item.last_used_at),
                }
                for item in sessions
            ],
            "consents": [
                {
                    "kind": item.kind,
                    "version": item.version,
                    "granted": item.granted,
                    "created_at": _iso(item.created_at),
                }
                for item in consents
            ],
            "activity_log": [
                {
                    "action": item.action,
                    "status": item.status,
                    "resource_type": item.resource_type,
                    "created_at": _iso(item.created_at),
                }
                for item in logs
            ],
        }
        # O que a conta gerou usando a plataforma — estudo, questões, memória,
        # conversas, gamificação, analytics e assinatura.
        payload.update(await DataExportService(self.session).collect(user))
        await self.audit.record(
            AuditAction.USER_DATA_EXPORTED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
        )
        await self.session.commit()
        return payload

    async def delete_account(self, user: User, context: RequestContext) -> None:
        """Exclusão LGPD: anonimiza dados pessoais e revoga todos os acessos."""
        anonymous = f"deleted-{new_ulid().lower()}@anonimizado.mestreconcurso.com.br"
        await self.audit.record(
            AuditAction.USER_ACCOUNT_DELETED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
        )
        await self.sessions.revoke_all_for_user(user.id, "ACCOUNT_DELETED")

        user.email = anonymous
        user.full_name = "Conta removida"
        user.status = UserStatus.DELETED
        user.deleted_at = datetime.now(UTC)
        user.email_verified_at = None
        user.password_hash = ""
        if user.profile is not None:
            profile = user.profile
            profile.avatar_url = None
            profile.phone = None
            profile.birth_date = None
            profile.city = None
            profile.state = None
            profile.bio = None
            profile.study_goal = None
            profile.preferences = {}
        await self.session.commit()


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _profile_dict(profile: Profile | None) -> dict[str, Any]:
    if profile is None:
        return {}
    return {
        "phone": profile.phone,
        "birth_date": profile.birth_date.isoformat() if profile.birth_date else None,
        "city": profile.city,
        "state": profile.state,
        "timezone": profile.timezone,
        "locale": profile.locale,
        "theme": profile.theme,
        "study_goal": profile.study_goal,
        "bio": profile.bio,
        "preferences": profile.preferences,
        "onboarding_completed_at": _iso(profile.onboarding_completed_at),
    }
