"""Casos de uso de autenticação, sessões e credenciais."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidTokenError,
    NotFoundError,
    ValidationError,
)
from app.core.ids import new_ulid
from app.core.logging import get_logger
from app.core.security import (
    compare_token_hash,
    create_access_token,
    generate_opaque_token,
    hash_opaque_token,
    hash_password,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.domain.permissions import DEFAULT_ROLE
from app.models.audit import AuditAction, ConsentKind, ConsentLog
from app.models.token import AuthToken, AuthTokenType
from app.models.user import Profile, User, UserStatus
from app.models.user_session import UserSession
from app.repositories.rbac import RoleRepository
from app.repositories.token import AuthTokenRepository
from app.repositories.user import UserRepository
from app.repositories.user_session import UserSessionRepository
from app.services import email as email_templates
from app.services.audit import AuditService
from app.services.mailer import EmailDispatcher, get_email_dispatcher

logger = get_logger(__name__)

TERMS_VERSION = "2026-01"


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Dados da requisição usados em auditoria e sessões."""

    ip_address: str | None = None
    user_agent: str | None = None
    device_label: str | None = None


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    session: UserSession


class AuthService:
    def __init__(self, session: AsyncSession, dispatcher: EmailDispatcher | None = None) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = UserSessionRepository(session)
        self.tokens = AuthTokenRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditService(session)
        self.mailer = dispatcher or get_email_dispatcher()

    # ------------------------------------------------------------------ #
    # Registro e verificação de e-mail
    # ------------------------------------------------------------------ #
    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        context: RequestContext,
    ) -> User:
        normalized = email.strip().lower()
        validate_password_strength(password)

        if await self.users.email_exists(normalized):
            raise EmailAlreadyRegisteredError

        user = User(
            email=normalized,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            status=UserStatus.PENDING,
            password_changed_at=datetime.now(UTC),
        )
        user.profile = Profile()
        default_role = await self.roles.get_by_slug(DEFAULT_ROLE)
        if default_role is not None:
            user.roles.append(default_role)
        self.users.add(user)
        await self.session.flush()

        for kind in (ConsentKind.TOS, ConsentKind.PRIVACY):
            self.session.add(
                ConsentLog(
                    user_id=user.id,
                    kind=kind,
                    version=TERMS_VERSION,
                    granted=True,
                    ip_address=context.ip_address,
                    user_agent=context.user_agent,
                )
            )

        token = await self._create_auth_token(user, AuthTokenType.EMAIL_VERIFY, context.ip_address)
        await self.audit.record(
            AuditAction.USER_REGISTERED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
        )
        await self.session.commit()

        await self.mailer.dispatch(
            email_templates.build_verification_email(user.email, user.full_name, token)
        )
        return user

    async def verify_email(self, token: str, context: RequestContext) -> User:
        auth_token = await self.tokens.get_valid(
            hash_opaque_token(token), AuthTokenType.EMAIL_VERIFY
        )
        if auth_token is None:
            raise InvalidTokenError("Link de verificação inválido ou expirado.")

        user = await self.users.get_with_relations(auth_token.user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")

        auth_token.used_at = datetime.now(UTC)
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(UTC)
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.ACTIVE

        await self.audit.record(
            AuditAction.USER_EMAIL_VERIFIED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
        )
        await self.session.commit()
        return user

    async def resend_verification(self, email: str, context: RequestContext) -> None:
        """Sempre responde igual — não revela se o e-mail existe."""
        user = await self.users.get_by_email(email)
        if user is None or user.is_email_verified or user.status == UserStatus.DELETED:
            return
        token = await self._create_auth_token(user, AuthTokenType.EMAIL_VERIFY, context.ip_address)
        await self.session.commit()
        await self.mailer.dispatch(
            email_templates.build_verification_email(user.email, user.full_name, token)
        )

    # ------------------------------------------------------------------ #
    # Login / sessões
    # ------------------------------------------------------------------ #
    async def login(
        self, *, email: str, password: str, context: RequestContext
    ) -> tuple[User, IssuedTokens]:
        user = await self.users.get_by_email(email)
        now = datetime.now(UTC)

        if user is None:
            # Custo de verificação equivalente ao caminho feliz (anti timing attack).
            hash_password(password)
            await self._record_failed_login(None, email, context)
            raise InvalidCredentialsError

        if user.locked_until and _aware(user.locked_until) > now:
            raise AccountLockedError(
                details={"locked_until": _aware(user.locked_until).isoformat()}
            )

        if not verify_password(password, user.password_hash):
            await self._register_failed_attempt(user, context)
            raise InvalidCredentialsError

        if user.status == UserStatus.SUSPENDED or user.deleted_at is not None:
            raise AccountInactiveError
        if not user.is_email_verified:
            raise EmailNotVerifiedError

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now

        tokens = await self._issue_session(user, context)
        await self.audit.record(
            AuditAction.USER_LOGIN,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="session",
            resource_id=tokens.session.public_id,
        )
        await self.session.commit()
        return user, tokens

    async def refresh(self, refresh_token: str, context: RequestContext) -> IssuedTokens:
        token_hash = hash_opaque_token(refresh_token)
        current = await self.sessions.get_by_token_hash(token_hash)
        if current is None:
            raise InvalidTokenError("Refresh token inválido.")

        now = datetime.now(UTC)
        if current.revoked_at is not None:
            # Token já rotacionado/revogado sendo reapresentado: possível roubo.
            revoked = await self.sessions.revoke_family(current.family_id, "REUSE_DETECTED")
            await self.audit.record(
                AuditAction.SESSION_REUSE_DETECTED,
                actor_ip=context.ip_address,
                resource_type="session",
                resource_id=current.public_id,
                status="BLOCKED",
                meta={"family_id": current.family_id, "revoked_sessions": revoked},
            )
            await self.session.commit()
            raise AuthenticationError(
                "Sessão encerrada por segurança. Faça login novamente.",
                code="refresh_token_reuse",
            )

        if _aware(current.expires_at) <= now:
            raise InvalidTokenError("Sessão expirada. Faça login novamente.")

        user = await self.users.get_with_relations(current.user_id)
        if user is None or not user.is_active:
            raise AccountInactiveError

        current.revoked_at = now
        current.revoked_reason = "ROTATED"
        current.last_used_at = now

        tokens = await self._issue_session(
            user,
            context,
            family_id=current.family_id,
            device_label=current.device_label,
            created_at=_aware(current.created_at),
        )
        await self.session.commit()
        return tokens

    async def logout(self, user: User, session_public_id: str, context: RequestContext) -> None:
        session = await self.sessions.get_by_public_id(session_public_id, user.id)
        if session is None:
            raise NotFoundError("Sessão não encontrada.")
        if session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            session.revoked_reason = "LOGOUT"
        await self.audit.record(
            AuditAction.USER_LOGOUT,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="session",
            resource_id=session.public_id,
        )
        await self.session.commit()

    async def logout_all(
        self, user: User, context: RequestContext, *, keep_session_id: int | None = None
    ) -> int:
        revoked = await self.sessions.revoke_all_for_user(
            user.id, "LOGOUT_ALL", except_session_id=keep_session_id
        )
        await self.audit.record(
            AuditAction.USER_LOGOUT_ALL,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
            meta={"revoked_sessions": revoked},
        )
        await self.session.commit()
        return revoked

    async def revoke_session(
        self, user: User, session_public_id: str, context: RequestContext
    ) -> None:
        session = await self.sessions.get_by_public_id(session_public_id, user.id)
        if session is None:
            raise NotFoundError("Sessão não encontrada.")
        if session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
            session.revoked_reason = "REVOKED_BY_USER"
        await self.audit.record(
            AuditAction.SESSION_REVOKED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="session",
            resource_id=session.public_id,
        )
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Senha
    # ------------------------------------------------------------------ #
    async def request_password_reset(self, email: str, context: RequestContext) -> None:
        user = await self.users.get_by_email(email)
        if user is None or user.status == UserStatus.DELETED:
            return
        token = await self._create_auth_token(
            user, AuthTokenType.PASSWORD_RESET, context.ip_address
        )
        await self.session.commit()
        await self.mailer.dispatch(
            email_templates.build_password_reset_email(user.email, user.full_name, token)
        )

    async def reset_password(self, token: str, new_password: str, context: RequestContext) -> None:
        validate_password_strength(new_password)
        auth_token = await self.tokens.get_valid(
            hash_opaque_token(token), AuthTokenType.PASSWORD_RESET
        )
        if auth_token is None:
            raise InvalidTokenError("Link de redefinição inválido ou expirado.")

        user = await self.users.get_with_relations(auth_token.user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")

        auth_token.used_at = datetime.now(UTC)
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        user.failed_login_count = 0
        user.locked_until = None
        if user.status == UserStatus.PENDING and user.is_email_verified:
            user.status = UserStatus.ACTIVE

        await self.sessions.revoke_all_for_user(user.id, "PASSWORD_RESET")
        await self.audit.record(
            AuditAction.USER_PASSWORD_RESET,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
        )
        await self.session.commit()
        await self.mailer.dispatch(
            email_templates.build_password_changed_email(user.email, user.full_name)
        )

    async def change_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
        context: RequestContext,
        keep_session_id: int | None = None,
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("A senha atual está incorreta.")
        if current_password == new_password:
            raise ValidationError("A nova senha deve ser diferente da atual.")
        validate_password_strength(new_password)

        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(UTC)
        await self.sessions.revoke_all_for_user(
            user.id, "PASSWORD_CHANGED", except_session_id=keep_session_id
        )
        await self.audit.record(
            AuditAction.USER_PASSWORD_CHANGED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id,
        )
        await self.session.commit()
        await self.mailer.dispatch(
            email_templates.build_password_changed_email(user.email, user.full_name)
        )

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    async def _issue_session(
        self,
        user: User,
        context: RequestContext,
        *,
        family_id: str | None = None,
        device_label: str | None = None,
        created_at: datetime | None = None,
    ) -> IssuedTokens:
        now = datetime.now(UTC)
        refresh_token = generate_opaque_token()
        session = UserSession(
            user_id=user.id,
            refresh_token_hash=hash_opaque_token(refresh_token),
            family_id=family_id or new_ulid(),
            device_label=device_label or context.device_label,
            user_agent=(context.user_agent or "")[:400] or None,
            ip_address=context.ip_address,
            expires_at=now + timedelta(days=settings.refresh_token_expire_days),
            last_used_at=now,
        )
        if created_at is not None:
            session.created_at = created_at
        self.session.add(session)
        await self.session.flush()

        access_token, expires_at = create_access_token(user.public_id, session_id=session.public_id)
        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int((expires_at - now).total_seconds()),
            session=session,
        )

    async def _create_auth_token(
        self, user: User, token_type: AuthTokenType, ip_address: str | None
    ) -> str:
        await self.tokens.invalidate_pending(user.id, token_type)
        raw_token = generate_opaque_token(32)
        lifetime = (
            timedelta(hours=settings.email_verification_expire_hours)
            if token_type == AuthTokenType.EMAIL_VERIFY
            else timedelta(minutes=settings.password_reset_expire_minutes)
        )
        self.session.add(
            AuthToken(
                user_id=user.id,
                type=token_type,
                token_hash=hash_opaque_token(raw_token),
                expires_at=datetime.now(UTC) + lifetime,
                requested_ip=ip_address,
            )
        )
        await self.session.flush()
        return raw_token

    async def _register_failed_attempt(self, user: User, context: RequestContext) -> None:
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_login_attempts:
            user.locked_until = datetime.now(UTC) + timedelta(
                minutes=settings.login_lockout_minutes
            )
            user.failed_login_count = 0
        await self._record_failed_login(user, user.email, context)

    async def _record_failed_login(
        self, user: User | None, email: str, context: RequestContext
    ) -> None:
        await self.audit.record(
            AuditAction.USER_LOGIN_FAILED,
            actor=user,
            actor_email=email,
            actor_ip=context.ip_address,
            resource_type="user",
            resource_id=user.public_id if user else None,
            status="FAILURE",
        )
        await self.session.commit()


def verify_token_matches(raw_token: str, token_hash: str) -> bool:
    """Exposto para testes e verificações pontuais."""
    return compare_token_hash(raw_token, token_hash)


def _aware(value: datetime) -> datetime:
    """MySQL/SQLite podem devolver datetimes ingênuos — normaliza para UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
