"""Orquestrador de agentes.

Generaliza o que o pipeline de análise de edital já fazia bem — passos
persistidos, acompanháveis ao vivo, com motivo escrito quando algo é pulado — e
acrescenta o que faltava: dependências entre agentes, tentativas, custo por
passo e execução manual de um agente só.

Quatro regras governam este serviço:

*Agente que não existe não finge que rodou.* Dois dos oito ainda não foram
construídos e dois dependem da geração em massa. Eles são marcados como
**pulados com o motivo escrito** — nunca como concluídos. Um passo verde que
não fez nada é pior que um passo vermelho, porque ninguém investiga.

*O teto de custo é perguntado antes de cada passo.* Gerar conteúdo para um
edital inteiro é o caso que o orçamento existe para conter. Passo barrado fica
``BUDGET_BLOCKED``, que não se confunde com falha de código nem com conclusão.

*Falha de um agente não derruba os independentes.* Quem dependia dele é pulado
com o motivo; quem não dependia continua.

*Retomar não refaz o que deu certo.* Passo em estado terminal é deixado quieto.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.agents import (
    AGENT_BY_KEY,
    AGENTS,
    AgentSpec,
    RunStatus,
    StepStatus,
    StepView,
    can_retry,
    flat_order,
    summarize,
)
from app.models.agent_run import AgentRun, AgentStep
from app.models.audit import AuditAction
from app.models.catalog import Competition
from app.models.user import User
from app.services.ai_budget import AIBudgetService, BudgetExceededError
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AgentOutcome:
    """O que um agente devolve ao orquestrador."""

    detail: str
    result: dict[str, object] | None = None
    #: O agente pode concluir que não havia o que fazer — e isso é "pulado",
    #: não "concluído". A diferença importa para quem lê a tela.
    skipped: bool = False


#: Assinatura de um agente executável. Recebe a sessão e a execução; devolve o
#: que aconteceu, em português.
AgentCallable = Callable[[AsyncSession, AgentRun], Awaitable[AgentOutcome]]


class AgentRegistry:
    """Liga a chave do agente à função que o executa de verdade.

    O catálogo em ``app.domain.agents`` declara **o que** cada agente é; aqui
    mora **como** ele roda. Agente declarado sem implementação registrada é
    pulado com o motivo que o catálogo já traz.
    """

    def __init__(self) -> None:
        self._runners: dict[str, AgentCallable] = {}

    def register(self, key: str, runner: AgentCallable) -> None:
        self._runners[key] = runner

    def get(self, key: str) -> AgentCallable | None:
        return self._runners.get(key)


registry = AgentRegistry()


class OrchestratorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
        self.budget = AIBudgetService(session)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str) -> AgentRun:
        found = (
            await self.session.execute(select(AgentRun).where(AgentRun.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Execução não encontrada.")
        return found

    async def list(self, *, limit: int, offset: int) -> tuple[list[AgentRun], int]:
        base = select(AgentRun).order_by(AgentRun.created_at.desc())
        rows = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        total = len(list((await self.session.execute(select(AgentRun))).scalars().all()))
        return rows, total

    def view(self, run: AgentRun) -> list[StepView]:
        """Os passos no formato que a tela e o domínio entendem."""
        por_chave = {step.agent_key: step for step in run.steps}
        vistas: list[StepView] = []
        for key in flat_order():
            spec = AGENT_BY_KEY[key]
            step = por_chave.get(key)
            vistas.append(
                StepView(
                    key=key,
                    label=spec.label,
                    description=spec.description,
                    status=step.status if step else StepStatus.PENDING,
                    depends_on=spec.depends_on,
                    attempts=step.attempts if step else 0,
                    max_attempts=spec.max_attempts,
                    detail=step.detail if step else spec.pending_reason,
                    is_implemented=spec.is_implemented,
                )
            )
        return vistas

    # ------------------------------------------------------------------ #
    # Criação
    # ------------------------------------------------------------------ #
    async def create(
        self, actor: User, context: RequestContext, *, competition_public_id: str
    ) -> AgentRun:
        competition = (
            await self.session.execute(
                select(Competition).where(Competition.public_id == competition_public_id)
            )
        ).scalar_one_or_none()
        if competition is None:
            raise NotFoundError("Concurso não encontrado.")

        run = AgentRun(
            competition_id=competition.id,
            started_by_user_id=actor.id,
            status=RunStatus.PENDING,
        )
        for spec in AGENTS:
            run.steps.append(
                AgentStep(
                    agent_key=spec.key,
                    status=StepStatus.PENDING,
                    detail=spec.pending_reason if not spec.is_implemented else None,
                )
            )
        self.session.add(run)
        await self.audit.record(
            AuditAction.AGENT_RUN_STARTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_run",
            resource_id=run.public_id,
            meta={"competition": competition_public_id},
        )
        await self.session.commit()
        return await self.get(run.public_id)

    # ------------------------------------------------------------------ #
    # Execução
    # ------------------------------------------------------------------ #
    async def _finish(self, run: AgentRun) -> AgentRun:
        estado = summarize(self.view(run))
        run.status = estado
        if estado in {RunStatus.DONE, RunStatus.FAILED}:
            run.finished_at = datetime.now(UTC)
        run.cost_cents = sum((Decimal(step.cost_cents or 0) for step in run.steps), Decimal("0"))
        await self.session.commit()
        return await self.get(run.public_id)

    def _step_of(self, run: AgentRun, key: str) -> AgentStep:
        for step in run.steps:
            if step.agent_key == key:
                return step
        raise NotFoundError("Passo não encontrado nesta execução.")

    async def _run_step(self, run: AgentRun, spec: AgentSpec, *, manual: bool = False) -> None:
        step = self._step_of(run, spec.key)

        if step.status in {StepStatus.DONE, StepStatus.SKIPPED} and not manual:
            return

        # Dependência que não terminou bem impede o passo — e o motivo é
        # escrito, para quem lê a tela não precisar reconstruir a cadeia.
        concluidos = {item.agent_key for item in run.steps if item.status in {StepStatus.DONE}}
        faltando = [key for key in spec.depends_on if key not in concluidos]
        if faltando:
            rotulos = ", ".join(AGENT_BY_KEY[key].label for key in faltando)
            step.status = StepStatus.SKIPPED
            step.detail = f"Não rodou porque depende de: {rotulos}."
            step.finished_at = datetime.now(UTC)
            return

        runner = registry.get(spec.key)
        if runner is None or not spec.is_implemented:
            # Declarado, não construído. Pulado com motivo — nunca concluído.
            step.status = StepStatus.SKIPPED
            step.detail = spec.pending_reason or "Este agente ainda não foi implementado."
            step.finished_at = datetime.now(UTC)
            return

        if not can_retry(spec, step.attempts):
            step.status = StepStatus.FAILED
            step.detail = f"Esgotou as {spec.max_attempts} tentativas."
            return

        # O teto é perguntado antes de gastar. Barrado não é falha de código.
        try:
            await self.budget.guard(feature=f"agent.{spec.key}")
        except BudgetExceededError as exc:
            step.status = StepStatus.BUDGET_BLOCKED
            step.detail = str(exc.message if hasattr(exc, "message") else exc)
            step.finished_at = datetime.now(UTC)
            logger.warning("agent.budget_blocked", agent=spec.key, run=run.public_id)
            return

        step.status = StepStatus.RUNNING
        step.attempts += 1
        step.started_at = datetime.now(UTC)
        await self.session.commit()

        gasto_antes = (await self.budget.overview()).spent_month_cents
        try:
            outcome = await runner(self.session, run)
        except Exception as exc:
            step.status = StepStatus.FAILED
            step.detail = str(exc)[:1000]
            step.finished_at = datetime.now(UTC)
            logger.warning("agent.failed", agent=spec.key, run=run.public_id, error=str(exc))
        else:
            step.status = StepStatus.SKIPPED if outcome.skipped else StepStatus.DONE
            step.detail = outcome.detail
            step.result = dict(outcome.result or {})
            step.finished_at = datetime.now(UTC)
        # O custo do passo é a diferença do gasto no período: é o que a camada
        # de medição registrou, sem o orquestrador precisar contar token.
        gasto_depois = (await self.budget.overview()).spent_month_cents
        step.cost_cents = max(Decimal("0"), gasto_depois - gasto_antes)
        await self.session.commit()

    async def execute(self, run: AgentRun, actor: User, context: RequestContext) -> AgentRun:
        """Roda a execução inteira, na ordem das dependências."""
        if run.status == RunStatus.RUNNING:
            raise ConflictError("Esta execução já está em andamento.", code="agent_run_running")

        run.status = RunStatus.RUNNING
        run.started_at = run.started_at or datetime.now(UTC)
        await self.session.commit()

        for key in flat_order():
            await self._run_step(run, AGENT_BY_KEY[key])

        await self.audit.record(
            AuditAction.AGENT_RUN_FINISHED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_run",
            resource_id=run.public_id,
        )
        return await self._finish(run)

    async def execute_one(
        self, run: AgentRun, agent_key: str, actor: User, context: RequestContext
    ) -> AgentRun:
        """Roda um agente sozinho, por decisão de uma pessoa.

        É o que permite insistir num passo que falhou por configuração sem
        refazer a execução inteira.
        """
        spec = AGENT_BY_KEY.get(agent_key)
        if spec is None:
            raise NotFoundError("Agente desconhecido.")
        await self._run_step(run, spec, manual=True)
        await self.audit.record(
            AuditAction.AGENT_STEP_RUN,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_step",
            resource_id=f"{run.public_id}:{agent_key}",
        )
        return await self._finish(run)
