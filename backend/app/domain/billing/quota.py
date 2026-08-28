"""Limites de consumo — a parte "limitar" do ciclo assinar → cobrar → limitar.

Uma recusa por limite precisa dizer **três coisas**: que o limite existe, quanto
já foi usado e o que fazer (esperar a virada ou mudar de plano). Recusa sem essas
três coisas vira suporte, e suporte por bloqueio mal explicado é o pior tipo.

Nenhum limite mora aqui. Este módulo recebe o direito de uso já resolvido do
banco e apenas decide se cabe mais uma.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.billing.plans import Entitlement, Period


@dataclass(frozen=True, slots=True)
class Window:
    starts_on: date
    ends_on: date | None

    @property
    def is_open(self) -> bool:
        """Janela ``TOTAL`` não vira: o consumo dela nunca reinicia."""
        return self.ends_on is None


@dataclass(frozen=True, slots=True)
class QuotaCheck:
    feature: str
    label: str
    allowed: bool
    #: ``None`` significa ilimitado — nunca "sem acesso".
    limit: int | None
    used: int
    remaining: int | None
    period: str
    #: Quando o contador zera. Nulo em limites totais e ilimitados.
    resets_on: date | None
    #: Vazio quando permitido; explica a recusa quando não.
    reason: str = ""

    @property
    def is_unlimited(self) -> bool:
        return self.allowed and self.limit is None


def window_for(period: str, *, today: date, anchor: date | None = None) -> Window:
    """A janela em que o consumo é contado.

    A janela mensal segue o **aniversário da assinatura**, não o mês do
    calendário: quem assinou dia 20 tem o contador zerado todo dia 20. Usar o mês
    civil daria a quem assina no fim do mês um ciclo de poucos dias.
    """
    if period == Period.DAY:
        return Window(starts_on=today, ends_on=today)

    if period == Period.TOTAL:
        return Window(starts_on=anchor or today, ends_on=None)

    if anchor is None:
        first = today.replace(day=1)
        month = first.month % 12 + 1
        year = first.year + (1 if first.month == 12 else 0)
        return Window(starts_on=first, ends_on=date(year, month, 1) - timedelta(days=1))

    # Aniversário da assinatura: recua o dia do anchor até caber neste mês.
    day = min(anchor.day, _days_in_month(today.year, today.month))
    start = date(today.year, today.month, day)
    if start > today:
        month = today.month - 1 or 12
        year = today.year - (1 if today.month == 1 else 0)
        start = date(year, month, min(anchor.day, _days_in_month(year, month)))

    month = start.month % 12 + 1
    year = start.year + (1 if start.month == 12 else 0)
    end = date(year, month, min(anchor.day, _days_in_month(year, month))) - timedelta(days=1)
    return Window(starts_on=start, ends_on=end)


def _days_in_month(year: int, month: int) -> int:
    next_month = month % 12 + 1
    next_year = year + (1 if month == 12 else 0)
    return (date(next_year, next_month, 1) - timedelta(days=1)).day


def check(
    entitlement: Entitlement,
    *,
    used: int,
    today: date,
    anchor: date | None = None,
    plan_name: str = "",
) -> QuotaCheck:
    """Decide se cabe mais um uso, e explica quando não cabe."""
    window = window_for(entitlement.period, today=today, anchor=anchor)

    if not entitlement.enabled:
        return QuotaCheck(
            feature=entitlement.feature,
            label=entitlement.label,
            allowed=False,
            limit=0,
            used=used,
            remaining=0,
            period=entitlement.period,
            resets_on=None,
            reason=(
                f"{entitlement.label} não está incluído"
                + (f" no plano {plan_name}." if plan_name else " no seu plano.")
                + " Veja os planos para liberar este recurso."
            ),
        )

    if entitlement.limit is None:
        return QuotaCheck(
            feature=entitlement.feature,
            label=entitlement.label,
            allowed=True,
            limit=None,
            used=used,
            remaining=None,
            period=entitlement.period,
            resets_on=None,
        )

    remaining = max(0, entitlement.limit - used)
    if remaining > 0:
        return QuotaCheck(
            feature=entitlement.feature,
            label=entitlement.label,
            allowed=True,
            limit=entitlement.limit,
            used=used,
            remaining=remaining,
            period=entitlement.period,
            resets_on=window.ends_on,
        )

    if window.ends_on is None:
        recomeco = "Este limite não se renova."
    else:
        renova = window.ends_on + timedelta(days=1)
        recomeco = f"O contador zera em {renova.strftime('%d/%m/%Y')}."

    return QuotaCheck(
        feature=entitlement.feature,
        label=entitlement.label,
        allowed=False,
        limit=entitlement.limit,
        used=used,
        remaining=0,
        period=entitlement.period,
        resets_on=window.ends_on,
        reason=(
            f"Você usou {used} de {entitlement.limit} — o limite de “{entitlement.label}” "
            f"do seu plano. {recomeco} Mudar de plano libera mais agora."
        ),
    )
