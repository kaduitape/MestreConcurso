"""Casos de uso do painel administrativo."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.models.audit import AuditAction, AuditLog
from app.models.user import User, UserStatus
from app.models.user_session import UserSession
from app.repositories.audit import AuditLogRepository
from app.repositories.rbac import PermissionRepository, RoleRepository
from app.repositories.user import UserRepository
from app.repositories.user_session import UserSessionRepository
from app.schemas.admin import AdminOverview
from app.services.audit import AuditService
from app.services.auth import RequestContext


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.permissions = PermissionRepository(session)
        self.sessions = UserSessionRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.audit = AuditService(session)

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None,
        status: str | None,
        role: str | None,
    ) -> tuple[Sequence[User], int]:
        return await self.users.search(
            limit=limit, offset=offset, search=search, status=status, role=role
        )

    async def get_user(self, public_id: str) -> User:
        user = await self.users.get_by_public_id(public_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        return user

    async def update_user(
        self,
        actor: User,
        public_id: str,
        *,
        status: str | None,
        full_name: str | None,
        context: RequestContext,
    ) -> User:
        user = await self.get_user(public_id)
        if user.id == actor.id and status and status != user.status:
            raise PermissionDeniedError("Você não pode alterar o status da própria conta.")

        changes: dict[str, str] = {}
        if status and status != user.status:
            changes["status"] = f"{user.status}->{status}"
            user.status = status
            if status == UserStatus.SUSPENDED:
                await self.sessions.revoke_all_for_user(user.id, "ADMIN_SUSPENDED")
        if full_name and full_name.strip() != user.full_name:
            changes["full_name"] = full_name.strip()
            user.full_name = full_name.strip()

        if changes:
            await self.audit.record(
                AuditAction.ADMIN_USER_UPDATED,
                actor=actor,
                actor_ip=context.ip_address,
                resource_type="user",
                resource_id=user.public_id,
                meta={"changes": changes},
            )
        await self.session.commit()
        return await self.get_user(public_id)

    async def assign_roles(
        self, actor: User, public_id: str, slugs: list[str], context: RequestContext
    ) -> User:
        user = await self.get_user(public_id)
        roles = await self.roles.list_by_slugs(slugs)
        found = {role.slug for role in roles}
        unknown = sorted(set(slugs) - found)
        if unknown:
            raise ValidationError("Papéis inexistentes.", details={"unknown_roles": unknown})
        if user.id == actor.id and not actor.is_superuser:
            raise PermissionDeniedError("Você não pode alterar os próprios papéis.")

        previous = sorted(role.slug for role in user.roles)
        user.roles = list(roles)
        await self.audit.record(
            AuditAction.ADMIN_ROLES_ASSIGNED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
            meta={"from": previous, "to": sorted(found)},
        )
        await self.session.commit()
        return await self.get_user(public_id)

    async def list_audit_logs(
        self,
        *,
        limit: int,
        offset: int,
        action: str | None = None,
        since_days: int | None = None,
    ) -> tuple[Sequence[AuditLog], int]:
        since = datetime.now(UTC) - timedelta(days=since_days) if since_days else None
        return await self.audit_logs.search(limit=limit, offset=offset, action=action, since=since)

    async def overview(self) -> AdminOverview:
        """Métricas do painel — contagens reais, sem estimativa."""
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)
        day_ago = now - timedelta(hours=24)

        status_rows = (
            await self.session.execute(
                select(User.status, func.count())
                .where(User.deleted_at.is_(None))
                .group_by(User.status)
            )
        ).all()
        by_status = {str(row[0]): int(row[1]) for row in status_rows}

        recent = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(User)
                    .where(User.created_at >= week_ago, User.deleted_at.is_(None))
                )
            ).scalar_one()
        )
        active_sessions = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(UserSession)
                    .where(UserSession.revoked_at.is_(None), UserSession.expires_at > now)
                )
            ).scalar_one()
        )
        logins = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(AuditLog)
                    .where(
                        AuditLog.action == AuditAction.USER_LOGIN,
                        AuditLog.created_at >= day_ago,
                    )
                )
            ).scalar_one()
        )
        return AdminOverview(
            users_total=sum(by_status.values()),
            users_active=by_status.get(UserStatus.ACTIVE, 0),
            users_pending=by_status.get(UserStatus.PENDING, 0),
            users_suspended=by_status.get(UserStatus.SUSPENDED, 0),
            users_created_last_7_days=recent,
            sessions_active=active_sessions,
            logins_last_24h=logins,
        )
