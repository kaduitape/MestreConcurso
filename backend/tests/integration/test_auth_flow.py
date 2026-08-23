"""Fluxo completo de autenticação."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import DEFAULT_PASSWORD, create_user, login, register_and_verify

REGISTER_PAYLOAD = {
    "email": "novo@exemplo.com.br",
    "password": DEFAULT_PASSWORD,
    "full_name": "Novo Candidato",
    "accepted_terms": True,
}


async def test_health_and_readiness(client: AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.headers["X-Request-ID"]

    ready = await client.get("/ready")
    assert ready.json()["checks"]["database"] is True


async def test_register_requires_terms_and_strong_password(client: AsyncClient) -> None:
    weak = await client.post(
        "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "password": "12345678"}
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "weak_password"

    no_terms = await client.post(
        "/api/v1/auth/register", json={**REGISTER_PAYLOAD, "accepted_terms": False}
    )
    assert no_terms.status_code == 422


async def test_register_then_verify_then_login(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    created = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert created.status_code == 201

    duplicated = await client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["code"] == "email_already_registered"

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTER_PAYLOAD["email"], "password": DEFAULT_PASSWORD},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "email_not_verified"

    token = emails.last_token("verificar-email")
    verified = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200

    reused = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert reused.status_code == 400

    tokens = await login(client, REGISTER_PAYLOAD["email"])
    assert tokens["expires_in"] > 0

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == REGISTER_PAYLOAD["email"]
    assert body["status"] == "ACTIVE"
    assert [role["slug"] for role in body["roles"]] == ["student"]


async def test_login_with_wrong_password_locks_account(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    await register_and_verify(client, emails, email="lock@exemplo.com.br")
    for _ in range(3):  # MAX_LOGIN_ATTEMPTS=3 no ambiente de teste
        failed = await client.post(
            "/api/v1/auth/login", json={"email": "lock@exemplo.com.br", "password": "Errada@123"}
        )
        assert failed.status_code == 401

    locked = await client.post(
        "/api/v1/auth/login",
        json={"email": "lock@exemplo.com.br", "password": DEFAULT_PASSWORD},
    )
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "account_locked"


async def test_unknown_email_returns_same_error_as_wrong_password(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "inexistente@exemplo.com.br", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_refresh_rotates_and_detects_reuse(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="rotacao@exemplo.com.br")

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": user.refresh_token})
    assert rotated.status_code == 200
    new_tokens = rotated.json()
    assert new_tokens["refresh_token"] != user.refresh_token

    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": user.refresh_token})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "refresh_token_reuse"

    # A família inteira foi revogada: o token novo também deixa de funcionar.
    after_reuse = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert after_reuse.status_code == 401


async def test_logout_invalidates_access_token(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    user = await create_user(client, emails, email="logout@exemplo.com.br")
    logout = await client.post("/api/v1/auth/logout", headers=user.auth_header)
    assert logout.status_code == 200

    me = await client.get("/api/v1/auth/me", headers=user.auth_header)
    assert me.status_code == 401
    assert me.json()["error"]["code"] == "session_revoked"


async def test_password_reset_flow(client: AsyncClient, emails: CapturingDispatcher) -> None:
    user = await create_user(client, emails, email="reset@exemplo.com.br")

    unknown = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "ninguem@exemplo.com.br"}
    )
    requested = await client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    # Mesma resposta para e-mail existente e inexistente (evita enumeração).
    assert unknown.json() == requested.json()

    token = emails.last_token("redefinir-senha")
    new_password = "NovaSenha@2026"
    reset = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": new_password}
    )
    assert reset.status_code == 200

    # Sessões anteriores foram encerradas e a senha antiga não vale mais.
    assert (await client.get("/api/v1/auth/me", headers=user.auth_header)).status_code == 401
    old = await client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": user.password}
    )
    assert old.status_code == 401
    await login(client, user.email, new_password)

    replay = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "Outra@Senha123"}
    )
    assert replay.status_code == 400


async def test_protected_route_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["request_id"]
