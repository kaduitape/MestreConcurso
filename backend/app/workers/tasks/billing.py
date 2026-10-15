"""Tarefas periódicas da camada comercial.

Existem porque três transições dependem apenas do calendário: a troca agendada
que precisa virar, o teste que venceu e a tolerância que acabou. Todas já
acontecem quando o candidato acessa a plataforma — mas quem parou de acessar
ficaria com o estado congelado, e é justamente esse estado que o painel de SaaS
soma. Sem esta tarefa, o MRR conta assinantes que já deveriam ter expirado.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain.billing.subscription import SubscriptionState, next_status
from app.models.billing import Subscription, SubscriptionEvent
from app.services.entitlements import EntitlementService

logger = get_logger(__name__)

#: Estados que ainda podem mudar sozinhos. Os finais não são revisitados.
OPEN_STATES = ("TRIALING", "ACTIVE", "PAST_DUE", "CANCELING")


async def _refresh_subscriptions() -> dict[str, int]:
    today = datetime.now(UTC).date()
    factory = get_session_factory()
    downgrades = 0
    transitions = 0

    async with factory() as session:
        service = EntitlementService(session)
        rows = list(
            (
                await session.execute(
                    select(Subscription).where(Subscription.status.in_(OPEN_STATES))
                )
            )
            .scalars()
            .all()
        )

        for subscription in rows:
            if await service.apply_scheduled_downgrade(subscription, today=today):
                downgrades += 1
                # O downgrade já reabriu o período: nada mais a decidir hoje.
                continue

            evolved = next_status(
                SubscriptionState(
                    status=subscription.status,
                    current_period_end=subscription.current_period_end,
                    trial_ends_on=subscription.trial_ends_on,
                    grace_ends_on=subscription.grace_ends_on,
                ),
                today=today,
            )
            if evolved == subscription.status:
                continue

            session.add(
                SubscriptionEvent(
                    subscription_id=subscription.id,
                    kind="STATUS_ADVANCED",
                    from_status=subscription.status,
                    to_status=evolved,
                    detail="Estado atualizado pela virada do calendário.",
                )
            )
            subscription.status = evolved
            transitions += 1

        if transitions:
            await session.commit()

    return {"downgrades_applied": downgrades, "status_transitions": transitions}


@shared_task(name="billing.refresh_subscriptions")
def refresh_subscriptions() -> dict[str, int]:
    """Aplica trocas agendadas e move os estados que o calendário já mudou."""
    result = asyncio.run(_refresh_subscriptions())
    logger.info("billing.refresh_subscriptions", **result)
    return result
