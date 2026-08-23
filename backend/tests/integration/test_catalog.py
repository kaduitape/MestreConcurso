"""Catálogo de concursos: administração e visão do candidato."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    create_admin,
    create_board,
    create_competition,
    create_organization,
    create_subject,
    create_user,
)


async def test_student_cannot_write_to_catalog(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.cat@exemplo.com.br")
    response = await client.post(
        "/api/v1/admin/catalog/boards",
        headers=student.auth_header,
        json={"name": "Banca Falsa", "short_name": "FAKE"},
    )
    assert response.status_code == 403


async def test_board_crud_and_slug_generation(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="cat1@exemplo.com.br")
    board = await create_board(client, admin, name="Cebraspe", short="CESPE")
    assert board["slug"] == "cespe"

    duplicated = await client.post(
        "/api/v1/admin/catalog/boards",
        headers=admin.auth_header,
        json={"name": "Outra", "short_name": "CESPE"},
    )
    assert duplicated.status_code == 409

    updated = await client.patch(
        f"/api/v1/admin/catalog/boards/{board['public_id']}",
        headers=admin.auth_header,
        json={"website": "https://www.cebraspe.org.br", "aliases": ["CESPE", "UnB"]},
    )
    assert updated.status_code == 200
    assert updated.json()["aliases"] == ["CESPE", "UnB"]

    listed = await client.get("/api/v1/admin/catalog/boards", headers=admin.auth_header)
    assert listed.json()["total"] == 1


async def test_board_with_competitions_cannot_be_deleted(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="cat2@exemplo.com.br")
    board = await create_board(client, admin)
    organization = await create_organization(client, admin)
    await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=board["public_id"],
    )

    blocked = await client.delete(
        f"/api/v1/admin/catalog/boards/{board['public_id']}", headers=admin.auth_header
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["competitions"] == 1


async def test_competition_with_positions_and_subjects(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="cat3@exemplo.com.br")
    board = await create_board(client, admin)
    organization = await create_organization(client, admin)
    competition = await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=board["public_id"],
    )
    assert competition["exam_board"]["short_name"] == "CESPE"
    assert competition["organization"]["short_name"] == "PCDF"

    position = await client.post(
        f"/api/v1/admin/catalog/competitions/{competition['public_id']}/positions",
        headers=admin.auth_header,
        json={
            "name": "Agente de Polícia",
            "education_level": "SUPERIOR",
            "salary_cents": 815700,
            "vacancies": 1200,
            "questions_count": 120,
        },
    )
    assert position.status_code == 201
    position_id = position.json()["public_id"]

    subject = await create_subject(client, admin)
    linked = await client.put(
        f"/api/v1/admin/catalog/positions/{position_id}/subjects",
        headers=admin.auth_header,
        json={
            "subject_public_id": subject["public_id"],
            "weight": "3.00",
            "questions_count": 20,
            "is_eliminatory": True,
        },
    )
    assert linked.status_code == 200
    subjects = linked.json()["subjects"]
    assert len(subjects) == 1
    assert subjects[0]["subject"]["name"] == "Direito Penal"
    assert subjects[0]["weight"] == "3.00"

    # Atualizar o vínculo não duplica a disciplina.
    again = await client.put(
        f"/api/v1/admin/catalog/positions/{position_id}/subjects",
        headers=admin.auth_header,
        json={"subject_public_id": subject["public_id"], "weight": "2.00"},
    )
    assert len(again.json()["subjects"]) == 1
    assert again.json()["subjects"][0]["weight"] == "2.00"

    removed = await client.delete(
        f"/api/v1/admin/catalog/positions/{position_id}/subjects/{subject['public_id']}",
        headers=admin.auth_header,
    )
    assert removed.json()["subjects"] == []


async def test_topic_tree_and_depth_limit(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="cat4@exemplo.com.br")
    subject = await create_subject(client, admin, name="Português")
    base = f"/api/v1/admin/catalog/subjects/{subject['public_id']}/topics"

    parent = await client.post(
        base, headers=admin.auth_header, json={"name": "Sintaxe", "sort_order": 1}
    )
    assert parent.status_code == 201
    assert parent.json()["depth"] == 0

    child = await client.post(
        base,
        headers=admin.auth_header,
        json={"name": "Crase", "parent_public_id": parent.json()["public_id"]},
    )
    assert child.status_code == 201
    assert child.json()["depth"] == 1
    assert child.json()["parent_public_id"] == parent.json()["public_id"]

    duplicated = await client.post(
        base,
        headers=admin.auth_header,
        json={"name": "Crase", "parent_public_id": parent.json()["public_id"]},
    )
    assert duplicated.status_code == 409

    listed = await client.get(base, headers=admin.auth_header)
    assert len(listed.json()) == 2

    # Remover o pai leva junto os filhos.
    await client.delete(
        f"/api/v1/admin/catalog/topics/{parent.json()['public_id']}",
        headers=admin.auth_header,
    )
    assert await (await client.get(base, headers=admin.auth_header)).aread() == b"[]"


async def test_topic_csv_import(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="cat5@exemplo.com.br")
    subject = await create_subject(client, admin, name="Direito Constitucional")

    csv_content = (
        "assunto;subassunto;ordem\n"
        "Direitos Fundamentais;Direitos individuais;1\n"
        "Direitos Fundamentais;Direitos sociais;2\n"
        "Organização do Estado;Competências da União;1\n"
        "Direitos Fundamentais;Direitos individuais;3\n"  # repetida: deve ser ignorada
    ).encode()

    response = await client.post(
        f"/api/v1/admin/catalog/subjects/{subject['public_id']}/topics/import",
        headers=admin.auth_header,
        files={"file": ("assuntos.csv", csv_content, "text/csv")},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["created"] == 5  # 2 pais + 3 filhos
    assert result["skipped"] == 1

    topics = await client.get(
        f"/api/v1/admin/catalog/subjects/{subject['public_id']}/topics",
        headers=admin.auth_header,
    )
    names = {topic["name"] for topic in topics.json()}
    assert "Direitos Fundamentais" in names
    assert "Competências da União" in names


async def test_public_catalog_shows_only_published(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="cat6@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.pub@exemplo.com.br")
    organization = await create_organization(client, admin)
    board = await create_board(client, admin)

    published = await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=board["public_id"],
        name="PCDF 2026 — Agente",
        is_published=True,
    )
    draft = await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=board["public_id"],
        name="Rascunho interno",
        is_published=False,
    )

    listing = await client.get("/api/v1/catalog/competitions", headers=student.auth_header)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["public_id"] == published["public_id"]

    hidden = await client.get(
        f"/api/v1/catalog/competitions/{draft['public_id']}", headers=student.auth_header
    )
    assert hidden.status_code == 404

    detail = await client.get(
        f"/api/v1/catalog/competitions/{published['public_id']}", headers=student.auth_header
    )
    assert detail.status_code == 200
    assert detail.json()["organization"]["short_name"] == "PCDF"


async def test_public_catalog_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/catalog/competitions")).status_code == 401


async def test_catalog_search_and_filters(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="cat7@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.filtro@exemplo.com.br")
    organization = await create_organization(client, admin)
    cespe = await create_board(client, admin, name="Cebraspe", short="CESPE")
    fgv = await create_board(client, admin, name="Fundação Getulio Vargas", short="FGV")

    await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=cespe["public_id"],
        name="Concurso CESPE 2026",
        year=2026,
    )
    await create_competition(
        client,
        admin,
        organization_public_id=organization["public_id"],
        exam_board_public_id=fgv["public_id"],
        name="Concurso FGV 2025",
        year=2025,
    )

    by_board = await client.get(
        "/api/v1/catalog/competitions?exam_board=fgv", headers=student.auth_header
    )
    assert by_board.json()["total"] == 1
    assert by_board.json()["items"][0]["exam_board"]["short_name"] == "FGV"

    by_year = await client.get(
        "/api/v1/catalog/competitions?year=2026", headers=student.auth_header
    )
    assert by_year.json()["total"] == 1

    by_search = await client.get(
        "/api/v1/catalog/competitions?search=FGV", headers=student.auth_header
    )
    assert by_search.json()["total"] == 1
