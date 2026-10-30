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
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from traceback import format_exception

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.logging import get_logger, request_id_ctx
from app.domain.agents import (
    AGENT_BY_KEY,
    AGENTS,
    NO_ATTEMPT_CONSUMED,
    TERMINAL,
    AgentSpec,
    RunStatus,
    StepStatus,
    StepView,
    blocking_reason,
    can_retry,
    flat_order,
    summarize,
)
from app.models.agent_run import AgentRun, AgentStep, AgentStepAttempt
from app.models.ai import AIFeature
from app.models.audit import AuditAction
from app.models.catalog import Competition
from app.models.notice import Notice, NoticeKind
from app.models.user import User
from app.repositories.base import rowcount
from app.services.ai_budget import AIBudgetService, BudgetExceededError
from app.services.ai_settings import AISettingsService
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class Precheck:
    """Uma conferência de pré-requisito, com a ação que resolve a pendência."""

    key: str
    label: str
    ok: bool
    detail: str | None
    #: O que a tela deve oferecer. ``None`` quando não há ação possível ali.
    action: str | None = None
    #: O recurso sobre o qual a ação age, quando há um.
    resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentOutcome:
    """O que um agente devolve ao orquestrador.

    Os três resultados que não são "concluído" são diferentes entre si, e
    confundi-los foi o defeito mais caro deste fluxo:

    * ``skipped`` — rodou e não havia o que fazer. Resultado legítimo.
    * ``awaiting_input`` — falta insumo ou configuração. **Não consome
      tentativa**, porque nenhuma repetição resolve falta de PDF.
    * ``notes`` — cumpriu o contrato, com ressalvas que alguém precisa ler.
    """

    detail: str
    result: dict[str, object] | None = None
    #: O agente pode concluir que não havia o que fazer — e isso é "pulado",
    #: não "concluído". A diferença importa para quem lê a tela.
    skipped: bool = False
    #: Falta insumo ou configuração. Não é falha e não gasta tentativa.
    awaiting_input: bool = False
    #: O que ficou de fora, apesar de o passo ter cumprido o contrato.
    notes: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        """O estado do passo que este resultado produz."""
        if self.awaiting_input:
            return StepStatus.AWAITING_INPUT
        if self.skipped:
            return StepStatus.SKIPPED
        if self.notes:
            return StepStatus.DONE_WITH_NOTES
        return StepStatus.DONE


#: Assinatura de um agente executável. Recebe a sessão e a execução; devolve o
#: que aconteceu, em português.
AgentCallable = Callable[[AsyncSession, AgentRun], Awaitable[AgentOutcome]]


#: Como o resultado da execução é dito na auditoria. Os quatro níveis que o
#: pedido separa — requisição, aceitação do job, resultado do passo, resultado
#: da execução — precisam de palavras diferentes, senão a auditoria responde
#: "SUCCESS" para a pergunta errada.
AUDIT_STATUS_BY_RUN: dict[str, str] = {
    RunStatus.DONE: "SUCCESS",
    RunStatus.DONE_WITH_NOTES: "PARTIAL",
    RunStatus.FAILED: "FAILED",
    RunStatus.CANCELED: "CANCELED",
    RunStatus.RUNNING: "ACCEPTED",
    RunStatus.PENDING: "ACCEPTED",
}

#: Idem para um passo. ``BLOCKED`` e ``AWAITING_INPUT`` não são falha: são
#: pendência, e quem audita precisa poder separar uma da outra.
AUDIT_STATUS_BY_STEP: dict[str, str] = {
    StepStatus.DONE: "SUCCESS",
    StepStatus.DONE_WITH_NOTES: "PARTIAL",
    StepStatus.SKIPPED: "NOTHING_TO_DO",
    StepStatus.AWAITING_INPUT: "PENDING_INPUT",
    StepStatus.BLOCKED: "BLOCKED",
    StepStatus.NOT_IMPLEMENTED: "NOT_IMPLEMENTED",
    StepStatus.BUDGET_BLOCKED: "BUDGET_BLOCKED",
    StepStatus.FAILED: "FAILED",
    StepStatus.CANCELED: "CANCELED",
    StepStatus.RUNNING: "ACCEPTED",
}

#: Depois disto, um passo ``RUNNING`` sem sinal de vida é considerado morto
#: junto com o processo que o rodava. Sem este prazo, processo derrubado no
#: meio deixava o passo travado em "executando" para sempre.
STUCK_AFTER = timedelta(minutes=30)


def _explain(exc: BaseException) -> tuple[str, str]:
    """A causa em português e um código estável, a partir da exceção.

    Sem isto, a tela recebia ``str(exc)`` cru — que para um erro de banco é
    uma linha de SQL, e para um erro sem mensagem é string vazia. Pior: vazio
    era indistinguível de "não sei o que houve".
    """
    if isinstance(exc, AppError):
        return (exc.message or type(exc).__name__)[:1000], exc.code
    texto = str(exc).strip()
    if not texto:
        texto = f"Erro {type(exc).__name__} sem mensagem."
    return texto[:1000], "agent_unhandled_error"


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
        self.ai_settings = AISettingsService(session)

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

    async def list_runs(self, *, limit: int, offset: int) -> tuple[list[AgentRun], int]:
        base = select(AgentRun).order_by(AgentRun.created_at.desc())
        rows = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        # Contar no banco, não na memória: a lista de execuções só cresce.
        total = int(
            (await self.session.execute(select(func.count()).select_from(AgentRun))).scalar_one()
        )
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
        vistas = self.view(run)
        estado = summarize(vistas)
        run.status = estado
        if estado in {RunStatus.DONE, RunStatus.DONE_WITH_NOTES, RunStatus.FAILED}:
            run.finished_at = datetime.now(UTC)
        # ``error`` era lido pela API e nunca escrito: a tela recebia sempre
        # nulo mesmo numa execução falhada. Agora ele resume o que quebrou.
        quebrados = [item for item in vistas if item.status == StepStatus.FAILED]
        run.error = (
            "; ".join(
                f"{item.label}: {item.detail or 'sem causa registrada'}" for item in quebrados
            )[:2000]
            or None
        )
        run.cost_cents = sum((Decimal(step.cost_cents or 0) for step in run.steps), Decimal("0"))
        await self.session.commit()
        return await self.get(run.public_id)

    def _step_of(self, run: AgentRun, key: str) -> AgentStep:
        for step in run.steps:
            if step.agent_key == key:
                return step
        raise NotFoundError("Passo não encontrado nesta execução.")

    async def preflight(self, run: AgentRun) -> list[Precheck]:
        """O que falta antes de rodar tudo, com a ação de cada pendência.

        Existe para que a pessoa descubra que o edital não tem PDF **antes** de
        disparar oito agentes, e não depois de ver sete passos pulados em
        cascata. Não chama IA e não escreve nada.
        """
        checagens: list[Precheck] = []
        competition = (
            await self.session.execute(
                select(Competition).where(Competition.id == run.competition_id)
            )
        ).scalar_one_or_none()

        if competition is None:
            return [
                Precheck(
                    key="competition",
                    label="Concurso",
                    ok=False,
                    detail="A execução não está ligada a um concurso.",
                    action=None,
                )
            ]

        notices = (
            (
                await self.session.execute(
                    select(Notice).where(
                        Notice.competition_id == competition.id, Notice.kind == NoticeKind.MAIN
                    )
                )
            )
            .scalars()
            .all()
        )
        principal = next(iter(notices), None)
        if principal is None:
            checagens.append(
                Precheck(
                    key="notice",
                    label="Edital principal",
                    ok=False,
                    detail="O concurso não tem edital principal cadastrado.",
                    action="ATTACH_NOTICE",
                )
            )
        elif not principal.files:
            checagens.append(
                Precheck(
                    key="notice_file",
                    label="PDF do edital",
                    ok=False,
                    detail=(
                        f"O edital '{principal.title}' está cadastrado sem arquivo PDF. "
                        "Anexe o PDF ou importe o edital por URL."
                    ),
                    action="ATTACH_PDF",
                    resource_id=principal.public_id,
                )
            )
        else:
            checagens.append(
                Precheck(key="notice_file", label="PDF do edital", ok=True, detail=None)
            )

        if competition.exam_board is None:
            checagens.append(
                Precheck(
                    key="exam_board",
                    label="Banca",
                    ok=False,
                    detail=(
                        "O concurso não tem banca definida: a incidência não roda, mas as "
                        "aulas e a ordem de estudo não dependem dela."
                    ),
                    action="SET_BOARD",
                )
            )
        else:
            checagens.append(Precheck(key="exam_board", label="Banca", ok=True, detail=None))

        # Resolver a funcionalidade é a única forma honesta de saber se ela
        # está pronta: o vínculo pode existir e o provedor estar inativo, ou o
        # modelo estar fora de uso. Só o serviço que decide sabe disso.
        try:
            resolvido = await self.ai_settings.resolve_feature(AIFeature.NOTICE_EXTRACTION)
        except AppError as exc:
            checagens.append(
                Precheck(
                    key="ai_notice_extraction",
                    label="Modelo para análise de edital",
                    ok=False,
                    detail=exc.message,
                    action="CONFIGURE_AI",
                )
            )
        else:
            checagens.append(
                Precheck(
                    key="ai_notice_extraction",
                    label="Modelo para análise de edital",
                    ok=True,
                    detail=f"{resolvido.provider_slug} · {resolvido.model_slug}",
                )
            )

        try:
            await self.budget.guard(feature="agent.preflight")
        except BudgetExceededError as exc:
            checagens.append(
                Precheck(
                    key="budget",
                    label="Teto de gasto de IA",
                    ok=False,
                    detail=str(getattr(exc, "message", exc)),
                    action="RAISE_BUDGET",
                )
            )
        else:
            checagens.append(
                Precheck(key="budget", label="Teto de gasto de IA", ok=True, detail=None)
            )

        return checagens

    async def recover_stuck(self) -> int:
        """Devolve ao fluxo os passos que o processo deixou travados.

        Processo derrubado no meio de um passo deixa ``RUNNING`` eterno: a tela
        mostra "executando" para sempre e a execução nunca termina. Aqui o
        passo volta a falhar com a causa escrita, e a tentativa dele fecha —
        sem consumir outra, porque ela já foi contada quando começou.
        """
        limite = datetime.now(UTC) - STUCK_AFTER
        travados = (
            (
                await self.session.execute(
                    select(AgentStep).where(
                        AgentStep.status == StepStatus.RUNNING,
                        AgentStep.heartbeat_at.is_not(None),
                        AgentStep.heartbeat_at < limite,
                    )
                )
            )
            .scalars()
            .all()
        )
        for step in travados:
            detalhe = (
                "A execução deste passo foi interrompida (processo encerrado ou reiniciado) "
                f"e não deu sinal por mais de {int(STUCK_AFTER.total_seconds() // 60)} minutos."
            )
            step.status = StepStatus.FAILED
            step.detail = detalhe
            step.finished_at = datetime.now(UTC)
            step.heartbeat_at = None
            if step.tries:
                aberta = step.tries[-1]
                if aberta.finished_at is None:
                    aberta.status = StepStatus.FAILED
                    aberta.detail = detalhe
                    aberta.error_code = "agent_step_stuck"
                    aberta.finished_at = datetime.now(UTC)
            logger.warning("agent.step_recovered", step=step.agent_key, run_id=step.run_id)

        if travados:
            await self.session.commit()
        return len(travados)

    async def cancel(self, run: AgentRun, actor: User, context: RequestContext) -> AgentRun:
        """Para a execução por decisão de alguém, preservando o que já terminou.

        Passo em estado terminal fica como está: cancelar não desfaz trabalho
        concluído, e refazê-lo custaria IA de novo.
        """
        if run.status in {RunStatus.DONE, RunStatus.DONE_WITH_NOTES, RunStatus.CANCELED}:
            raise ConflictError("Esta execução já terminou.", code="agent_run_already_finished")
        for step in run.steps:
            if step.status not in TERMINAL and step.status != StepStatus.FAILED:
                step.status = StepStatus.CANCELED
                step.detail = "Cancelado antes de rodar."
                step.finished_at = datetime.now(UTC)
                step.heartbeat_at = None
        run.status = RunStatus.CANCELED
        run.canceled_at = datetime.now(UTC)
        run.canceled_by_user_id = actor.id
        run.finished_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.AGENT_RUN_FINISHED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_run",
            resource_id=run.public_id,
            status="CANCELED",
            meta={"run_status": RunStatus.CANCELED},
        )
        await self.session.commit()
        return await self.get(run.public_id)

    async def _run_step(self, run: AgentRun, spec: AgentSpec, *, manual: bool = False) -> None:
        step = self._step_of(run, spec.key)

        if step.status in TERMINAL and not manual:
            return

        # Dependência que não cumpriu o contrato impede o passo. O motivo traz
        # **o que aconteceu com a dependência**, não só o nome dela: era isso
        # que obrigava quem lê a tela a caçar o passo anterior.
        por_chave = {item.key: item for item in self.view(run)}
        motivo = blocking_reason(spec, por_chave)
        if motivo is not None:
            self._settle(step, StepStatus.BLOCKED, motivo)
            return

        runner = registry.get(spec.key)
        if runner is None or not spec.is_implemented:
            # Declarado, não construído. Nunca concluído — e agora com estado
            # próprio, em vez de se misturar a "rodou e não havia o que fazer".
            self._settle(
                step,
                StepStatus.NOT_IMPLEMENTED,
                spec.pending_reason or "Este agente ainda não tem implementação registrada.",
            )
            return

        if not can_retry(spec, step.attempts):
            # O detalhe **não** é tocado: a causa da última falha é o que serve
            # para diagnosticar, e sobrescrevê-la com "esgotou as tentativas"
            # era o que deixava a tela sem a causa original. Que as tentativas
            # acabaram é propriedade derivada de attempts × max_attempts.
            step.status = StepStatus.FAILED
            step.finished_at = step.finished_at or datetime.now(UTC)
            if not step.detail:
                step.detail = (
                    f"Falhou {step.attempts}× e não há causa registrada — "
                    "veja o histórico de tentativas."
                )
            return

        # O teto é perguntado antes de gastar. Barrado não é falha de código, e
        # também não consome tentativa: o agente nem foi chamado.
        try:
            await self.budget.guard(feature=f"agent.{spec.key}")
        except BudgetExceededError as exc:
            self._settle(
                step,
                StepStatus.BUDGET_BLOCKED,
                str(getattr(exc, "message", exc)),
            )
            logger.warning("agent.budget_blocked", agent=spec.key, run=run.public_id)
            return

        tentativa = AgentStepAttempt(
            number=step.attempts + 1,
            status=StepStatus.RUNNING,
            request_id=request_id_ctx.get(),
            started_at=datetime.now(UTC),
        )
        step.tries.append(tentativa)
        step.status = StepStatus.RUNNING
        step.attempts += 1
        step.started_at = step.started_at or datetime.now(UTC)
        step.heartbeat_at = datetime.now(UTC)
        await self.session.commit()

        # Os identificadores são guardados como texto: o rollback abaixo expira
        # todo objeto da sessão, e ler ``run.public_id`` de um objeto expirado
        # dispara um SELECT fora do laço assíncrono.
        run_public_id = run.public_id
        numero = tentativa.number

        comeco = perf_counter()
        gasto_antes = (await self.budget.overview()).spent_month_cents
        try:
            outcome = await runner(self.session, run)
        except Exception as exc:
            # A sessão pode ter ficado inutilizável — um erro de banco deixa a
            # transação morta, e todo SELECT seguinte estoura. Sem este
            # rollback, o próprio tratamento de erro quebrava e a causa real
            # era substituída por um estouro genérico mais adiante.
            await self.session.rollback()
            run = await self.get(run_public_id)
            step = self._step_of(run, spec.key)
            tentativa = next(
                (item for item in step.tries if item.number == numero),
                None,
            ) or AgentStepAttempt(step_id=step.id, number=numero, started_at=datetime.now(UTC))
            if tentativa not in step.tries:
                step.tries.append(tentativa)
            detalhe, codigo = _explain(exc)
            step.status = StepStatus.FAILED
            step.detail = detalhe
            step.finished_at = datetime.now(UTC)
            tentativa.status = StepStatus.FAILED
            tentativa.detail = detalhe
            tentativa.error_code = codigo
            tentativa.error_class = f"{type(exc).__module__}.{type(exc).__qualname__}"[:160]
            # A pilha fica **no servidor**: a tela recebe o detalhe em
            # português, e quem investiga tem o caminho inteiro aqui.
            tentativa.traceback = "".join(format_exception(type(exc), exc, exc.__traceback__))[
                -8000:
            ]
            logger.warning(
                "agent.failed",
                agent=spec.key,
                run=run_public_id,
                attempt=tentativa.number,
                error_code=codigo,
                exc_info=exc,
            )
        else:
            step.status = outcome.status
            step.detail = outcome.detail
            step.result = dict(outcome.result or {})
            if outcome.notes:
                step.result["notes"] = list(outcome.notes)
            step.finished_at = datetime.now(UTC)
            tentativa.status = step.status
            tentativa.detail = outcome.detail
            if step.status in NO_ATTEMPT_CONSUMED:
                # Falta de insumo não gasta tentativa. Era exatamente isto que
                # levava um edital sem PDF a "esgotar as 2 tentativas" sem
                # nunca ter havido falha nenhuma.
                step.attempts = max(0, step.attempts - 1)
                tentativa.number = step.attempts + 1

        step.heartbeat_at = None
        tentativa.finished_at = datetime.now(UTC)
        tentativa.duration_ms = int((perf_counter() - comeco) * 1000)
        # O custo do passo é a diferença do gasto no período: é o que a camada
        # de medição registrou, sem o orquestrador precisar contar token.
        gasto_depois = (await self.budget.overview()).spent_month_cents
        custo = max(Decimal("0"), gasto_depois - gasto_antes)
        step.cost_cents = Decimal(step.cost_cents or 0) + custo
        tentativa.cost_cents = custo
        await self.session.commit()

    def _settle(self, step: AgentStep, status: str, detail: str) -> None:
        """Encerra o passo sem ter chamado o agente.

        Nenhum destes estados consome tentativa, e é por isso que eles passam
        por aqui em vez de pelo caminho de execução.
        """
        step.status = status
        step.detail = detail
        step.finished_at = datetime.now(UTC)
        step.heartbeat_at = None

    async def execute(self, run: AgentRun, actor: User, context: RequestContext) -> AgentRun:
        """Roda a execução inteira, na ordem das dependências."""
        await self._claim(run)
        actor_id, public_id = actor.id, run.public_id

        for key in flat_order():
            run = await self.get(public_id)
            if run.status == RunStatus.CANCELED:
                logger.info("agent.run_canceled_midway", run=public_id)
                break
            await self._run_step(run, AGENT_BY_KEY[key])

        run = await self.get(public_id)
        run = await self._finish(run)
        actor = await self._reload_actor(actor_id, actor)
        # A auditoria registra o **resultado da execução**, não o sucesso do
        # pedido HTTP. Era isso que gravava SUCCESS para execução falhada: o
        # status vinha do padrão do método, que descreve a requisição.
        await self.audit.record(
            AuditAction.AGENT_RUN_FINISHED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_run",
            resource_id=run.public_id,
            status=AUDIT_STATUS_BY_RUN.get(run.status, "SUCCESS"),
            meta=self._audit_meta(run),
        )
        await self.session.commit()
        return run

    async def _reload_actor(self, actor_id: int, fallback: User) -> User:
        """O ator recarregado, porque um passo que quebrou pode tê-lo expirado.

        O rollback que salva a sessão de uma transação morta expira **todos** os
        objetos dela, o ator incluído. Auditar com um objeto expirado dispara um
        SELECT fora do laço assíncrono e estoura — trocando a causa real do
        problema por um erro de infraestrutura no meio do registro.
        """
        encontrado = (
            await self.session.execute(select(User).where(User.id == actor_id))
        ).scalar_one_or_none()
        return encontrado or fallback

    async def enqueue(self, run: AgentRun, actor: User, context: RequestContext) -> AgentRun:
        """Aceita o trabalho e devolve na hora, deixando o resto para a fila.

        A execução vira ``PENDING`` com a marca de quem pediu e o id de
        correlação, e a tarefa segue fora do ciclo HTTP. É o que garante que
        fechar a página ou ter a sessão expirada não cancele um job que o
        servidor já aceitou.

        A trava de execução simultânea continua valendo: enfileirar duas vezes
        a mesma execução é recusado aqui, antes de a tarefa sair.
        """
        from app.workers.tasks.agents import run_agents_task

        if run.status == RunStatus.RUNNING:
            raise ConflictError("Esta execução já está em andamento.", code="agent_run_running")
        if run.status in {RunStatus.DONE, RunStatus.DONE_WITH_NOTES, RunStatus.CANCELED}:
            raise ConflictError("Esta execução já terminou.", code="agent_run_already_finished")

        run.request_id = request_id_ctx.get()
        await self.audit.record(
            AuditAction.AGENT_RUN_STARTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_run",
            resource_id=run.public_id,
            # "Aceito" é um nível próprio: não é o resultado da execução, é o
            # servidor dizendo que assumiu o trabalho.
            status="ACCEPTED",
            meta={"mode": "background", "request_id": run.request_id},
        )
        await self.session.commit()

        run_agents_task.apply_async(
            kwargs={"run_public_id": run.public_id, "actor_id": actor.id}, retry=False
        )
        logger.info("agents.enqueued", run=run.public_id)
        return await self.get(run.public_id)

    async def _claim(self, run: AgentRun) -> None:
        """Marca a execução como em andamento, uma vez só.

        A trava é no banco, com ``UPDATE … WHERE status <> 'RUNNING'``: ler e
        depois escrever deixava uma janela em que dois pedidos simultâneos
        passavam os dois pela conferência e rodavam os mesmos agentes em
        paralelo, cada um gastando IA.
        """
        agora = datetime.now(UTC)
        resultado = await self.session.execute(
            update(AgentRun)
            .where(AgentRun.id == run.id, AgentRun.status != RunStatus.RUNNING)
            .values(
                status=RunStatus.RUNNING,
                started_at=func.coalesce(AgentRun.started_at, agora),
                request_id=request_id_ctx.get(),
            )
        )
        await self.session.commit()
        if rowcount(resultado) == 0:
            raise ConflictError("Esta execução já está em andamento.", code="agent_run_running")

    def _audit_meta(self, run: AgentRun) -> dict[str, object]:
        """O que a auditoria guarda de uma execução: contagem por estado."""
        contagem: dict[str, int] = {}
        for step in run.steps:
            contagem[step.status] = contagem.get(step.status, 0) + 1
        return {
            "run_status": run.status,
            "steps": contagem,
            "cost_cents": str(run.cost_cents),
            "request_id": run.request_id,
        }

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
        actor_id, public_id = actor.id, run.public_id
        await self._run_step(run, spec, manual=True)
        run = await self._finish(await self.get(public_id))
        actor = await self._reload_actor(actor_id, actor)
        passo = self._step_of(run, agent_key)
        # Mesma regra da execução inteira: o registro descreve o que o passo
        # fez, não o fato de a requisição ter chegado.
        await self.audit.record(
            AuditAction.AGENT_STEP_RUN,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="agent_step",
            resource_id=f"{run.public_id}:{agent_key}",
            status=AUDIT_STATUS_BY_STEP.get(passo.status, "SUCCESS"),
            meta={
                "step_status": passo.status,
                "attempts": passo.attempts,
                "detail": (passo.detail or "")[:500],
                "request_id": request_id_ctx.get(),
            },
        )
        await self.session.commit()
        return run
