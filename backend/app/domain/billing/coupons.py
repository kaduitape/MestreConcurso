"""Cupons — desconto com regra explícita e recusa explicada.

Cupom recusado sem motivo é a forma mais rápida de perder uma venda e ganhar um
chamado de suporte. Toda recusa aqui devolve o motivo em texto, e o desconto
nunca ultrapassa o valor cobrado: cupom não gera crédito nem valor negativo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class DiscountKind(StrEnum):
    PERCENT = "PERCENT"
    FIXED = "FIXED"


@dataclass(frozen=True, slots=True)
class Coupon:
    code: str
    kind: str
    #: Percentual (1..100) ou centavos, conforme ``kind``.
    value: int
    is_active: bool = True
    starts_on: date | None = None
    ends_on: date | None = None
    max_redemptions: int | None = None
    redeemed: int = 0
    #: Vazio significa "vale para qualquer plano".
    plan_slugs: tuple[str, ...] = ()
    #: Uma vez por candidato, quando verdadeiro.
    once_per_user: bool = True
    min_amount_cents: int = 0


@dataclass(frozen=True, slots=True)
class CouponResult:
    valid: bool
    discount_cents: int
    final_cents: int
    #: Motivo da recusa. Vazio quando o cupom vale.
    reason: str = ""
    description: str = ""


def describe(coupon: Coupon) -> str:
    if coupon.kind == DiscountKind.PERCENT:
        return f"{coupon.value}% de desconto"
    return f"R$ {coupon.value / 100:.2f} de desconto"


def apply(
    coupon: Coupon,
    *,
    amount_cents: int,
    today: date,
    plan_slug: str,
    already_used_by_user: bool = False,
) -> CouponResult:
    """Valida o cupom e calcula o desconto. Toda recusa vem com o motivo."""

    def refuse(reason: str) -> CouponResult:
        return CouponResult(valid=False, discount_cents=0, final_cents=amount_cents, reason=reason)

    if not coupon.is_active:
        return refuse("Este cupom não está mais ativo.")
    if coupon.starts_on is not None and today < coupon.starts_on:
        return refuse(f"Este cupom passa a valer em {coupon.starts_on.strftime('%d/%m/%Y')}.")
    if coupon.ends_on is not None and today > coupon.ends_on:
        return refuse(f"Este cupom expirou em {coupon.ends_on.strftime('%d/%m/%Y')}.")
    if coupon.max_redemptions is not None and coupon.redeemed >= coupon.max_redemptions:
        return refuse("Este cupom já atingiu o número máximo de usos.")
    if coupon.plan_slugs and plan_slug not in coupon.plan_slugs:
        return refuse("Este cupom não vale para o plano escolhido.")
    if already_used_by_user and coupon.once_per_user:
        return refuse("Você já usou este cupom.")
    if amount_cents < coupon.min_amount_cents:
        return refuse(f"Este cupom vale a partir de R$ {coupon.min_amount_cents / 100:.2f}.")

    if coupon.kind == DiscountKind.PERCENT:
        discount = int(amount_cents * min(100, max(0, coupon.value)) / 100)
    else:
        discount = max(0, coupon.value)

    # O desconto não pode passar do valor cobrado: cupom não vira crédito.
    discount = min(discount, amount_cents)

    return CouponResult(
        valid=True,
        discount_cents=discount,
        final_cents=amount_cents - discount,
        description=describe(coupon),
    )
