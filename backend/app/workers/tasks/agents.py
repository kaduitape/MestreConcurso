"""Execução dos agentes fora do ciclo HTTP.

Por que isto existe. A execução rodava **dentro da requisição**: o navegador
ficava esperando oito agentes, e se a aba fechasse, a sessão expirasse ou o
proxy cortasse a conexão, o servidor cancelava a tarefa no meio. Um trabalho
que já tinha sido aceito morria por um motivo que não tinha nada a ver com ele
— e os passos ficavam travados em "executando" para sempre.

Agora o pedido devolve a execução imediatamente e o trabalho segue aqui. O
estado mora no banco, passo a passo, então:

* fechar a página não cancela nada;
* reiniciar o worker retoma de onde parou, porque passo em estado terminal é
  deixado quieto;
* o varredor de travados devolve ao fluxo o passo cujo processo morreu.

Cancelar continua sendo decisão de uma pessoa, e aí é explícito: a execução
passa a ``CANCELED`` e o laço para na próxima volta.
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain.agents import RunStatus
from app.services.auth import RequestContext

# Importar a aplicação Celery aqui não é adorno: `shared_task` se liga à
# aplicação **corrente**, e sem esta linha a tarefa acaba numa aplicação padrão
# que não conhece a configuração do projeto — inclusive o modo síncrono dos
# testes, que então tentariam falar com um broker que não existe.
from app.workers.celery_app import celery_app  # noqa: F401

logger = get_logger(__name__)


async def _run(run_public_id: str, actor_id: int) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        # Importar aqui mantém o registro dos agentes fora do import do módulo:
        # é o mesmo motivo pelo qual o router importa `agent_runners`.
        from sqlalchemy import select

        from app.models.user import User
        from app.services import agent_runners  # noqa: F401  (registra os agentes)
        from app.services.orchestrator import OrchestratorService

        service = OrchestratorService(session)
        run = await service.get(run_public_id)
        if run.status in {RunStatus.CANCELED, RunStatus.DONE, RunStatus.DONE_WITH_NOTES}:
            logger.info("agents.task_skipped", run=run_public_id, status=run.status)
            return {"status": "SKIPPED", "run_status": run.status}

        actor = (
            await session.execute(select(User).where(User.id == actor_id))
        ).scalar_one_or_none()
        if actor is None:
            # Sem a pessoa que pediu não há em nome de quem auditar o resultado.
            logger.warning("agents.task_without_actor", run=run_public_id)
            return {"status": "NO_ACTOR"}

        # Passo travado de uma execução anterior volta ao fluxo antes de
        # começar: senão ele seguraria a execução em "executando" para sempre.
        recuperados = await service.recover_stuck()

        run = await service.execute(await service.get(run_public_id), actor, RequestContext())
        contagem: dict[str, int] = {}
        for step in run.steps:
            contagem[step.status] = contagem.get(step.status, 0) + 1
        return {
            "status": "OK",
            "run_status": run.status,
            "recovered_stuck": recuperados,
            "steps": contagem,
        }


@shared_task(
    name="agents.run_all",
    bind=True,
    # Sem retentativa automática da tarefa: as tentativas são **por passo**, com
    # teto declarado no catálogo de agentes. Repetir a tarefa inteira refaria o
    # que já deu certo e gastaria IA de novo.
    max_retries=0,
    time_limit=7200,
    soft_time_limit=7080,
)
def run_agents_task(self: Any, run_public_id: str, actor_id: int) -> dict[str, Any]:
    """Executa os agentes de uma execução já criada."""
    resultado = asyncio.run(_run(run_public_id, actor_id))
    logger.info("agents.task_done", run=run_public_id, **resultado)
    return resultado


@shared_task(name="agents.recover_stuck", bind=True, max_retries=0, time_limit=600)
def recover_stuck_steps_task(self: Any) -> dict[str, Any]:
    """Devolve ao fluxo os passos cujo processo morreu no meio.

    Roda sozinha, pela rotina de manutenção: um passo travado não se resolve na
    próxima execução (ela é recusada enquanto a anterior parece estar em
    andamento), então alguém precisa varrer.
    """

    async def _sweep() -> int:
        factory = get_session_factory()
        async with factory() as session:
            from app.services.orchestrator import OrchestratorService

            return await OrchestratorService(session).recover_stuck()

    recuperados = asyncio.run(_sweep())
    logger.info("agents.recover_stuck_done", recovered=recuperados)
    return {"status": "OK", "recovered": recuperados}
