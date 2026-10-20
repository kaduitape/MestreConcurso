"""Custo de IA: quanto foi gasto e quando parar.

Este módulo existe porque a plataforma vai começar a gerar conteúdo em massa.
Gerar aula, mapa, flashcard e questão para todas as disciplinas de um edital é
um volume de token que ninguém mediu — e, até agora, **nada media**: a tabela
``ai_usage`` existia e nenhum código escrevia nela, então o painel de custo
reportava zero desde sempre.

Três regras governam o que está aqui:

*Preço que não existe não vira zero em silêncio.* Quando o modelo não tem
preço cadastrado, o custo é desconhecido — não é grátis. O cálculo devolve isso
explicitamente, e quem decide o corte sabe que está olhando um número
incompleto. Tratar desconhecido como zero faria o teto parecer respeitado
enquanto a fatura cresce.

*O teto corta antes de gastar, não depois.* A verificação acontece antes da
chamada. Depois já foi.

*Os limites não são do código.* Eles vêm do banco e são editáveis no painel.

O módulo é puro: sem I/O, sem banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

#: Centavos. Toda a contabilidade é em centavos para não arrastar float.
CENTS = Decimal("0.000001")

#: Quando o teto está desligado, não há corte — mas a medição continua.
UNLIMITED = Decimal("0")


class BudgetVerdict(StrEnum):
    ALLOWED = "ALLOWED"
    #: Estouraria o teto da execução em curso.
    RUN_EXCEEDED = "RUN_EXCEEDED"
    #: Estouraria o teto do mês.
    MONTH_EXCEEDED = "MONTH_EXCEEDED"


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Quanto custou (ou custaria) uma chamada.

    ``is_known`` é parte da resposta, não um detalhe: um custo desconhecido
    somado como zero corromperia o total do mês.
    """

    cents: Decimal = Decimal("0")
    is_known: bool = True

    def __add__(self, other: CostEstimate) -> CostEstimate:
        return CostEstimate(
            cents=self.cents + other.cents,
            # Desconhecido contamina a soma: o total deixa de ser confiável.
            is_known=self.is_known and other.is_known,
        )


def cost_of(
    *,
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1k: Decimal | None,
    output_cost_per_1k: Decimal | None,
) -> CostEstimate:
    """Custo de uma chamada, em centavos.

    Preço ausente **em qualquer um dos lados** torna o total desconhecido. Não
    adianta contar só a entrada: o resultado seria um número menor que o real,
    e um número menor que o real é pior que nenhum número.
    """
    if input_cost_per_1k is None or output_cost_per_1k is None:
        return CostEstimate(cents=Decimal("0"), is_known=False)

    entrada = (Decimal(max(0, input_tokens)) / Decimal(1000)) * input_cost_per_1k
    saida = (Decimal(max(0, output_tokens)) / Decimal(1000)) * output_cost_per_1k
    total = (entrada + saida).quantize(CENTS, rounding=ROUND_HALF_UP)
    return CostEstimate(cents=total, is_known=True)


@dataclass(frozen=True, slots=True)
class BudgetLimits:
    """Os tetos, como vieram do banco. Zero quer dizer "sem teto"."""

    monthly_cents: Decimal = UNLIMITED
    per_run_cents: Decimal = UNLIMITED
    is_enabled: bool = False

    @property
    def has_monthly(self) -> bool:
        return self.is_enabled and self.monthly_cents > UNLIMITED

    @property
    def has_per_run(self) -> bool:
        return self.is_enabled and self.per_run_cents > UNLIMITED


@dataclass(frozen=True, slots=True)
class BudgetState:
    """Quanto já foi gasto, do mês e da execução em curso."""

    spent_month_cents: Decimal = Decimal("0")
    spent_run_cents: Decimal = Decimal("0")
    #: Falso quando algum gasto do período veio de modelo sem preço cadastrado.
    is_complete: bool = True


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    verdict: str
    reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.verdict == BudgetVerdict.ALLOWED


def _money(cents: Decimal) -> str:
    return f"R$ {cents / 100:.2f}".replace(".", ",")


def check(
    limits: BudgetLimits,
    state: BudgetState,
    projected: CostEstimate,
) -> BudgetDecision:
    """Decide se a próxima chamada pode acontecer.

    Chamada de custo **desconhecido** não é barrada: barrar por um número que
    não existe deixaria a plataforma muda por falta de cadastro de preço, o que
    é problema de configuração e não de orçamento. O que ela faz é marcar o
    total como incompleto, e disso o painel avisa.
    """
    if not limits.is_enabled:
        return BudgetDecision(verdict=BudgetVerdict.ALLOWED)

    if limits.has_per_run:
        depois = state.spent_run_cents + projected.cents
        if depois > limits.per_run_cents:
            return BudgetDecision(
                verdict=BudgetVerdict.RUN_EXCEEDED,
                reason=(
                    f"Esta execução chegaria a {_money(depois)} e o teto por execução é "
                    f"{_money(limits.per_run_cents)}."
                ),
            )

    if limits.has_monthly:
        depois = state.spent_month_cents + projected.cents
        if depois > limits.monthly_cents:
            return BudgetDecision(
                verdict=BudgetVerdict.MONTH_EXCEEDED,
                reason=(
                    f"O mês chegaria a {_money(depois)} e o teto mensal é "
                    f"{_money(limits.monthly_cents)}."
                ),
            )

    return BudgetDecision(verdict=BudgetVerdict.ALLOWED)
