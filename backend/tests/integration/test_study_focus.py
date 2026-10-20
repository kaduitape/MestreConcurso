"""Concurso principal, contagem regressiva e esteira editorial.

A regra que estes testes vigiam é a mesma da barra de FOCO da batalha: **sem
dado real não há número**. Sem concurso escolhido não há contagem; sem data de
prova no edital também não — e nos dois casos a resposta traz o motivo, em vez
de um traço sem explicação ou um número inventado.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin, create_user


async def _competition(
    client: AsyncClient,
    admin: RegisteredUser,
    *,
    name: str = "Concurso de Teste",
    exam_date: str | None = None,
) -> dict[str, Any]:
    org = await client.post(
        "/api/v1/admin/catalog/organizations",
        headers=admin.auth_header,
        json={"name": "Tribunal de Teste", "short_name": "TT", "sphere": "FEDERAL"},
    )
    assert org.status_code == 201, org.text
    payload: dict[str, Any] = {
        "name": name,
        "year": 2026,
        "organization_public_id": org.json()["public_id"],
    }
    if exam_date:
        payload["exam_date"] = exam_date
    created = await client.post(
        "/api/v1/admin/catalog/competitions", headers=admin.auth_header, json=payload
    )
    assert created.status_code == 201, created.text
    return dict(created.json())


async def _publish(client: AsyncClient, admin: RegisteredUser, public_id: str) -> None:
    for destino in ("REVIEW", "PUBLISHED"):
        response = await client.put(
            f"/api/v1/admin/catalog/competitions/{public_id}/editorial-status",
            headers=admin.auth_header,
            json={"editorial_status": destino},
        )
        assert response.status_code == 200, response.text


# --------------------------------------------------------------------------- #
# Esteira editorial
# --------------------------------------------------------------------------- #
async def test_a_competition_starts_as_a_draft_and_is_invisible(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="foco1@exemplo.com.br")
    competition = await _competition(client, admin)

    assert competition["editorial_status"] == "DRAFT"
    assert competition["is_published"] is False


async def test_publishing_is_what_makes_it_visible(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Uma verdade só: o estado editorial manda na visibilidade."""
    admin = await create_admin(client, emails, email="foco2@exemplo.com.br")
    competition = await _competition(client, admin)

    await _publish(client, admin, competition["public_id"])

    aberto = await client.get(
        f"/api/v1/admin/catalog/competitions/{competition['public_id']}",
        headers=admin.auth_header,
    )
    assert aberto.json()["editorial_status"] == "PUBLISHED"
    assert aberto.json()["is_published"] is True


async def test_archiving_takes_it_off_the_air(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="foco3@exemplo.com.br")
    competition = await _competition(client, admin)
    await _publish(client, admin, competition["public_id"])

    arquivado = await client.put(
        f"/api/v1/admin/catalog/competitions/{competition['public_id']}/editorial-status",
        headers=admin.auth_header,
        json={"editorial_status": "ARCHIVED"},
    )

    assert arquivado.status_code == 200
    assert arquivado.json()["is_published"] is False


async def test_a_published_competition_cannot_jump_back_to_draft(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Sairia do ar sem ninguém revisar."""
    admin = await create_admin(client, emails, email="foco4@exemplo.com.br")
    competition = await _competition(client, admin)
    await _publish(client, admin, competition["public_id"])

    response = await client.put(
        f"/api/v1/admin/catalog/competitions/{competition['public_id']}/editorial-status",
        headers=admin.auth_header,
        json={"editorial_status": "DRAFT"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "competition_invalid_transition"


# --------------------------------------------------------------------------- #
# Concurso principal
# --------------------------------------------------------------------------- #
async def test_without_a_choice_there_is_no_countdown_and_the_reason_is_given(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.foco1@exemplo.com.br")

    response = await client.get("/api/v1/users/me/focus", headers=student.auth_header)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["competition_public_id"] is None
    assert body["days_remaining"] is None
    assert body["unavailable_reason"], "a tela precisa saber por que não há contagem"


async def test_choosing_a_competition_gives_the_countdown(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="foco5@exemplo.com.br")
    prova = date.today() + timedelta(days=45)
    competition = await _competition(client, admin, exam_date=prova.isoformat())
    await _publish(client, admin, competition["public_id"])
    student = await create_user(client, emails, email="aluno.foco2@exemplo.com.br")

    escolhido = await client.put(
        "/api/v1/users/me/focus",
        headers=student.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )

    assert escolhido.status_code == 200, escolhido.text
    body = escolhido.json()
    assert body["competition_public_id"] == competition["public_id"]
    assert body["days_remaining"] == 45
    assert body["unavailable_reason"] is None


async def test_a_competition_without_an_exam_date_has_no_countdown(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O edital não trouxe a data; a plataforma não inventa uma."""
    admin = await create_admin(client, emails, email="foco6@exemplo.com.br")
    competition = await _competition(client, admin)
    await _publish(client, admin, competition["public_id"])
    student = await create_user(client, emails, email="aluno.foco3@exemplo.com.br")

    escolhido = await client.put(
        "/api/v1/users/me/focus",
        headers=student.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )

    assert escolhido.status_code == 200
    assert escolhido.json()["competition_name"] == competition["name"]
    assert escolhido.json()["days_remaining"] is None
    assert "data da prova" in escolhido.json()["unavailable_reason"]


async def test_an_exam_that_already_happened_counts_zero_not_negative(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="foco7@exemplo.com.br")
    passado = date.today() - timedelta(days=10)
    competition = await _competition(client, admin, exam_date=passado.isoformat())
    await _publish(client, admin, competition["public_id"])
    student = await create_user(client, emails, email="aluno.foco4@exemplo.com.br")

    escolhido = await client.put(
        "/api/v1/users/me/focus",
        headers=student.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )

    assert escolhido.json()["days_remaining"] == 0


async def test_an_unpublished_competition_cannot_be_chosen(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Exibiria ficha que a equipe nem terminou de revisar."""
    admin = await create_admin(client, emails, email="foco8@exemplo.com.br")
    competition = await _competition(client, admin)
    student = await create_user(client, emails, email="aluno.foco5@exemplo.com.br")

    response = await client.put(
        "/api/v1/users/me/focus",
        headers=student.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "competition_not_published"


async def test_the_choice_can_be_abandoned(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="foco9@exemplo.com.br")
    competition = await _competition(client, admin, exam_date="2026-12-01")
    await _publish(client, admin, competition["public_id"])
    student = await create_user(client, emails, email="aluno.foco6@exemplo.com.br")

    await client.put(
        "/api/v1/users/me/focus",
        headers=student.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )
    abandonado = await client.put(
        "/api/v1/users/me/focus", headers=student.auth_header, json={"competition_public_id": None}
    )

    assert abandonado.status_code == 200
    assert abandonado.json()["competition_public_id"] is None
    assert abandonado.json()["unavailable_reason"]


async def test_one_student_choice_does_not_leak_to_another(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O dado é por usuário; é o que o Módulo 1 exige."""
    admin = await create_admin(client, emails, email="foco10@exemplo.com.br")
    competition = await _competition(client, admin, exam_date="2026-12-01")
    await _publish(client, admin, competition["public_id"])
    um = await create_user(client, emails, email="aluno.foco7@exemplo.com.br")
    outro = await create_user(client, emails, email="aluno.foco8@exemplo.com.br")

    await client.put(
        "/api/v1/users/me/focus",
        headers=um.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )

    do_outro = await client.get("/api/v1/users/me/focus", headers=outro.auth_header)
    assert do_outro.json()["competition_public_id"] is None
