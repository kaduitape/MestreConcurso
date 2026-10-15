"""A aula-modelo chega inteira a quem estuda.

O seed roda a cada subida do contêiner. Aqui se cobra o que isso implica: que
a aula aparece uma vez só, que ela é **publicada** (uma instalação nova não
começa com a biblioteca vazia) e que o seed nunca sobrescreve o que uma pessoa
editou no estúdio.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.training.example import EXAMPLE_PUBLIC_ID, EXAMPLE_SCRIPT, EXAMPLE_TITLE
from app.models.training import TrainingLesson, TrainingStatus
from app.models.user import User
from app.services.seed import ensure_example_training
from tests.conftest import CapturingDispatcher
from tests.factories import create_admin, create_user


async def _author(session: AsyncSession, email: str) -> User:
    return (await session.execute(select(User).where(User.email == email))).scalar_one()


async def test_the_seed_installs_the_example_once(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    await create_admin(client, emails, email="exemplo1@exemplo.com.br")
    author = await _author(db_session, "exemplo1@exemplo.com.br")

    assert await ensure_example_training(db_session, author) is True
    # Rodar de novo não duplica: o contêiner reinicia e o seed roda outra vez.
    assert await ensure_example_training(db_session, author) is False

    rows = (
        (
            await db_session.execute(
                select(TrainingLesson).where(TrainingLesson.public_id == EXAMPLE_PUBLIC_ID)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].status == TrainingStatus.PUBLISHED
    assert len(rows[0].script["scenes"]) == len(EXAMPLE_SCRIPT["scenes"])


async def test_without_an_administrator_nothing_is_installed(db_session: AsyncSession) -> None:
    """Sem autor não há aula — e o seed segue sem quebrar a subida da API."""
    assert await ensure_example_training(db_session, None) is False


async def test_the_seed_does_not_overwrite_a_human_edit(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    await create_admin(client, emails, email="exemplo2@exemplo.com.br")
    author = await _author(db_session, "exemplo2@exemplo.com.br")
    await ensure_example_training(db_session, author)

    lesson = (
        await db_session.execute(
            select(TrainingLesson).where(TrainingLesson.public_id == EXAMPLE_PUBLIC_ID)
        )
    ).scalar_one()
    lesson.title = "Crase — versão da casa"
    await db_session.commit()

    await ensure_example_training(db_session, author)

    reread = (
        await db_session.execute(
            select(TrainingLesson).where(TrainingLesson.public_id == EXAMPLE_PUBLIC_ID)
        )
    ).scalar_one()
    assert reread.title == "Crase — versão da casa", "reiniciar o contêiner não apaga edição"


async def test_a_student_opens_the_example_lesson(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    await create_admin(client, emails, email="exemplo3@exemplo.com.br")
    author = await _author(db_session, "exemplo3@exemplo.com.br")
    await ensure_example_training(db_session, author)
    student = await create_user(client, emails, email="aluno.exemplo@exemplo.com.br")

    listed = await client.get("/api/v1/training", headers=student.auth_header)
    assert listed.status_code == 200
    assert EXAMPLE_PUBLIC_ID in {item["public_id"] for item in listed.json()["items"]}

    opened = await client.get(f"/api/v1/training/{EXAMPLE_PUBLIC_ID}", headers=student.auth_header)
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["title"] == EXAMPLE_TITLE
    assert len(body["script"]["scenes"]) == len(EXAMPLE_SCRIPT["scenes"])

    # A cena de pergunta chega com alternativas e resposta — é o que a aula
    # promete no fim, e sem isso o player não teria o que corrigir.
    question = next(scene for scene in body["script"]["scenes"] if scene["type"] == "question")
    assert len(question["options"]) == 4
    assert question["correct_option"] == 2

    # E o progresso funciona nela como em qualquer outra aula.
    started = await client.post(
        f"/api/v1/training/{EXAMPLE_PUBLIC_ID}/progress/start", headers=student.auth_header
    )
    assert started.status_code in {200, 201}, started.text
