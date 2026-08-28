"""Seed idempotente do RBAC e do administrador inicial."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.permissions import PERMISSIONS, ROLE_ADMIN, ROLES
from app.domain.trap_catalogue import TRAP_PATTERNS
from app.models.intelligence import TrapPattern
from app.models.rbac import Permission, Role
from app.models.user import Profile, User, UserStatus

logger = get_logger(__name__)


async def sync_rbac(session: AsyncSession) -> None:
    """Alinha o banco com o catálogo de permissões/papéis do domínio."""
    existing_permissions = {
        permission.slug: permission
        for permission in (await session.execute(select(Permission))).scalars()
    }
    for spec in PERMISSIONS:
        permission = existing_permissions.get(spec.slug)
        if permission is None:
            permission = Permission(
                slug=spec.slug,
                resource=spec.resource,
                action=spec.action,
                description=spec.description,
            )
            session.add(permission)
            existing_permissions[spec.slug] = permission
        elif permission.description != spec.description:
            permission.description = spec.description
    await session.flush()

    existing_roles = {
        role.slug: role
        for role in (
            await session.execute(select(Role).options(selectinload(Role.permissions)))
        ).scalars()
    }
    for role_spec in ROLES:
        role = existing_roles.get(role_spec.slug)
        if role is None:
            role = Role(
                slug=role_spec.slug,
                name=role_spec.name,
                description=role_spec.description,
                is_system=True,
            )
            session.add(role)
            existing_roles[role_spec.slug] = role
        else:
            role.name = role_spec.name
            role.description = role_spec.description
            role.is_system = True
        role.permissions = [existing_permissions[slug] for slug in role_spec.permissions]
    await session.commit()
    logger.info("seed.rbac.synced", roles=len(ROLES), permissions=len(PERMISSIONS))


async def sync_trap_patterns(session: AsyncSession) -> int:
    """Mantém o catálogo editorial de pegadinhas em dia, sem apagar edições feitas
    no painel: só cria o que falta e atualiza texto de quem veio do catálogo."""
    existing = {
        pattern.slug: pattern for pattern in (await session.execute(select(TrapPattern))).scalars()
    }
    created = 0
    for spec in TRAP_PATTERNS:
        pattern = existing.get(spec.slug)
        if pattern is None:
            session.add(
                TrapPattern(
                    slug=spec.slug,
                    name=spec.name,
                    category=spec.category,
                    description=spec.description,
                    detection_hint=spec.detection_hint,
                    is_active=True,
                )
            )
            created += 1
    await session.commit()
    logger.info("seed.traps.synced", total=len(TRAP_PATTERNS), created=created)
    return created


async def sync_gamification(session: AsyncSession) -> tuple[int, int]:
    """Semeia as regras de pontuação e o catálogo de conquistas."""
    from app.services.game_engine import GameEngine

    engine = GameEngine(session)
    rules = await engine.sync_rules()
    achievements = await engine.sync_achievements()
    logger.info("seed.game.synced", rules=rules, achievements=achievements)
    return rules, achievements


async def ensure_bootstrap_admin(session: AsyncSession) -> User | None:
    """Cria o administrador inicial se ainda não existir nenhum superusuário."""
    existing = (
        await session.execute(select(User).where(User.is_superuser.is_(True)).limit(1))
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("seed.admin.exists", email=existing.email)
        return existing

    email = str(settings.bootstrap_admin_email).strip().lower()
    admin_role = (
        await session.execute(select(Role).where(Role.slug == ROLE_ADMIN))
    ).scalar_one_or_none()

    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=settings.bootstrap_admin_name,
            password_hash=hash_password(settings.bootstrap_admin_password),
            status=UserStatus.ACTIVE,
            email_verified_at=datetime.now(UTC),
            password_changed_at=datetime.now(UTC),
        )
        user.profile = Profile()
        session.add(user)

    user.is_superuser = True
    user.status = UserStatus.ACTIVE
    if admin_role is not None:
        user.roles = [admin_role]
    await session.commit()
    logger.warning(
        "seed.admin.created",
        email=email,
        hint="Troque a senha do administrador no primeiro acesso.",
    )
    return user
