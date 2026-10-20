"""Medir o gasto com IA e cortar quando passar do teto.

Antes desta camada, a tabela ``ai_usage`` existia e **nenhum código escrevia
nela**: o painel de custo reportava zero desde sempre, e um teto sobre esse
número seria ficção. Aqui ela passa a ser alimentada em todo caminho que fala
com um provedor.

Três decisões que valem explicação:

*O registro sobrevive à falha de quem chamou.* O consumo é gravado numa sessão
própria. O token foi gasto mesmo que a funcionalidade tenha dado erro depois —
descartar o registro junto com a transação do chamador esconderia dinheiro
real.

*Preço ausente não vira zero.* Modelo sem preço cadastrado grava os tokens e
marca o total do período como **incompleto**. O painel mostra isso, para a
pessoa cadastrar o preço em vez de confiar num número menor que o real.

*O corte acontece na chamada seguinte.* O custo de uma chamada só é conhecido
depois dela: não há como projetar tokens de saída sem inventar um número. Então
o teto barra a **próxima** chamada depois de ser estourado, e o estouro máximo
é de uma chamada. Preferi essa honestidade a uma estimativa fabricada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain.ai_budget import (
    BudgetLimits,
    BudgetState,
    CostEstimate,
    check,
    cost_of,
)
from app.models.ai import AIBudget, AIModel, AIUsage
from app.models.audit import AuditAction
from app.models.user import User
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

GLOBAL_SCOPE = "GLOBAL"


class BudgetExceededError(AppError):
    """O teto de gasto com IA foi atingido."""

    status_code = 429
    code = "ai_budget_exceeded"


@dataclass(frozen=True, slots=True)
class BudgetOverview:
    limits: BudgetLimits
    spent_month_cents: Decimal
    #: Falso quando algum gasto do mês veio de modelo sem preço cadastrado.
    is_complete: bool
    calls_month: int
    #: Modelos usados no mês que não têm preço — é o que torna o total incompleto.
    models_without_price: list[str]


def _month_start(now: datetime | None = None) -> datetime:
    reference = now or datetime.now(UTC)
    return reference.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


class AIBudgetService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Limites
    # ------------------------------------------------------------------ #
    async def _row(self) -> AIBudget:
        found = (
            await self.session.execute(select(AIBudget).where(AIBudget.scope == GLOBAL_SCOPE))
        ).scalar_one_or_none()
        if found is None:
            found = AIBudget(scope=GLOBAL_SCOPE)
            self.session.add(found)
            await self.session.flush()
        return found

    async def limits(self) -> BudgetLimits:
        row = await self._row()
        return BudgetLimits(
            monthly_cents=Decimal(row.monthly_limit_cents or 0),
            per_run_cents=Decimal(row.per_run_limit_cents or 0),
            is_enabled=bool(row.is_enabled),
        )

    async def set_limits(
        self,
        actor: User,
        context: RequestContext,
        *,
        is_enabled: bool,
        monthly_limit_cents: Decimal,
        per_run_limit_cents: Decimal,
    ) -> BudgetLimits:
        row = await self._row()
        row.is_enabled = is_enabled
        row.monthly_limit_cents = max(Decimal("0"), monthly_limit_cents)
        row.per_run_limit_cents = max(Decimal("0"), per_run_limit_cents)
        await self.audit.record(
            AuditAction.AI_BUDGET_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_budget",
            resource_id=GLOBAL_SCOPE,
            meta={
                "is_enabled": is_enabled,
                "monthly_limit_cents": str(row.monthly_limit_cents),
                "per_run_limit_cents": str(row.per_run_limit_cents),
            },
        )
        await self.session.commit()
        return await self.limits()

    # ------------------------------------------------------------------ #
    # Consumo
    # ------------------------------------------------------------------ #
    async def overview(self) -> BudgetOverview:
        inicio = _month_start()
        total, chamadas = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(AIUsage.cost_cents), 0),
                    func.count(AIUsage.id),
                ).where(AIUsage.created_at >= inicio)
            )
        ).one()

        # Modelos sem preço tornam o total menor que o real; dizer quais é o
        # que permite consertar o cadastro em vez de desconfiar do número.
        sem_preco = (
            (
                await self.session.execute(
                    select(AIUsage.model_slug)
                    .where(AIUsage.created_at >= inicio, AIUsage.cost_cents == 0)
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        return BudgetOverview(
            limits=await self.limits(),
            spent_month_cents=Decimal(total or 0),
            is_complete=not sem_preco,
            calls_month=int(chamadas or 0),
            models_without_price=sorted(str(item) for item in sem_preco),
        )

    async def state(self, *, spent_run_cents: Decimal = Decimal("0")) -> BudgetState:
        resumo = await self.overview()
        return BudgetState(
            spent_month_cents=resumo.spent_month_cents,
            spent_run_cents=spent_run_cents,
            is_complete=resumo.is_complete,
        )

    async def guard(self, *, feature: str, spent_run_cents: Decimal = Decimal("0")) -> None:
        """Barra a próxima chamada quando o teto já foi estourado."""
        limites = await self.limits()
        if not limites.is_enabled:
            return
        decisao = check(limites, await self.state(spent_run_cents=spent_run_cents), CostEstimate())
        if not decisao.allowed:
            logger.warning("ai.budget.blocked", feature=feature, verdict=decisao.verdict)
            raise BudgetExceededError(
                decisao.reason or "O teto de gasto com IA foi atingido.",
            )


async def record_usage(
    *,
    feature: str,
    provider_slug: str,
    model_slug: str,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1k: Decimal | None,
    output_cost_per_1k: Decimal | None,
    latency_ms: int | None = None,
    user_id: int | None = None,
    status: str = "SUCCESS",
    error_code: str | None = None,
    cached: bool = False,
) -> CostEstimate:
    """Grava o consumo numa sessão própria.

    Sessão própria de propósito: se a funcionalidade falhar depois da chamada e
    o chamador desfizer a transação dele, o gasto continua registrado. O token
    foi consumido de qualquer jeito.
    """
    custo = cost_of(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_cost_per_1k=input_cost_per_1k,
        output_cost_per_1k=output_cost_per_1k,
    )
    factory = get_session_factory()
    try:
        async with factory() as session:
            session.add(
                AIUsage(
                    user_id=user_id,
                    feature=feature,
                    provider_slug=provider_slug,
                    model_slug=model_slug,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_cents=custo.cents,
                    latency_ms=latency_ms,
                    status=status,
                    error_code=error_code,
                    cached=cached,
                )
            )
            await session.commit()
    except Exception as exc:  # pragma: no cover - contabilidade não derruba a feature
        # Falhar aqui não pode quebrar a funcionalidade que já respondeu ao
        # usuário; o log é o que denuncia a lacuna no registro.
        logger.warning("ai.usage.record_failed", feature=feature, error=str(exc))
    return custo


async def price_of(session: AsyncSession, model_id: int) -> tuple[Decimal | None, Decimal | None]:
    """Preço por 1k tokens do modelo, como está cadastrado. ``None`` é ausência."""
    model = (
        await session.execute(select(AIModel).where(AIModel.id == model_id))
    ).scalar_one_or_none()
    if model is None:
        return None, None
    entrada = model.input_cost_per_1k
    saida = model.output_cost_per_1k
    return (
        Decimal(entrada) if entrada is not None else None,
        Decimal(saida) if saida is not None else None,
    )
