"""Custo de IA: o que não se sabe não vira zero.

O teste mais importante aqui é o do preço ausente. Somar desconhecido como
zero faria o teto parecer respeitado enquanto a fatura cresce — é a forma mais
silenciosa de o controle de custo falhar.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.ai_budget import (
    BudgetLimits,
    BudgetState,
    BudgetVerdict,
    CostEstimate,
    check,
    cost_of,
)

PRECO_ENTRADA = Decimal("0.15")  # centavos por 1k tokens
PRECO_SAIDA = Decimal("0.60")


def test_cost_is_computed_from_the_registered_price() -> None:
    custo = cost_of(
        input_tokens=2000,
        output_tokens=1000,
        input_cost_per_1k=PRECO_ENTRADA,
        output_cost_per_1k=PRECO_SAIDA,
    )
    # 2 * 0,15 + 1 * 0,60 = 0,90 centavos
    assert custo.cents == Decimal("0.900000")
    assert custo.is_known is True


def test_a_model_without_a_price_is_unknown_not_free() -> None:
    """A regra que sustenta o módulo."""
    custo = cost_of(
        input_tokens=100_000,
        output_tokens=50_000,
        input_cost_per_1k=None,
        output_cost_per_1k=PRECO_SAIDA,
    )
    assert custo.is_known is False
    assert custo.cents == Decimal("0")


def test_half_a_price_is_still_unknown() -> None:
    """Contar só a entrada daria um número menor que o real."""
    assert (
        cost_of(
            input_tokens=10,
            output_tokens=10,
            input_cost_per_1k=PRECO_ENTRADA,
            output_cost_per_1k=None,
        ).is_known
        is False
    )


def test_unknown_contaminates_the_sum() -> None:
    conhecido = CostEstimate(cents=Decimal("5"), is_known=True)
    desconhecido = CostEstimate(cents=Decimal("0"), is_known=False)
    total = conhecido + desconhecido
    assert total.is_known is False, "um total parcial não pode se passar por completo"


def test_negative_tokens_do_not_generate_credit() -> None:
    custo = cost_of(
        input_tokens=-500,
        output_tokens=0,
        input_cost_per_1k=PRECO_ENTRADA,
        output_cost_per_1k=PRECO_SAIDA,
    )
    assert custo.cents == Decimal("0")


# --------------------------------------------------------------------------- #
# O corte
# --------------------------------------------------------------------------- #
def test_with_the_ceiling_off_nothing_is_cut() -> None:
    decisao = check(
        BudgetLimits(is_enabled=False),
        BudgetState(spent_month_cents=Decimal("999999")),
        CostEstimate(cents=Decimal("1000")),
    )
    assert decisao.allowed


def test_zero_means_no_ceiling_even_with_the_control_on() -> None:
    limites = BudgetLimits(is_enabled=True, monthly_cents=Decimal("0"))
    assert limites.has_monthly is False
    assert check(limites, BudgetState(), CostEstimate(cents=Decimal("1000"))).allowed


def test_the_run_ceiling_cuts_before_spending() -> None:
    decisao = check(
        BudgetLimits(is_enabled=True, per_run_cents=Decimal("100")),
        BudgetState(spent_run_cents=Decimal("95")),
        CostEstimate(cents=Decimal("10")),
    )
    assert decisao.allowed is False
    assert decisao.verdict == BudgetVerdict.RUN_EXCEEDED
    assert "teto por execução" in (decisao.reason or "")


def test_the_monthly_ceiling_cuts_too() -> None:
    decisao = check(
        BudgetLimits(is_enabled=True, monthly_cents=Decimal("10000")),
        BudgetState(spent_month_cents=Decimal("9999")),
        CostEstimate(cents=Decimal("5")),
    )
    assert decisao.verdict == BudgetVerdict.MONTH_EXCEEDED


def test_landing_exactly_on_the_ceiling_is_allowed() -> None:
    decisao = check(
        BudgetLimits(is_enabled=True, per_run_cents=Decimal("100")),
        BudgetState(spent_run_cents=Decimal("90")),
        CostEstimate(cents=Decimal("10")),
    )
    assert decisao.allowed, "o teto é o limite, não o que vem antes dele"


def test_the_reason_says_the_numbers_in_money() -> None:
    """Quem administra precisa entender o corte sem abrir o código."""
    decisao = check(
        BudgetLimits(is_enabled=True, monthly_cents=Decimal("5000")),
        BudgetState(spent_month_cents=Decimal("4999")),
        CostEstimate(cents=Decimal("200")),
    )
    assert "R$ 50,00" in (decisao.reason or "")


def test_an_unknown_cost_is_not_blocked_by_the_budget() -> None:
    """Barrar por um número que não existe deixaria a plataforma muda por
    falta de cadastro de preço — problema de configuração, não de orçamento."""
    decisao = check(
        BudgetLimits(is_enabled=True, monthly_cents=Decimal("100")),
        BudgetState(spent_month_cents=Decimal("99")),
        CostEstimate(cents=Decimal("0"), is_known=False),
    )
    assert decisao.allowed
