"""Vínculo de conteúdo com o catálogo, ponta a ponta.

O que se cobra aqui, acima de tudo: **a sugestão não aplica nada**. O conteúdo
só muda de tópico quando uma pessoa confirma. E conteúdo sem vínculo continua
funcionando — "não sei" é resposta melhor que um palpite errado.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin

SCRIPT: dict[str, Any] = {
    "objectives": ["Dominar a crase"],
    "scenes": [
        {
            "id": 1,
            "type": "intro",
            "narration": "A crase é a fusão da preposição com o artigo.",
            "screen_text": "Crase",
            "duration": 10,
        }
    ],
}


async def _subject(client: AsyncClient, admin: RegisteredUser, name: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/admin/catalog/subjects",
        headers=admin.auth_header,
        json={"name": name, "area": "BASICA"},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _topic(
    client: AsyncClient, admin: RegisteredUser, subject_id: str, name: str
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/admin/catalog/subjects/{subject_id}/topics",
        headers=admin.auth_header,
        json={"name": name},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def _lesson(client: AsyncClient, admin: RegisteredUser, subject: str, topic: str) -> str:
    created = await client.post(
        "/api/v1/admin/training",
        headers=admin.auth_header,
        json={
            "subject": subject,
            "topic": topic,
            "character_name": "Mestre Arcanus",
            "level": "INTERMEDIARIO",
            "style": "AULA",
            "target_duration_minutes": 10,
            "research_before_generate": False,
        },
    )
    assert created.status_code == 201, created.text
    public_id = str(created.json()["public_id"])
    saved = await client.put(
        f"/api/v1/admin/training/{public_id}/script",
        headers=admin.auth_header,
        json={"title": f"{topic}", "script": SCRIPT},
    )
    assert saved.status_code == 200, saved.text
    return public_id


async def test_a_new_lesson_starts_without_a_link_and_shows_up_as_pending(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="link1@exemplo.com.br")
    await _subject(client, admin, "Língua Portuguesa")
    lesson_id = await _lesson(client, admin, "Língua Portuguesa", "Crase")

    pending = await client.get("/api/v1/admin/catalog/links/pending", headers=admin.auth_header)

    assert pending.status_code == 200, pending.text
    item = next(row for row in pending.json()["items"] if row["public_id"] == lesson_id)
    assert item["kind"] == "TRAINING"
    assert item["subject_text"] == "Língua Portuguesa"
    assert item["subject_public_id"] is None


async def test_the_suggestion_ranks_but_does_not_apply(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A regra que sustenta o módulo inteiro."""
    admin = await create_admin(client, emails, email="link2@exemplo.com.br")
    portugues = await _subject(client, admin, "Língua Portuguesa")
    await _subject(client, admin, "Direito Administrativo")
    lesson_id = await _lesson(client, admin, "Língua Portuguesa", "Crase")

    pending = await client.get("/api/v1/admin/catalog/links/pending", headers=admin.auth_header)
    item = next(row for row in pending.json()["items"] if row["public_id"] == lesson_id)

    melhor = item["subject_suggestions"]["candidates"][0]
    assert melhor["public_id"] == portugues["public_id"]
    assert melhor["is_strong"] is True
    assert melhor["reason_label"], "quem revisa precisa saber por que foi sugerido"

    # E mesmo com nota máxima, nada foi aplicado.
    assert item["subject_public_id"] is None


async def test_a_person_confirms_and_only_then_the_link_exists(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="link3@exemplo.com.br")
    portugues = await _subject(client, admin, "Língua Portuguesa")
    crase = await _topic(client, admin, portugues["public_id"], "Crase")
    lesson_id = await _lesson(client, admin, "Língua Portuguesa", "Crase")

    sugestoes = await client.get(
        f"/api/v1/admin/catalog/links/TRAINING/{lesson_id}/topics"
        f"?subject_public_id={portugues['public_id']}",
        headers=admin.auth_header,
    )
    assert sugestoes.status_code == 200, sugestoes.text
    assert sugestoes.json()["candidates"][0]["public_id"] == crase["public_id"]

    aplicado = await client.put(
        f"/api/v1/admin/catalog/links/TRAINING/{lesson_id}",
        headers=admin.auth_header,
        json={
            "subject_public_id": portugues["public_id"],
            "topic_public_id": crase["public_id"],
        },
    )

    assert aplicado.status_code == 200, aplicado.text
    assert aplicado.json()["subject_public_id"] == portugues["public_id"]
    assert aplicado.json()["topic_public_id"] == crase["public_id"]

    # Vinculado por inteiro, sai da fila de pendências.
    pending = await client.get("/api/v1/admin/catalog/links/pending", headers=admin.auth_header)
    assert lesson_id not in {row["public_id"] for row in pending.json()["items"]}


async def test_a_topic_from_another_subject_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Deixar passar criaria um vínculo impossível."""
    admin = await create_admin(client, emails, email="link4@exemplo.com.br")
    portugues = await _subject(client, admin, "Língua Portuguesa")
    direito = await _subject(client, admin, "Direito Administrativo")
    principios = await _topic(client, admin, direito["public_id"], "Princípios")
    lesson_id = await _lesson(client, admin, "Língua Portuguesa", "Crase")

    response = await client.put(
        f"/api/v1/admin/catalog/links/TRAINING/{lesson_id}",
        headers=admin.auth_header,
        json={
            "subject_public_id": portugues["public_id"],
            "topic_public_id": principios["public_id"],
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "topic_subject_mismatch"


async def test_a_topic_without_a_subject_is_not_a_link(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="link5@exemplo.com.br")
    portugues = await _subject(client, admin, "Língua Portuguesa")
    crase = await _topic(client, admin, portugues["public_id"], "Crase")
    lesson_id = await _lesson(client, admin, "Língua Portuguesa", "Crase")

    response = await client.put(
        f"/api/v1/admin/catalog/links/TRAINING/{lesson_id}",
        headers=admin.auth_header,
        json={"subject_public_id": None, "topic_public_id": crase["public_id"]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "topic_without_subject"


async def test_the_link_can_be_undone(client: AsyncClient, emails: CapturingDispatcher) -> None:
    """Quem revisa precisa poder dizer "isto não é nada do catálogo"."""
    admin = await create_admin(client, emails, email="link6@exemplo.com.br")
    portugues = await _subject(client, admin, "Língua Portuguesa")
    lesson_id = await _lesson(client, admin, "Língua Portuguesa", "Crase")

    await client.put(
        f"/api/v1/admin/catalog/links/TRAINING/{lesson_id}",
        headers=admin.auth_header,
        json={"subject_public_id": portugues["public_id"], "topic_public_id": None},
    )
    desfeito = await client.put(
        f"/api/v1/admin/catalog/links/TRAINING/{lesson_id}",
        headers=admin.auth_header,
        json={"subject_public_id": None, "topic_public_id": None},
    )

    assert desfeito.status_code == 200
    assert desfeito.json()["subject_public_id"] is None


async def test_an_unlinked_lesson_keeps_working_for_the_student(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A migração é aditiva: nada que já funcionava pode parar."""
    admin = await create_admin(client, emails, email="link7@exemplo.com.br")
    lesson_id = await _lesson(client, admin, "Matéria Que Não Está No Catálogo", "Tópico")
    published = await client.post(
        f"/api/v1/admin/training/{lesson_id}/publish", headers=admin.auth_header
    )
    assert published.status_code == 200, published.text

    from tests.factories import create_user

    student = await create_user(client, emails, email="aluno.link@exemplo.com.br")
    opened = await client.get(f"/api/v1/training/{lesson_id}", headers=student.auth_header)

    assert opened.status_code == 200
    assert opened.json()["script"]["scenes"]


async def test_a_student_cannot_link_content(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    from tests.factories import create_user

    student = await create_user(client, emails, email="aluno.link2@exemplo.com.br")
    response = await client.get("/api/v1/admin/catalog/links/pending", headers=student.auth_header)
    assert response.status_code == 403
