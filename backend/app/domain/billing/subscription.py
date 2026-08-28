"""Ciclo de vida da assinatura — quando o acesso começa e quando termina.

A regra que evita o erro mais caro deste módulo: **cancelar não é cortar na
hora**. Quem pagou até o dia 30 tem acesso até o dia 30, mesmo tendo cancelado no
dia 2. Cortar imediatamente é cobrar por um serviço não entregue.

O outro cuidado é com a inadimplência: um pagamento que falha não vira corte
instantâneo. Há um período de tolerância declarado, porque cartão recusado é
quase sempre um problema de banco, não uma decisão de quem estuda.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

# Dias de tolerância após uma falha de cobrança antes de o acesso cair.
GRACE_DAYS = 5


class SubscriptionStatus(StrEnum):
    TRIALING = "TRIALING"
    ACTIVE = "ACTIVE"
    #: Cobrança falhou; ainda dentro da tolerância.
    PAST_DUE = "PAST_DUE"
    #: Cancelada pelo candidato, mas ainda no período pago.
    CANCELING = "CANCELING"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


#: Estados em que o candidato usa o plano contratado.
ENTITLED_STATES = frozenset(
    {
        SubscriptionStatus.TRIALING,
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.CANCELING,
    }
)

STATUS_LABEL: dict[str, str] = {
    SubscriptionStatus.TRIALING: "Em teste",
    SubscriptionStatus.ACTIVE: "Ativa",
    SubscriptionStatus.PAST_DUE: "Pagamento pendente",
    SubscriptionStatus.CANCELING: "Cancelada — ativa até o fim do período",
    SubscriptionStatus.CANCELED: "Cancelada",
    SubscriptionStatus.EXPIRED: "Expirada",
}


class ChangeKind(StrEnum):
    UPGRADE = "UPGRADE"
    DOWNGRADE = "DOWNGRADE"
    SAME = "SAME"


@dataclass(frozen=True, slots=True)
class SubscriptionState:
    status: str
    current_period_end: date | None
    trial_ends_on: date | None = None
    grace_ends_on: date | None = None

    @property
    def label(self) -> str:
        return STATUS_LABEL.get(self.status, self.status)


@dataclass(frozen=True, slots=True)
class ChangeDecision:
    kind: str
    #: Verdadeiro quando a troca vale já, e não no fim do período.
    immediate: bool
    #: Crédito proporcional do que sobrou do período atual, em centavos.
    credit_cents: int
    #: Quanto o candidato paga agora, já descontado o crédito.
    charge_cents: int
    reason: str


def is_entitled(state: SubscriptionState, *, today: date) -> bool:
    """Se o candidato tem direito ao plano contratado hoje."""
    if state.status not in ENTITLED_STATES:
        return False

    if state.status == SubscriptionStatus.PAST_DUE:
        # A tolerância é o que separa "cartão recusou" de "não é mais assinante".
        return state.grace_ends_on is not None and today <= state.grace_ends_on

    if state.current_period_end is not None:
        return today <= state.current_period_end
    return True


def next_status(state: SubscriptionState, *, today: date) -> str:
    """O estado que o tempo, sozinho, já produziu."""
    if state.status == SubscriptionStatus.TRIALING:
        if state.trial_ends_on is not None and today > state.trial_ends_on:
            # Terminado o teste, a assinatura precisa de pagamento confirmado.
            return SubscriptionStatus.PAST_DUE
        return state.status

    if state.status == SubscriptionStatus.PAST_DUE:
        if state.grace_ends_on is not None and today > state.grace_ends_on:
            return SubscriptionStatus.EXPIRED
        return state.status

    if state.status == SubscriptionStatus.CANCELING:
        if state.current_period_end is not None and today > state.current_period_end:
            return SubscriptionStatus.CANCELED
        return state.status

    if state.status == SubscriptionStatus.ACTIVE:
        if state.current_period_end is not None and today > state.current_period_end:
            return SubscriptionStatus.PAST_DUE
        return state.status

    return state.status


def grace_deadline(failed_on: date, *, days: int = GRACE_DAYS) -> date:
    return failed_on + timedelta(days=days)


def remaining_credit(*, price_cents: int, period_start: date, period_end: date, today: date) -> int:
    """Crédito proporcional aos dias não usados do período atual.

    Cobrar o plano novo sem descontar o que já foi pago seria cobrar duas vezes
    pelos mesmos dias.
    """
    total_days = (period_end - period_start).days + 1
    if total_days <= 0 or price_cents <= 0:
        return 0
    remaining = (period_end - today).days
    if remaining <= 0:
        return 0
    return int(price_cents * remaining / total_days)


def decide_change(
    *,
    current_price_cents: int,
    new_price_cents: int,
    period_start: date | None,
    period_end: date | None,
    today: date,
) -> ChangeDecision:
    """Decide como uma troca de plano acontece.

    Subir de plano vale **na hora**, com crédito do que sobrou. Descer vale **no
    fim do período**: quem pagou o mês inteiro tem o mês inteiro, e trocar não
    devolve dinheiro nem tira o que já foi pago.
    """
    if new_price_cents == current_price_cents:
        return ChangeDecision(
            kind=ChangeKind.SAME,
            immediate=False,
            credit_cents=0,
            charge_cents=0,
            reason="O plano escolhido é o mesmo que já está em vigor.",
        )

    if new_price_cents > current_price_cents:
        credit = (
            remaining_credit(
                price_cents=current_price_cents,
                period_start=period_start,
                period_end=period_end,
                today=today,
            )
            if period_start and period_end
            else 0
        )
        charge = max(0, new_price_cents - credit)
        return ChangeDecision(
            kind=ChangeKind.UPGRADE,
            immediate=True,
            credit_cents=credit,
            charge_cents=charge,
            reason=(
                f"Upgrade imediato. Os dias já pagos do plano atual viram um crédito de "
                f"R$ {credit / 100:.2f}, descontado da cobrança."
            ),
        )

    return ChangeDecision(
        kind=ChangeKind.DOWNGRADE,
        immediate=False,
        credit_cents=0,
        charge_cents=0,
        reason=(
            "Downgrade agendado para o fim do período atual. Você mantém o plano de "
            "hoje até lá — não há cobrança agora nem devolução."
        ),
    )


def period_end_for(start: date, *, months: int = 1) -> date:
    """Fim do período de cobrança a partir de uma data de início.

    Somamos meses de calendário, com o cuidado do dia 31: quem assina em 31 de
    janeiro renova em 28 de fevereiro, não em 3 de março.
    """
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = start.day
    while day > 0:
        try:
            return date(year, month, day) - timedelta(days=1)
        except ValueError:
            day -= 1
    raise ValueError("Data de período inválida.")
