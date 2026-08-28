"""Indicadores de SaaS — com denominador à vista.

MRR, churn e ARPU são números que, mal calculados, sustentam decisões caras. As
regras aqui são as mesmas do resto da plataforma: **sem denominador não há
indicador**, e um valor ausente é ``None`` com motivo, nunca zero.

Churn de um período que ainda não fechou não é churn: é meia informação com cara
de indicador. Por isso ele exige período encerrado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class SubscriptionSnapshot:
    """Uma assinatura paga vigente, normalizada para o cálculo."""

    plan_slug: str
    price_cents: int
    #: Meses cobertos pelo pagamento (1 = mensal, 12 = anual).
    months: int = 1

    @property
    def monthly_cents(self) -> int:
        """Plano anual entra pelo duodécimo — senão o MRR vira serra.

        A divisão trunca de propósito: arredondar para baixo nunca superestima
        receita, e superestimar receita é o erro que dói.
        """
        return self.price_cents // max(1, self.months)


@dataclass(frozen=True, slots=True)
class Metric:
    key: str
    label: str
    #: ``None`` quando não há base para calcular.
    value: float | None
    unit: str
    #: O denominador ou a amostra, escritos.
    basis: str
    empty_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SaasMetrics:
    metrics: list[Metric] = field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None

    def get(self, key: str) -> Metric | None:
        return next((item for item in self.metrics if item.key == key), None)


def mrr(subscriptions: list[SubscriptionSnapshot]) -> Metric:
    """Receita recorrente mensal das assinaturas pagas vigentes."""
    paying = [item for item in subscriptions if item.price_cents > 0]
    if not paying:
        return Metric(
            key="mrr",
            label="MRR",
            value=None,
            unit="BRL",
            basis="nenhuma assinatura paga vigente",
            empty_reason="Ainda não há assinatura paga para somar.",
        )
    total = sum(item.monthly_cents for item in paying)
    return Metric(
        key="mrr",
        label="MRR",
        value=round(total / 100, 2),
        unit="BRL",
        basis=f"{len(paying)} assinatura(s) paga(s), planos anuais divididos por 12",
    )


def arpu(subscriptions: list[SubscriptionSnapshot]) -> Metric:
    """Receita média por assinante pagante."""
    paying = [item for item in subscriptions if item.price_cents > 0]
    if not paying:
        return Metric(
            key="arpu",
            label="ARPU",
            value=None,
            unit="BRL",
            basis="nenhum assinante pagante",
            empty_reason="ARPU precisa de pelo menos um assinante pagante.",
        )
    total = sum(item.monthly_cents for item in paying)
    return Metric(
        key="arpu",
        label="ARPU",
        value=round(total / len(paying) / 100, 2),
        unit="BRL",
        basis=f"MRR dividido por {len(paying)} assinante(s) pagante(s)",
    )


def churn(*, active_at_start: int, canceled_in_period: int, period_closed: bool) -> Metric:
    """Churn do período. Exige período encerrado e base não vazia."""
    if not period_closed:
        return Metric(
            key="churn",
            label="Churn",
            value=None,
            unit="%",
            basis="período ainda em curso",
            empty_reason=(
                "O churn só é calculado sobre um período encerrado. No meio do mês ele "
                "seria meia informação com cara de indicador."
            ),
        )
    if active_at_start <= 0:
        return Metric(
            key="churn",
            label="Churn",
            value=None,
            unit="%",
            basis="nenhuma assinatura ativa no início do período",
            empty_reason="Sem base no início do período, não há churn a calcular.",
        )
    return Metric(
        key="churn",
        label="Churn",
        value=round(canceled_in_period / active_at_start * 100, 2),
        unit="%",
        basis=f"{canceled_in_period} cancelamento(s) sobre {active_at_start} ativa(s)",
    )


def ai_cost(cost_cents: float, *, calls: int) -> Metric:
    if calls <= 0:
        return Metric(
            key="ai_cost",
            label="Custo de IA",
            value=None,
            unit="BRL",
            basis="nenhuma chamada de IA no período",
            empty_reason="Não houve uso de IA no período.",
        )
    return Metric(
        key="ai_cost",
        label="Custo de IA",
        value=round(cost_cents / 100, 2),
        unit="BRL",
        basis=f"{calls} chamada(s) registrada(s) em ai_usage",
    )


def gross_margin(mrr_metric: Metric, cost_metric: Metric) -> Metric:
    """Margem = MRR − custo de IA. Sem MRR, não há margem."""
    if mrr_metric.value is None:
        return Metric(
            key="margin",
            label="Margem sobre IA",
            value=None,
            unit="BRL",
            basis="sem MRR",
            empty_reason="A margem depende de receita recorrente, que ainda não existe.",
        )
    cost = cost_metric.value or 0.0
    return Metric(
        key="margin",
        label="Margem sobre IA",
        value=round(mrr_metric.value - cost, 2),
        unit="BRL",
        basis=f"MRR de R$ {mrr_metric.value:.2f} menos R$ {cost:.2f} de custo de IA",
    )


def build(
    *,
    subscriptions: list[SubscriptionSnapshot],
    active_at_start: int,
    canceled_in_period: int,
    period_closed: bool,
    cost_cents: float,
    ai_calls: int,
    period_start: date | None = None,
    period_end: date | None = None,
) -> SaasMetrics:
    receita = mrr(subscriptions)
    custo = ai_cost(cost_cents, calls=ai_calls)
    return SaasMetrics(
        metrics=[
            receita,
            arpu(subscriptions),
            churn(
                active_at_start=active_at_start,
                canceled_in_period=canceled_in_period,
                period_closed=period_closed,
            ),
            custo,
            gross_margin(receita, custo),
        ],
        period_start=period_start,
        period_end=period_end,
    )
