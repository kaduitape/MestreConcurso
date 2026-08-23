"""Painel administrativo e controle de permissões."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import create_user, promote_to_admin


async def test_student_cannot_access_admin(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno@exemplo.com.br")
    for path in ("/api/v1/admin/users", "/api/v1/admin/overview", "/api/v1/admin/audit-logs"):
        response = await client.get(path, headers=student.auth_header)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "permission_denied"


async def test_admin_lists_filters_and_updates_users(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_user(client, emails, email="admin@exemplo.com.br")
    await promote_to_admin(admin.email)
    student = await create_user(client, emails, email="aluno2@exemplo.com.br")

    listing = await client.get("/api/v1/admin/users?page=1&page_size=10", headers=admin.auth_header)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert {item["email"] for item in body["items"]} == {admin.email, student.email}

    filtered = await client.get("/api/v1/admin/users?search=aluno2", headers=admin.auth_header)
    assert filtered.json()["total"] == 1

    by_role = await client.get("/api/v1/admin/users?role=admin", headers=admin.auth_header)
    assert by_role.json()["total"] == 1

    detail = await client.get(
        f"/api/v1/admin/users/{filtered.json()['items'][0]['public_id']}",
        headers=admin.auth_header,
    )
    assert detail.status_code == 200


async def test_admin_suspends_user_and_kills_sessions(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_user(client, emails, email="admin2@exemplo.com.br")
    await promote_to_admin(admin.email)
    student = await create_user(client, emails, email="suspender@exemplo.com.br")
    public_id = (
        await client.get(f"/api/v1/admin/users?search={student.email}", headers=admin.auth_header)
    ).json()["items"][0]["public_id"]

    updated = await client.patch(
        f"/api/v1/admin/users/{public_id}",
        headers=admin.auth_header,
        json={"status": "SUSPENDED"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "SUSPENDED"

    blocked = await client.get("/api/v1/auth/me", headers=student.auth_header)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "account_inactive"


async def test_admin_cannot_change_own_status(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_user(client, emails, email="admin3@exemplo.com.br")
    await promote_to_admin(admin.email)
    me = await client.get("/api/v1/auth/me", headers=admin.auth_header)
    response = await client.patch(
        f"/api/v1/admin/users/{me.json()['public_id']}",
        headers=admin.auth_header,
        json={"status": "SUSPENDED"},
    )
    assert response.status_code == 403


async def test_admin_assigns_roles(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_user(client, emails, email="admin4@exemplo.com.br")
    await promote_to_admin(admin.email)
    student = await create_user(client, emails, email="promover@exemplo.com.br")
    public_id = (
        await client.get(f"/api/v1/admin/users?search={student.email}", headers=admin.auth_header)
    ).json()["items"][0]["public_id"]

    unknown = await client.put(
        f"/api/v1/admin/users/{public_id}/roles",
        headers=admin.auth_header,
        json={"roles": ["inexistente"]},
    )
    assert unknown.status_code == 422
    assert unknown.json()["error"]["details"]["unknown_roles"] == ["inexistente"]

    assigned = await client.put(
        f"/api/v1/admin/users/{public_id}/roles",
        headers=admin.auth_header,
        json={"roles": ["staff"]},
    )
    assert assigned.status_code == 200
    assert [role["slug"] for role in assigned.json()["roles"]] == ["staff"]

    # staff enxerga usuários, mas não pode alterá-los.
    staff_view = await client.get("/api/v1/admin/users", headers=student.auth_header)
    assert staff_view.status_code == 200
    staff_write = await client.patch(
        f"/api/v1/admin/users/{public_id}",
        headers=student.auth_header,
        json={"full_name": "Tentativa"},
    )
    assert staff_write.status_code == 403


async def test_overview_and_audit_logs(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_user(client, emails, email="admin5@exemplo.com.br")
    await promote_to_admin(admin.email)
    await create_user(client, emails, email="metricas@exemplo.com.br")

    overview = (await client.get("/api/v1/admin/overview", headers=admin.auth_header)).json()
    assert overview["users_total"] == 2
    assert overview["users_active"] == 2
    assert overview["sessions_active"] == 2
    assert overview["logins_last_24h"] == 2

    logs = await client.get("/api/v1/admin/audit-logs?action=user.login", headers=admin.auth_header)
    assert logs.status_code == 200
    assert logs.json()["total"] == 2

    denied = await client.get("/api/v1/admin/users", headers=admin.auth_header)
    assert denied.status_code == 200

    roles = await client.get("/api/v1/admin/roles", headers=admin.auth_header)
    assert {role["slug"] for role in roles.json()} == {"admin", "staff", "student"}
    permissions = await client.get("/api/v1/admin/permissions", headers=admin.auth_header)
    assert any(item["slug"] == "users:read" for item in permissions.json())


async def test_permission_denied_is_audited(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_user(client, emails, email="admin6@exemplo.com.br")
    await promote_to_admin(admin.email)
    student = await create_user(client, emails, email="negado@exemplo.com.br")
    await client.get("/api/v1/admin/users", headers=student.auth_header)

    logs = await client.get(
        "/api/v1/admin/audit-logs?action=permission.denied", headers=admin.auth_header
    )
    assert logs.json()["total"] == 1
    entry = logs.json()["items"][0]
    assert entry["status"] == "DENIED"
    assert entry["meta"]["required"] == ["users:read"]
