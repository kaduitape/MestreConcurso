"""Auxiliares para montar cenários de teste através da própria API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
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
    name: str = "PCDF — Agente de Polícia",
    year: int | None = None,
    exam_date: str | None = None,
    is_published: bool = True,
) -> dict[str, Any]:
    """Concurso com prova no futuro — datas relativas mantêm os testes estáveis."""
    exam = (
        date.today() + timedelta(days=200) if exam_date is None else date.fromisoformat(exam_date)
    )
    response = await client.post(
        "/api/v1/admin/catalog/competitions",
        headers=user.auth_header,
        json={
            "name": name,
            "year": year or exam.year,
            "organization_public_id": organization_public_id,
            "exam_board_public_id": exam_board_public_id,
            "status": "OPEN",
            "vacancies_total": 1200,
            "exam_date": exam.isoformat(),
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


async def configure_ai(
    client: AsyncClient,
    admin: RegisteredUser,
    *,
    features: tuple[str, ...] = ("notice.extraction",),
) -> None:
    """Deixa o provedor de IA pronto e vinculado às funcionalidades informadas."""
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": "sk-proj-chave-de-teste-1234567890"},
    )
    synced = await client.post(
        "/api/v1/admin/ai/providers/openai/models/sync", headers=admin.auth_header
    )
    assert synced.status_code == 200, synced.text
    activated = await client.patch(
        "/api/v1/admin/ai/providers/openai",
        headers=admin.auth_header,
        json={"is_active": True},
    )
    assert activated.status_code == 200, activated.text

    for feature in features:
        model = "text-embedding-3-small" if feature == "embeddings.default" else "gpt-4o-mini"
        bound = await client.put(
            f"/api/v1/admin/ai/features/{feature}",
            headers=admin.auth_header,
            json={
                "provider_slug": "openai",
                "model_slug": model,
                "is_enabled": True,
            },
        )
        assert bound.status_code == 200, bound.text


async def create_notice_with_pdf(
    client: AsyncClient,
    admin: RegisteredUser,
    *,
    pdf: bytes,
    title: str = "Edital nº 1/2026 — Agente de Polícia",
) -> str:
    """Cadastra o edital e envia o PDF. Devolve o public_id do edital."""
    created = await client.post(
        "/api/v1/admin/notices", headers=admin.auth_header, json={"title": title}
    )
    assert created.status_code == 201, created.text
    notice_id = created.json()["public_id"]

    uploaded = await client.post(
        f"/api/v1/admin/notices/{notice_id}/files",
        headers=admin.auth_header,
        files={"file": ("edital.pdf", pdf, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    return str(notice_id)


async def create_position_with_subjects(
    client: AsyncClient,
    admin: RegisteredUser,
    *,
    subjects: tuple[tuple[str, str, int], ...] = (
        ("Direito Penal", "3.00", 20),
        ("Português", "2.00", 20),
        ("Informática", "1.00", 8),
    ),
) -> dict[str, Any]:
    """Cria concurso + cargo + disciplinas vinculadas. Devolve o cargo criado."""
    organization = await create_organization(client, admin)
    board = await create_board(client, admin)
    competition = await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=board["public_id"],
    )
    created = await client.post(
        f"/api/v1/admin/catalog/competitions/{competition['public_id']}/positions",
        headers=admin.auth_header,
        json={"name": "Agente de Polícia", "questions_count": 120},
    )
    assert created.status_code == 201, created.text
    position = created.json()

    for name, weight, questions in subjects:
        subject = await create_subject(client, admin, name=name)
        linked = await client.put(
            f"/api/v1/admin/catalog/positions/{position['public_id']}/subjects",
            headers=admin.auth_header,
            json={
                "subject_public_id": subject["public_id"],
                "weight": weight,
                "questions_count": questions,
            },
        )
        assert linked.status_code == 200, linked.text

    return position


WEEKDAY_AVAILABILITY = {"0": 120, "1": 120, "2": 120, "3": 120, "4": 120, "5": 240}
