"""Conta do usuário: perfil, senha, dispositivos e LGPD."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import DEFAULT_PASSWORD, create_user, login


async def test_update_profile(client: AsyncClient, emails: CapturingDispatcher) -> None:
    user = await create_user(client, emails, email="perfil@exemplo.com.br")
    response = await client.patch(
        "/api/v1/users/me",
        headers=user.auth_header,
        json={
            "full_name": "Carlos Eduardo",
            "profile": {"city": "Brasília", "state": "DF", "theme": "dark"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Carlos Eduardo"
    assert body["profile"]["city"] == "Brasília"
    assert body["profile"]["theme"] == "dark"


async def test_invalid_theme_is_rejected(client: AsyncClient, emails: CapturingDispatcher) -> None:
    user = await create_user(client, emails, email="tema@exemplo.com.br")
    response = await client.patch(
        "/api/v1/users/me", headers=user.auth_header, json={"profile": {"theme": "neon"}}
    )
    assert response.status_code == 422


async def test_change_password_keeps_current_session_and_revokes_others(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="senha@exemplo.com.br")
    other = await login(client, user.email)
    other_header = {"Authorization": f"Bearer {other['access_token']}"}

    wrong = await client.post(
        "/api/v1/users/me/change-password",
        headers=user.auth_header,
        json={"current_password": "Errada@123", "new_password": "NovaSenha@2026"},
    )
    assert wrong.status_code == 401

    changed = await client.post(
        "/api/v1/users/me/change-password",
        headers=user.auth_header,
        json={"current_password": DEFAULT_PASSWORD, "new_password": "NovaSenha@2026"},
    )
    assert changed.status_code == 200

    assert (await client.get("/api/v1/auth/me", headers=user.auth_header)).status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=other_header)).status_code == 401
    await login(client, user.email, "NovaSenha@2026")


async def test_list_and_revoke_devices(client: AsyncClient, emails: CapturingDispatcher) -> None:
    user = await create_user(client, emails, email="dispositivos@exemplo.com.br")
    other = await login(client, user.email)

    listed = await client.get("/api/v1/users/me/sessions", headers=user.auth_header)
    assert listed.status_code == 200
    sessions = listed.json()
    assert len(sessions) == 2
    assert sum(1 for item in sessions if item["is_current"]) == 1

    revoked = await client.delete(
        f"/api/v1/users/me/sessions/{other['session_id']}", headers=user.auth_header
    )
    assert revoked.status_code == 200

    remaining = (await client.get("/api/v1/users/me/sessions", headers=user.auth_header)).json()
    assert len(remaining) == 1
    assert remaining[0]["is_current"] is True


async def test_logout_all_revokes_every_session(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="sairtudo@exemplo.com.br")
    other = await login(client, user.email)
    response = await client.post("/api/v1/auth/logout-all", headers=user.auth_header)
    assert response.status_code == 200
    assert response.json()["detail"]["revoked_sessions"] == 2

    header = {"Authorization": f"Bearer {other['access_token']}"}
    assert (await client.get("/api/v1/auth/me", headers=header)).status_code == 401


async def test_export_personal_data(client: AsyncClient, emails: CapturingDispatcher) -> None:
    user = await create_user(client, emails, email="lgpd@exemplo.com.br")
    response = await client.get("/api/v1/users/me/export", headers=user.auth_header)
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    payload = response.json()
    assert payload["account"]["email"] == user.email
    assert {item["kind"] for item in payload["consents"]} == {"TOS", "PRIVACY"}
    assert payload["activity_log"]


async def test_delete_account_anonymizes_and_blocks_access(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="excluir@exemplo.com.br")

    wrong_confirmation = await client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=user.auth_header,
        json={"password": DEFAULT_PASSWORD, "confirmation": "sim"},
    )
    assert wrong_confirmation.status_code == 401

    deleted = await client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=user.auth_header,
        json={"password": DEFAULT_PASSWORD, "confirmation": "EXCLUIR"},
    )
    assert deleted.status_code == 200

    blocked = await client.get("/api/v1/auth/me", headers=user.auth_header)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "account_inactive"

    relogin = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": DEFAULT_PASSWORD}
    )
    assert relogin.status_code == 401
