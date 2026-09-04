"""Exportação LGPD completa e a tarefa que move o calendário.

Os dois nasceram de lacunas encontradas em revisão: a exportação prometia "tudo
o que a plataforma guarda" e entregava só a Fase 1, e as transições de
assinatura só aconteciam quando o candidato aparecia.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    WEEKDAY_AVAILABILITY,
    RegisteredUser,
    create_admin,
    create_position_with_subjects,
    create_question,
    create_user,
)


async def _export(client: AsyncClient, user: RegisteredUser) -> dict[str, Any]:
    response = await client.get("/api/v1/users/me/export", headers=user.auth_header)
    assert response.status_code == 200, response.text
    return json.loads(response.content)


# --------------------------------------------------------------------------- #
# Exportação LGPD
# --------------------------------------------------------------------------- #
async def test_the_export_covers_every_area_of_the_product(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="lgpd1@exemplo.com.br")

    body = await _export(client, student)

    assert {"account", "profile", "sessions", "consents", "activity_log"} <= set(body)
    # E as áreas que o produto ganhou depois da Fase 1.
    for area in (
        "estudo",
        "questoes",
        "memorizacao",
        "mestre_ia",
        "inteligencia",
        "gamificacao",
        "analytics",
        "comercial",
    ):
        assert area in body, f"a exportação não cobre {area}"


async def test_every_collection_declares_its_total(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="lgpd2@exemplo.com.br")

    body = await _export(client, student)

    for area, collections in body.items():
        if area in {"account", "profile", "sessions", "consents", "activity_log", "exported_at"}:
            continue
        for key, collection in collections.items():
            assert "total" in collection, f"{area}.{key} não declara o total"
            assert "items" in collection
            assert collection["label"], f"{area}.{key} não tem rótulo legível"


async def test_the_export_carries_what_the_candidate_actually_did(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="lgpd3@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.lgpd3@exemplo.com.br")

    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    question = await create_question(
        client, admin, statement="Exportação — enunciado com texto suficiente."
    )
    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=student.auth_header,
        json={"letter": "A", "time_seconds": 30},
    )

    body = await _export(client, student)

    assert body["estudo"]["planos"]["total"] == 1
    assert body["estudo"]["planos"]["items"][0]["name"]
    assert body["questoes"]["respostas"]["total"] == 1
    assert body["questoes"]["respostas"]["items"][0]["is_correct"] is True
    # A gamificação reagiu à resposta, e o extrato de XP também é dado pessoal.
    assert body["gamificacao"]["extrato_de_xp"]["total"] >= 1


async def test_the_export_serializes_dates_and_decimals(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Se algum tipo escapasse, a resposta quebraria antes de chegar aqui."""
    admin = await create_admin(client, emails, email="lgpd4@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.lgpd4@exemplo.com.br")
    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )

    body = await _export(client, student)
    progresso = body["estudo"]["progresso_por_disciplina"]["items"]

    assert progresso
    assert isinstance(progresso[0]["completion"], float)


# --------------------------------------------------------------------------- #
# Tarefa periódica
# --------------------------------------------------------------------------- #
async def test_the_job_applies_a_scheduled_downgrade_without_the_candidate(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A troca agendada não pode depender de o candidato abrir a tela."""
    student = await create_user(client, emails, email="job1@exemplo.com.br")
    await client.post(
        "/api/v1/billing/subscribe",
        headers=student.auth_header,
        json={"plan_slug": "mestre-anual"},
    )
    await client.post(
        "/api/v1/billing/change-plan",
        headers=student.auth_header,
        json={"plan_slug": "mestre"},
    )

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.billing import Subscription
    from app.workers.tasks.billing import _refresh_subscriptions

    factory = get_session_factory()
    async with factory() as session:
        record = (
            await session.execute(select(Subscription).order_by(Subscription.id.desc()).limit(1))
        ).scalar_one()
        record.current_period_start = date.today() - timedelta(days=400)
        record.current_period_end = date.today() - timedelta(days=1)
        await session.commit()
        subscription_id = record.id

    result = await _refresh_subscriptions()
    assert result["downgrades_applied"] == 1

    async with factory() as session:
        stored = await session.get(Subscription, subscription_id)
        assert stored is not None
        assert stored.scheduled_plan_id is None
        assert stored.current_period_end >= date.today()


async def test_the_job_expires_a_subscription_past_its_grace(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Sem isto, o painel de SaaS somaria assinantes que já deveriam ter saído."""
    student = await create_user(client, emails, email="job2@exemplo.com.br")
    await client.post(
        "/api/v1/billing/subscribe",
        headers=student.auth_header,
        json={"plan_slug": "mestre"},
    )

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.billing import Subscription, SubscriptionEvent
    from app.workers.tasks.billing import _refresh_subscriptions

    factory = get_session_factory()
    async with factory() as session:
        record = (
            await session.execute(select(Subscription).order_by(Subscription.id.desc()).limit(1))
        ).scalar_one()
        record.status = "PAST_DUE"
        record.trial_ends_on = None
        record.grace_ends_on = date.today() - timedelta(days=1)
        await session.commit()
        subscription_id = record.id

    result = await _refresh_subscriptions()
    assert result["status_transitions"] == 1

    async with factory() as session:
        stored = await session.get(Subscription, subscription_id)
        assert stored is not None
        assert stored.status == "EXPIRED"

        # A mudança fica registrada: "por que meu acesso mudou?" tem resposta.
        events = list(
            (
                await session.execute(
                    select(SubscriptionEvent).where(
                        SubscriptionEvent.subscription_id == subscription_id,
                        SubscriptionEvent.kind == "STATUS_ADVANCED",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].to_status == "EXPIRED"


async def test_the_job_leaves_healthy_subscriptions_alone(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="job3@exemplo.com.br")
    await client.post(
        "/api/v1/billing/subscribe",
        headers=student.auth_header,
        json={"plan_slug": "mestre"},
    )

    from app.workers.tasks.billing import _refresh_subscriptions

    result = await _refresh_subscriptions()

    assert result == {"downgrades_applied": 0, "status_transitions": 0}
