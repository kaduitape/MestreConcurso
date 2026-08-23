"""Auxiliares para montar cenários de teste através da própria API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher

DEFAULT_PASSWORD = "Senha@Forte123"


@dataclass(slots=True)
class RegisteredUser:
    email: str
    password: str
    access_token: str
    refresh_token: str
    session_id: str

    @property
    def auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


async def register_and_verify(
    client: AsyncClient,
    emails: CapturingDispatcher,
    *,
    email: str = "candidato@exemplo.com.br",
    password: str = DEFAULT_PASSWORD,
    full_name: str = "Candidato Exemplo",
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": full_name,
            "accepted_terms": True,
        },
    )
    assert response.status_code == 201, response.text
    token = emails.last_token("verificar-email")
    verify = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verify.status_code == 200, verify.text


async def login(
    client: AsyncClient, email: str, password: str = DEFAULT_PASSWORD
) -> dict[str, Any]:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


async def create_user(
    client: AsyncClient,
    emails: CapturingDispatcher,
    *,
    email: str = "candidato@exemplo.com.br",
    password: str = DEFAULT_PASSWORD,
    full_name: str = "Candidato Exemplo",
) -> RegisteredUser:
    await register_and_verify(client, emails, email=email, password=password, full_name=full_name)
    tokens = await login(client, email, password)
    return RegisteredUser(
        email=email,
        password=password,
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        session_id=tokens["session_id"],
    )


async def promote_to_admin(email: str) -> None:
    """Concede o papel de administrador diretamente na base (setup de cenário)."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.db.session import get_session_factory
    from app.models.rbac import Role
    from app.models.user import User

    factory = get_session_factory()
    async with factory() as session:
        user = (
            await session.execute(
                select(User).where(User.email == email).options(selectinload(User.roles))
            )
        ).scalar_one()
        role = (await session.execute(select(Role).where(Role.slug == "admin"))).scalar_one()
        user.roles = [role]
        await session.commit()


async def create_admin(
    client: AsyncClient,
    emails: CapturingDispatcher,
    *,
    email: str = "gestor@exemplo.com.br",
) -> RegisteredUser:
    """Cria um usuário e o promove a administrador (setup de cenário)."""
    user = await create_user(client, emails, email=email)
    await promote_to_admin(email)
    return user


MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


async def create_board(
    client: AsyncClient, user: RegisteredUser, *, name: str = "Cebraspe", short: str = "CESPE"
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/catalog/boards",
        headers=user.auth_header,
        json={"name": name, "short_name": short},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_organization(
    client: AsyncClient,
    user: RegisteredUser,
    *,
    name: str = "Polícia Civil do Distrito Federal",
    short: str = "PCDF",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/catalog/organizations",
        headers=user.auth_header,
        json={"name": name, "short_name": short, "sphere": "DISTRITAL", "uf": "DF"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_competition(
    client: AsyncClient,
    user: RegisteredUser,
    *,
    organization_public_id: str,
    exam_board_public_id: str | None = None,
    name: str = "PCDF 2026 — Agente de Polícia",
    year: int = 2026,
    is_published: bool = True,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/catalog/competitions",
        headers=user.auth_header,
        json={
            "name": name,
            "year": year,
            "organization_public_id": organization_public_id,
            "exam_board_public_id": exam_board_public_id,
            "status": "OPEN",
            "vacancies_total": 1200,
            "exam_date": "2026-03-15",
            "is_published": is_published,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_subject(
    client: AsyncClient, user: RegisteredUser, *, name: str = "Direito Penal"
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/catalog/subjects",
        headers=user.auth_header,
        json={"name": name, "area": "Direito", "color_token": "subject-direito"},
    )
    assert response.status_code == 201, response.text
    return response.json()
