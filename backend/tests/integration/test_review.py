"""Revisão espaçada: fila com teto, intervalos explicados e adiamento declarado."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient

from app.domain.srs import DEFAULT_DAILY_LIMIT
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_user


async def _deck(client: AsyncClient, user: RegisteredUser, size: int) -> list[str]:
    ids: list[str] = []
    for index in range(size):
        response = await client.post(
            "/api/v1/flashcards",
            headers=user.auth_header,
            json={
                "front": f"Pergunta número {index} sobre o conteúdo estudado",
                "back": f"Resposta {index}",
            },
        )
        assert response.status_code == 201, response.text
        ids.append(response.json()["public_id"])
    return ids


async def _make_overdue(email: str, *, days: int) -> None:
    """Envelhece a fila direto na base — simula a ausência do candidato."""
    from sqlalchemy import select, update

    from app.db.session import get_session_factory
    from app.models.flashcard import CardMemoryState
    from app.models.user import User

    factory = get_session_factory()
    async with factory() as session:
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        await session.execute(
            update(CardMemoryState)
            .where(CardMemoryState.user_id == user_id)
            .values(
                due_on=date.today() - timedelta(days=days),
                state="REVIEW",
                interval_days=10,
                repetitions=3,
                last_reviewed_at=datetime.now(UTC) - timedelta(days=days),
            )
        )
        await session.commit()


async def test_new_cards_enter_the_queue_respecting_the_daily_cap(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rev1@exemplo.com.br")
    await _deck(client, student, 25)

    response = await client.get("/api/v1/review/queue?new_per_day=10", headers=student.auth_header)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total_cards"] == 25
    assert body["plan"]["new_count"] == 10
    assert len(body["items"]) == 10
    assert all(item["is_new"] for item in body["items"])
    assert body["items"][0]["state"]["state"] == "NEW"


async def test_empty_deck_says_the_memory_is_up_to_date(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rev2@exemplo.com.br")

    body = (await client.get("/api/v1/review/queue", headers=student.auth_header)).json()

    assert body["items"] == []
    assert "em dia" in body["plan"]["summary"]


async def test_the_queue_never_explodes_after_an_absence(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    email = "rev3@exemplo.com.br"
    student = await create_user(client, emails, email=email)
    await _deck(client, student, 120)

    # Entra na fila uma vez e depois some por dez dias.
    await client.get("/api/v1/review/queue", headers=student.auth_header)
    await _make_overdue(email, days=10)

    body = (
        await client.get("/api/v1/review/queue?daily_limit=40", headers=student.auth_header)
    ).json()

    assert body["plan"]["overdue_count"] == 120
    assert len(body["items"]) == 40, "o teto diário precisa ser respeitado"
    assert body["plan"]["rescheduled_count"] == 80
    assert body["plan"]["absence_days"] == 10
    assert "10 dias sem revisar" in body["plan"]["summary"]
    assert "distribuídos pelos próximos dias" in body["plan"]["summary"]

    # E o excedente foi realmente movido: amanhã não reencontra a mesma avalanche.
    again = (
        await client.get("/api/v1/review/queue?daily_limit=40", headers=student.auth_header)
    ).json()
    assert again["plan"]["overdue_count"] == 40
    assert again["plan"]["rescheduled_count"] == 0


async def test_answering_moves_the_card_forward_and_explains_the_interval(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rev4@exemplo.com.br")
    cards = await _deck(client, student, 3)
    await client.get("/api/v1/review/queue", headers=student.auth_header)

    response = await client.post(
        f"/api/v1/review/{cards[0]}/answer",
        headers=student.auth_header,
        json={"rating": "GOOD", "time_seconds": 12},
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["interval_days"] == 1
    assert body["state"] == "LEARNING"
    assert body["due_on"] == (date.today() + timedelta(days=1)).isoformat()
    assert body["remaining_today"] == 2
    # O intervalo vem explicado, não seco.
    assert body["breakdown"]["resposta"] == "GOOD"
    assert body["breakdown"]["intervalo_final"] == 1


async def test_speed_changes_the_interval_of_a_mature_card(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    email = "rev5@exemplo.com.br"
    student = await create_user(client, emails, email=email)
    cards = await _deck(client, student, 2)
    await client.get("/api/v1/review/queue", headers=student.auth_header)
    await _make_overdue(email, days=1)

    rapido = await client.post(
        f"/api/v1/review/{cards[0]}/answer",
        headers=student.auth_header,
        json={"rating": "GOOD", "time_seconds": 4},
    )
    lento = await client.post(
        f"/api/v1/review/{cards[1]}/answer",
        headers=student.auth_header,
        json={"rating": "GOOD", "time_seconds": 90},
    )

    assert rapido.json()["interval_days"] > lento.json()["interval_days"]
    assert rapido.json()["breakdown"]["ajuste_de_velocidade"] > 1
    assert lento.json()["breakdown"]["ajuste_de_velocidade"] < 1


async def test_missing_a_mature_card_shortens_without_erasing_the_progress(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    email = "rev6@exemplo.com.br"
    student = await create_user(client, emails, email=email)
    cards = await _deck(client, student, 1)
    await client.get("/api/v1/review/queue", headers=student.auth_header)
    await _make_overdue(email, days=1)

    response = await client.post(
        f"/api/v1/review/{cards[0]}/answer",
        headers=student.auth_header,
        json={"rating": "AGAIN", "time_seconds": 30},
    )
    body = response.json()

    assert body["state"] == "RELEARNING"
    # Intervalo era 10; cai proporcionalmente, mas não volta a zero.
    assert 1 <= body["interval_days"] < 10
    assert body["breakdown"]["motivo"] == "erro"


async def test_flash_review_is_a_short_slice_of_the_same_queue(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    email = "rev7@exemplo.com.br"
    student = await create_user(client, emails, email=email)
    await _deck(client, student, 30)
    await client.get("/api/v1/review/queue", headers=student.auth_header)
    await _make_overdue(email, days=2)

    body = (await client.get("/api/v1/review/flash?size=5", headers=student.auth_header)).json()

    assert len(body["items"]) == 5
    assert body["plan"]["new_count"] == 0


async def test_postponing_is_a_declared_choice(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rev8@exemplo.com.br")
    await _deck(client, student, 5)
    await client.get("/api/v1/review/queue", headers=student.auth_header)

    response = await client.post("/api/v1/review/postpone?days=2", headers=student.auth_header)
    assert response.status_code == 200, response.text
    assert response.json()["detail"]["moved"] == 5

    body = (await client.get("/api/v1/review/queue", headers=student.auth_header)).json()
    assert body["items"] == []
    assert body["plan"]["overdue_count"] == 0


async def test_stats_report_real_numbers_and_admit_the_missing_ones(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rev9@exemplo.com.br")
    cards = await _deck(client, student, 4)

    empty = (await client.get("/api/v1/review/stats", headers=student.auth_header)).json()
    assert empty["total_reviews"] == 0
    # Sem revisão registrada não existe taxa de recordação: nula, não zero.
    assert empty["recall_rate"] is None

    await client.get("/api/v1/review/queue", headers=student.auth_header)
    for index, card in enumerate(cards):
        await client.post(
            f"/api/v1/review/{card}/answer",
            headers=student.auth_header,
            json={"rating": "AGAIN" if index == 0 else "GOOD", "time_seconds": 10},
        )

    body = (await client.get("/api/v1/review/stats", headers=student.auth_header)).json()
    assert body["total_cards"] == 4
    assert body["total_reviews"] == 4
    assert body["reviewed_today"] == 4
    assert body["recall_rate"] == 0.75
    assert body["ratings"]["GOOD"] == 3
    assert len(body["upcoming"]) == 14


async def test_a_card_of_another_candidate_cannot_be_answered(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rev10@exemplo.com.br")
    intruder = await create_user(client, emails, email="intruso.rev@exemplo.com.br")
    cards = await _deck(client, student, 1)
    await client.get("/api/v1/review/queue", headers=student.auth_header)

    response = await client.post(
        f"/api/v1/review/{cards[0]}/answer",
        headers=intruder.auth_header,
        json={"rating": "GOOD"},
    )
    assert response.status_code == 404


async def test_default_ceiling_keeps_the_session_finishable(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    email = "rev11@exemplo.com.br"
    student = await create_user(client, emails, email=email)
    await _deck(client, student, 90)
    await client.get("/api/v1/review/queue", headers=student.auth_header)
    await _make_overdue(email, days=3)

    body = (await client.get("/api/v1/review/queue", headers=student.auth_header)).json()
    assert len(body["items"]) == DEFAULT_DAILY_LIMIT
