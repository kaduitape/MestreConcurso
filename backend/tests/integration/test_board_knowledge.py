"""Conhecimento sobre a banca: gravar uma vez, reutilizar sempre."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import create_admin, create_board, create_user

ENTRY = {
    "kind": "STYLE_TRAIT",
    "entry_key": "interpretacao",
    "title": "Alta exigência de interpretação",
    "content": "A banca cobra leitura minuciosa do enunciado.",
    "data": {"score": 91},
    "source": "COMPUTED",
    "confidence": "0.870",
    "sample_exams": 48,
    "sample_questions": 5760,
    "period_start_year": 2018,
    "period_end_year": 2025,
}


async def test_save_and_reuse_board_knowledge(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="dna1@exemplo.com.br")
    board = await create_board(client, admin)
    base = f"/api/v1/admin/catalog/boards/{board['public_id']}/knowledge"

    saved = await client.put(base, headers=admin.auth_header, json=ENTRY)
    assert saved.status_code == 200
    body = saved.json()
    assert body["source"] == "COMPUTED"
    assert body["sample_questions"] == 5760
    assert body["is_expired"] is False

    # Gravar de novo atualiza o mesmo registro em vez de duplicar.
    again = await client.put(
        base, headers=admin.auth_header, json={**ENTRY, "title": "Interpretação pesada"}
    )
    assert again.status_code == 200
    listed = await client.get(base, headers=admin.auth_header)
    assert len(listed.json()) == 1
    assert listed.json()[0]["title"] == "Interpretação pesada"


async def test_knowledge_records_ai_origin_and_tokens(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="dna2@exemplo.com.br")
    board = await create_board(client, admin)
    base = f"/api/v1/admin/catalog/boards/{board['public_id']}/knowledge"

    await client.put(
        base,
        headers=admin.auth_header,
        json={
            "kind": "PROFILE_SUMMARY",
            "entry_key": "resumo-geral",
            "title": "Resumo do estilo da banca",
            "content": "Texto interpretativo.",
            "source": "AI",
            "confidence": "0.700",
        },
    )

    coverage = await client.get(f"{base}/coverage", headers=admin.auth_header)
    assert coverage.status_code == 200
    assert coverage.json()["total"] == 1
    assert coverage.json()["by_source"] == {"AI": 1}
    assert coverage.json()["by_kind"] == {"PROFILE_SUMMARY": 1}


async def test_student_reads_stored_knowledge(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="dna3@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.dna@exemplo.com.br")
    board = await create_board(client, admin)

    await client.put(
        f"/api/v1/admin/catalog/boards/{board['public_id']}/knowledge",
        headers=admin.auth_header,
        json=ENTRY,
    )

    response = await client.get(
        f"/api/v1/catalog/boards/{board['public_id']}/knowledge",
        headers=student.auth_header,
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    entry = response.json()[0]
    # A origem e o tamanho da amostra acompanham o dado — nada aparece "solto".
    assert entry["source"] == "COMPUTED"
    assert entry["sample_exams"] == 48
    assert entry["period_start_year"] == 2018


async def test_expired_knowledge_is_hidden_from_students(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.board_knowledge import BoardKnowledgeEntry

    admin = await create_admin(client, emails, email="dna4@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.exp@exemplo.com.br")
    board = await create_board(client, admin)

    await client.put(
        f"/api/v1/admin/catalog/boards/{board['public_id']}/knowledge",
        headers=admin.auth_header,
        json={**ENTRY, "ttl_days": 30},
    )

    factory = get_session_factory()
    async with factory() as session:
        entry = (await session.execute(select(BoardKnowledgeEntry))).scalar_one()
        entry.expires_at = datetime.now(UTC) - timedelta(days=1)
        await session.commit()

    student_view = await client.get(
        f"/api/v1/catalog/boards/{board['public_id']}/knowledge",
        headers=student.auth_header,
    )
    assert student_view.json() == []

    # O administrador continua vendo, marcado como vencido, para poder reapurar.
    admin_view = await client.get(
        f"/api/v1/admin/catalog/boards/{board['public_id']}/knowledge",
        headers=admin.auth_header,
    )
    assert admin_view.json()[0]["is_expired"] is True


async def test_delete_knowledge_entry(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="dna5@exemplo.com.br")
    board = await create_board(client, admin)
    base = f"/api/v1/admin/catalog/boards/{board['public_id']}/knowledge"

    created = await client.put(base, headers=admin.auth_header, json=ENTRY)
    entry_id = created.json()["id"]

    deleted = await client.delete(f"{base}/{entry_id}", headers=admin.auth_header)
    assert deleted.status_code == 200
    assert (await client.get(base, headers=admin.auth_header)).json() == []
