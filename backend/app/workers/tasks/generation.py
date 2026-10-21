"""Geração em massa fora do ciclo HTTP.

A passada roda em blocos e se reagenda: assim o acompanhamento ao vivo tem o que
mostrar, o teto de gasto é consultado com frequência e uma interrupção do worker
não perde o que já foi gerado — o estado mora no banco, item a item.
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain.generation import ItemStatus, PlanStatus
from app.services.auth import RequestContext
from app.services.generation import GenerationService

# Importar a aplicação Celery aqui não é adorno: `shared_task` se liga à
# aplicação **corrente**, e sem esta linha a tarefa acaba numa aplicação padrão
# que não conhece a configuração do projeto — inclusive o modo síncrono dos
# testes, que então tentariam falar com um broker que não existe.
from app.workers.celery_app import celery_app  # noqa: F401

logger = get_logger(__name__)

#: Quantos blocos uma tarefa roda antes de devolver o worker. Sem este limite,
#: um plano grande seguraria o processo por horas.
MAX_BATCHES = 20


async def _run(plan_public_id: str) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        service = GenerationService(session)
        plan = await service.get(plan_public_id)
        if plan.status in {PlanStatus.DRAFT, PlanStatus.CANCELED}:
            logger.info("generation.task_skipped", plan=plan_public_id, status=plan.status)
            return {"status": "SKIPPED", "plan_status": plan.status}

        from sqlalchemy import select

        from app.models.user import User

        actor = (
            await session.execute(select(User).where(User.id == plan.confirmed_by_user_id))
        ).scalar_one_or_none()
        if actor is None:
            # Sem a pessoa que confirmou não há em nome de quem criar conteúdo.
            logger.warning("generation.task_without_actor", plan=plan_public_id)
            return {"status": "NO_ACTOR"}

        gerados = reaproveitados = falhos = barrados = 0
        for _ in range(MAX_BATCHES):
            resultado = await service.run(plan, actor, RequestContext())
            gerados += resultado.generated
            reaproveitados += resultado.reused
            falhos += resultado.failed
            barrados += resultado.blocked
            if resultado.remaining == 0:
                break
            plan = await service.get(plan_public_id)

        restantes = sum(1 for item in plan.items if item.status == ItemStatus.PENDING)
        return {
            "status": "OK",
            "generated": gerados,
            "reused": reaproveitados,
            "failed": falhos,
            "blocked": barrados,
            "remaining": restantes,
        }


@shared_task(
    name="generation.run_plan",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
    time_limit=3600,
    soft_time_limit=3540,
)
def run_generation_plan_task(self: Any, plan_public_id: str) -> dict[str, Any]:
    """Executa um plano de geração já confirmado por uma pessoa."""
    resultado = asyncio.run(_run(plan_public_id))
    logger.info("generation.task_done", plan=plan_public_id, **resultado)
    return resultado
