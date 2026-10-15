"""Seed idempotente do RBAC e do administrador inicial."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.domain.permissions import PERMISSIONS, ROLE_ADMIN, ROLES
from app.domain.training.example import (
    EXAMPLE_CHARACTER,
    EXAMPLE_DURATION_MINUTES,
    EXAMPLE_LEVEL,
    EXAMPLE_PUBLIC_ID,
    EXAMPLE_SCRIPT,
    EXAMPLE_STYLE,
    EXAMPLE_SUBJECT,
    EXAMPLE_TITLE,
    EXAMPLE_TOPIC,
)
from app.domain.trap_catalogue import TRAP_PATTERNS
from app.models.intelligence import TrapPattern
from app.models.rbac import Permission, Role
from app.models.training import TrainingLesson, TrainingStatus
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


async def ensure_example_training(session: AsyncSession, author: User | None) -> bool:
    """Instala a aula-modelo do Dia de Treinamento, uma única vez.

    O seed **só cria**. Se a aula já existe, ela não é tocada: alguém pode ter
    reescrito uma cena no estúdio, e sobrescrever isso a cada reinício do
    contêiner apagaria trabalho humano sem avisar.

    Sem administrador não há autor, e sem autor não há aula — o modelo volta no
    próximo seed, depois que o administrador inicial existir.
    """
    if author is None:
        logger.info("seed.training_example.skipped", reason="sem administrador")
        return False

    existing = (
        await session.execute(
            select(TrainingLesson).where(TrainingLesson.public_id == EXAMPLE_PUBLIC_ID)
        )
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("seed.training_example.exists", public_id=EXAMPLE_PUBLIC_ID)
        return False

    session.add(
        TrainingLesson(
            public_id=EXAMPLE_PUBLIC_ID,
            created_by_user_id=author.id,
            title=EXAMPLE_TITLE,
            subject=EXAMPLE_SUBJECT,
            topic=EXAMPLE_TOPIC,
            character_name=EXAMPLE_CHARACTER,
            level=EXAMPLE_LEVEL,
            style=EXAMPLE_STYLE,
            target_duration_minutes=EXAMPLE_DURATION_MINUTES,
            research_before_generate=False,
            status=TrainingStatus.PUBLISHED,
            # Cópia: a constante do módulo é compartilhada pelo processo inteiro,
            # e a validação de roteiro completa campos ausentes no próprio dicionário.
            script=copy.deepcopy(EXAMPLE_SCRIPT),
            published_at=datetime.now(UTC),
        )
    )
    await session.commit()
    logger.info(
        "seed.training_example.created",
        public_id=EXAMPLE_PUBLIC_ID,
        scenes=len(EXAMPLE_SCRIPT["scenes"]),
    )
    return True
