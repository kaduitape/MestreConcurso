"""Testes da avaliação de permissões."""

from __future__ import annotations

from app.domain.permissions import PERMISSIONS, ROLES, USERS_READ, USERS_WRITE
from app.models.rbac import Permission, Role
from app.models.user import User


def _role(slug: str, *slugs: str) -> Role:
    role = Role(slug=slug, name=slug, description="")
    role.permissions = [
        Permission(slug=item, resource=item.split(":")[0], action=item.split(":")[1])
        for item in slugs
    ]
    return role


def test_user_without_roles_has_no_permission() -> None:
    user = User(email="a@b.com.br", password_hash="x", full_name="A")
    assert user.has_permission(USERS_READ) is False


def test_permissions_are_union_of_roles() -> None:
    user = User(email="a@b.com.br", password_hash="x", full_name="A")
    user.roles = [_role("leitura", USERS_READ), _role("escrita", USERS_WRITE)]
    assert user.permission_slugs == {USERS_READ, USERS_WRITE}
    assert user.has_permission(USERS_READ) is True


def test_wildcard_by_resource() -> None:
    user = User(email="a@b.com.br", password_hash="x", full_name="A")
    user.roles = [_role("gestor", "users:*")]
    assert user.has_permission(USERS_WRITE) is True
    assert user.has_permission("audit:read") is False


def test_superuser_has_every_permission() -> None:
    user = User(email="a@b.com.br", password_hash="x", full_name="A", is_superuser=True)
    assert user.has_permission("qualquer:coisa") is True


def test_role_catalog_only_references_declared_permissions() -> None:
    declared = {permission.slug for permission in PERMISSIONS}
    for role in ROLES:
        assert set(role.permissions) <= declared, role.slug
