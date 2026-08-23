"""Cadastro de editais e upload de arquivos."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    MINIMAL_PDF,
    create_admin,
    create_board,
    create_competition,
    create_organization,
    create_user,
)


async def _competition(client: AsyncClient, admin: object) -> dict[str, str]:
    organization = await create_organization(client, admin)  # type: ignore[arg-type]
    board = await create_board(client, admin)  # type: ignore[arg-type]
    return await create_competition(
        client,
        admin,  # type: ignore[arg-type]
        organization_public_id=organization["public_id"],
        exam_board_public_id=board["public_id"],
    )


async def test_student_cannot_create_notice(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.edital@exemplo.com.br")
    response = await client.post(
        "/api/v1/admin/notices",
        headers=student.auth_header,
        json={"title": "Edital falso"},
    )
    assert response.status_code == 403


async def test_create_notice_and_upload_pdf(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="edital1@exemplo.com.br")
    competition = await _competition(client, admin)

    created = await client.post(
        "/api/v1/admin/notices",
        headers=admin.auth_header,
        json={
            "title": "Edital nº 1/2026 — Agente de Polícia",
            "competition_public_id": competition["public_id"],
            "number": "1/2026",
        },
    )
    assert created.status_code == 201
    notice_id = created.json()["public_id"]
    assert created.json()["status"] == "DRAFT"
    assert created.json()["files"] == []

    uploaded = await client.post(
        f"/api/v1/admin/notices/{notice_id}/files",
        headers=admin.auth_header,
        files={"file": ("edital.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert body["size_bytes"] == len(MINIMAL_PDF)
    assert body["status"] == "STORED"
    assert len(body["checksum_sha256"]) == 64

    detail = await client.get(f"/api/v1/admin/notices/{notice_id}", headers=admin.auth_header)
    assert len(detail.json()["files"]) == 1

    download = await client.get(
        f"/api/v1/admin/notices/files/{body['public_id']}/download",
        headers=admin.auth_header,
    )
    assert download.status_code == 200
    assert download.content == MINIMAL_PDF
    assert "attachment" in download.headers["content-disposition"]


async def test_rejects_file_that_is_not_a_pdf(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="edital2@exemplo.com.br")
    created = await client.post(
        "/api/v1/admin/notices", headers=admin.auth_header, json={"title": "Edital"}
    )
    notice_id = created.json()["public_id"]

    # Extensão e content-type mentem; o conteúdo é que vale.
    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/files",
        headers=admin.auth_header,
        files={"file": ("edital.pdf", b"<?php system($_GET[0]); ?>", "application/pdf")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_pdf"


async def test_duplicate_upload_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="edital3@exemplo.com.br")
    created = await client.post(
        "/api/v1/admin/notices", headers=admin.auth_header, json={"title": "Edital"}
    )
    notice_id = created.json()["public_id"]

    first = await client.post(
        f"/api/v1/admin/notices/{notice_id}/files",
        headers=admin.auth_header,
        files={"file": ("edital.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/admin/notices/{notice_id}/files",
        headers=admin.auth_header,
        files={"file": ("copia.pdf", MINIMAL_PDF, "application/pdf")},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "duplicate_notice_file"
    assert second.json()["error"]["details"]["file_public_id"] == first.json()["public_id"]


async def test_delete_notice_removes_files(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="edital4@exemplo.com.br")
    created = await client.post(
        "/api/v1/admin/notices", headers=admin.auth_header, json={"title": "Edital"}
    )
    notice_id = created.json()["public_id"]
    uploaded = await client.post(
        f"/api/v1/admin/notices/{notice_id}/files",
        headers=admin.auth_header,
        files={"file": ("edital.pdf", MINIMAL_PDF, "application/pdf")},
    )
    file_id = uploaded.json()["public_id"]

    deleted = await client.delete(f"/api/v1/admin/notices/{notice_id}", headers=admin.auth_header)
    assert deleted.status_code == 200

    assert (
        await client.get(f"/api/v1/admin/notices/{notice_id}", headers=admin.auth_header)
    ).status_code == 404
    assert (
        await client.get(
            f"/api/v1/admin/notices/files/{file_id}/download", headers=admin.auth_header
        )
    ).status_code == 404


async def test_student_sees_notices_of_published_competition(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="edital5@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.ver@exemplo.com.br")
    competition = await _competition(client, admin)

    await client.post(
        "/api/v1/admin/notices",
        headers=admin.auth_header,
        json={
            "title": "Edital nº 1/2026",
            "competition_public_id": competition["public_id"],
        },
    )

    response = await client.get(
        f"/api/v1/catalog/competitions/{competition['public_id']}/notices",
        headers=student.auth_header,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Edital nº 1/2026"
