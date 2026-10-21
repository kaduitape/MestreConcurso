"""Roteador de modelos: qual modelo atende esta chamada, e por quê.

Até aqui a resposta era uma só — o modelo que o administrador vinculou à
funcionalidade no painel. Isso basta enquanto todas as chamadas de uma
funcionalidade são parecidas, e deixa de bastar quando não são: analisar um
edital de 8 páginas e um de 300 é a mesma funcionalidade e não é o mesmo
trabalho.

Três regras governam este módulo, e as três existem para que ele não vire uma
caixa preta:

*A decisão é determinística.* Nenhuma IA escolhe o modelo. A entrada é um
conjunto de sinais medidos mais um conjunto de regras cadastradas; a saída é
sempre a mesma para a mesma entrada. Pedir a um LLM para escolher o modelo
seria trocar uma pergunta auditável por um palpite caro.

*Sinal ausente não vale como falso.* Uma regra que depende do tamanho da
entrada, numa funcionalidade que não informa tamanho, fica **não avaliada** e
diz isso. O contrário — tratar ausência como zero — faria a condição "entrada
acima de 50 mil caracteres" parecer respondida quando ninguém mediu nada.

*Toda escolha carrega o rastro.* A saída não é só o modelo: é a regra que
venceu, as que não venceram e o motivo de cada uma. É o que permite responder
"por que este modelo foi usado nesta execução" sem garimpar log.

Todas as regras são avaliadas, inclusive as que vêm depois da vencedora. Custa
algumas comparações e evita um rastro cheio de "não cheguei a olhar".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

#: Teto de regras por funcionalidade. Não é limite de produto — é o que mantém
#: o rastro legível numa tela. Uma funcionalidade que precise de mais do que
#: isso está pedindo outra coisa, não mais regras.
MAX_RULES_PER_FEATURE = 20


class RouteReason(StrEnum):
    """Por que este modelo, nesta chamada."""

    #: Nenhuma regra se aplicou: valeu o vínculo configurado no painel.
    BINDING_DEFAULT = "BINDING_DEFAULT"
    #: Uma regra venceu, e o rastro diz qual.
    RULE_MATCHED = "RULE_MATCHED"
    #: O modelo escolhido falhou e o de reserva atendeu no lugar dele.
    FALLBACK_AFTER_ERROR = "FALLBACK_AFTER_ERROR"


class SignalKey(StrEnum):
    """Sinais sobre os quais uma regra pode decidir.

    A lista é curta de propósito: só entra aqui o que a plataforma **mede**.
    "Complexidade da pergunta" não está nesta lista porque ninguém a mede —
    estimá-la com IA seria devolver ao palpite a decisão que este módulo
    existe para tornar auditável.
    """

    #: Tamanho do texto que vai na requisição, em caracteres.
    INPUT_CHARS = "INPUT_CHARS"
    #: A chamada exige resposta em JSON.
    NEEDS_JSON = "NEEDS_JSON"
    #: Quanto do teto mensal de gasto já foi consumido, em porcentagem.
    BUDGET_USED_PCT = "BUDGET_USED_PCT"


SIGNAL_LABELS: dict[SignalKey, str] = {
    SignalKey.INPUT_CHARS: "tamanho da entrada",
    SignalKey.NEEDS_JSON: "exige resposta em JSON",
    SignalKey.BUDGET_USED_PCT: "percentual do teto mensal já gasto",
}


class RuleOutcome(StrEnum):
    """O que aconteceu com uma regra nesta avaliação."""

    MATCHED = "MATCHED"
    NOT_MATCHED = "NOT_MATCHED"
    #: Depende de um sinal que esta chamada não informou.
    NOT_EVALUATED = "NOT_EVALUATED"
    #: Cadastrada, mas desligada pelo administrador.
    DISABLED = "DISABLED"
    #: O modelo que ela aponta não está utilizável (sem modelo, modelo inativo
    #: ou provedor inativo). Não dá para aplicar uma regra que leva a lugar nenhum.
    UNUSABLE = "UNUSABLE"


@dataclass(frozen=True, slots=True)
class Signals:
    """O que esta chamada informou sobre si mesma.

    ``None`` em qualquer campo quer dizer "não informado" — nunca zero, nunca
    falso. Quem chama declara o que sabe; o que não sabe fica em branco e as
    regras que dependiam daquilo ficam não avaliadas.
    """

    input_chars: int | None = None
    needs_json: bool | None = None
    budget_used_pct: Decimal | None = None

    def known(self) -> tuple[SignalKey, ...]:
        presentes = []
        if self.input_chars is not None:
            presentes.append(SignalKey.INPUT_CHARS)
        if self.needs_json is not None:
            presentes.append(SignalKey.NEEDS_JSON)
        if self.budget_used_pct is not None:
            presentes.append(SignalKey.BUDGET_USED_PCT)
        return tuple(presentes)

    def as_dict(self) -> dict[str, object]:
        """Forma serializável, só com o que foi informado."""
        dados: dict[str, object] = {}
        if self.input_chars is not None:
            dados["input_chars"] = self.input_chars
        if self.needs_json is not None:
            dados["needs_json"] = self.needs_json
        if self.budget_used_pct is not None:
            dados["budget_used_pct"] = str(self.budget_used_pct)
        return dados


@dataclass(frozen=True, slots=True)
class Rule:
    """Uma regra cadastrada, já com o estado do modelo que ela aponta.

    ``model_is_usable`` é decidido fora daqui, por quem tem acesso ao banco: o
    domínio não sabe consultar provedor nem checar se está ativo. Chega pronto
    para que a decisão continue sendo uma função pura.
    """

    id: int
    label: str
    priority: int
    is_enabled: bool
    model_id: int | None = None
    model_slug: str | None = None
    provider_slug: str | None = None
    model_is_usable: bool = False
    min_input_chars: int | None = None
    max_input_chars: int | None = None
    requires_json: bool | None = None
    min_budget_used_pct: Decimal | None = None

    def has_conditions(self) -> bool:
        return any(
            valor is not None
            for valor in (
                self.min_input_chars,
                self.max_input_chars,
                self.requires_json,
                self.min_budget_used_pct,
            )
        )


@dataclass(frozen=True, slots=True)
class ConditionTrace:
    """Uma condição da regra, com o que se esperava e o que se observou."""

    signal: SignalKey
    description: str
    outcome: RuleOutcome
    observed: str | None = None


@dataclass(frozen=True, slots=True)
class RuleTrace:
    rule_id: int
    label: str
    priority: int
    outcome: RuleOutcome
    detail: str
    conditions: tuple[ConditionTrace, ...] = ()

    @property
    def missing_signals(self) -> tuple[SignalKey, ...]:
        return tuple(
            item.signal for item in self.conditions if item.outcome is RuleOutcome.NOT_EVALUATED
        )


@dataclass(frozen=True, slots=True)
class Decision:
    """O modelo escolhido e o rastro inteiro da escolha."""

    model_id: int | None
    model_slug: str | None
    provider_slug: str | None
    reason: RouteReason
    explanation: str
    signals: Signals = field(default_factory=Signals)
    rule_id: int | None = None
    rule_label: str | None = None
    trace: tuple[RuleTrace, ...] = ()


# --------------------------------------------------------------------------- #
# Formatação — o rastro é lido por pessoas
# --------------------------------------------------------------------------- #
def _milhar(valor: int) -> str:
    return f"{valor:,}".replace(",", ".")


def _pct(valor: Decimal) -> str:
    return f"{valor.quantize(Decimal('0.1'))}%".replace(".", ",")


# --------------------------------------------------------------------------- #
# Avaliação
# --------------------------------------------------------------------------- #
def _check_min_input(rule: Rule, signals: Signals) -> ConditionTrace | None:
    if rule.min_input_chars is None:
        return None
    descricao = f"entrada com {_milhar(rule.min_input_chars)} caracteres ou mais"
    if signals.input_chars is None:
        return ConditionTrace(SignalKey.INPUT_CHARS, descricao, RuleOutcome.NOT_EVALUATED)
    observado = f"{_milhar(signals.input_chars)} caracteres"
    atende = signals.input_chars >= rule.min_input_chars
    return ConditionTrace(
        SignalKey.INPUT_CHARS,
        descricao,
        RuleOutcome.MATCHED if atende else RuleOutcome.NOT_MATCHED,
        observado,
    )


def _check_max_input(rule: Rule, signals: Signals) -> ConditionTrace | None:
    if rule.max_input_chars is None:
        return None
    descricao = f"entrada com até {_milhar(rule.max_input_chars)} caracteres"
    if signals.input_chars is None:
        return ConditionTrace(SignalKey.INPUT_CHARS, descricao, RuleOutcome.NOT_EVALUATED)
    observado = f"{_milhar(signals.input_chars)} caracteres"
    atende = signals.input_chars <= rule.max_input_chars
    return ConditionTrace(
        SignalKey.INPUT_CHARS,
        descricao,
        RuleOutcome.MATCHED if atende else RuleOutcome.NOT_MATCHED,
        observado,
    )


def _check_json(rule: Rule, signals: Signals) -> ConditionTrace | None:
    if rule.requires_json is None:
        return None
    descricao = "chamada que exige JSON" if rule.requires_json else "chamada que não exige JSON"
    if signals.needs_json is None:
        return ConditionTrace(SignalKey.NEEDS_JSON, descricao, RuleOutcome.NOT_EVALUATED)
    observado = "exige JSON" if signals.needs_json else "não exige JSON"
    atende = signals.needs_json is rule.requires_json
    return ConditionTrace(
        SignalKey.NEEDS_JSON,
        descricao,
        RuleOutcome.MATCHED if atende else RuleOutcome.NOT_MATCHED,
        observado,
    )


def _check_budget(rule: Rule, signals: Signals) -> ConditionTrace | None:
    if rule.min_budget_used_pct is None:
        return None
    descricao = f"teto mensal com {_pct(rule.min_budget_used_pct)} ou mais já gastos"
    if signals.budget_used_pct is None:
        # Sem teto mensal cadastrado não existe "percentual do teto": o sinal
        # não é zero, é inexistente. A regra fica não avaliada e o rastro diz.
        return ConditionTrace(SignalKey.BUDGET_USED_PCT, descricao, RuleOutcome.NOT_EVALUATED)
    observado = _pct(signals.budget_used_pct)
    atende = signals.budget_used_pct >= rule.min_budget_used_pct
    return ConditionTrace(
        SignalKey.BUDGET_USED_PCT,
        descricao,
        RuleOutcome.MATCHED if atende else RuleOutcome.NOT_MATCHED,
        observado,
    )


_CHECKS = (_check_min_input, _check_max_input, _check_json, _check_budget)


def evaluate(rule: Rule, signals: Signals) -> RuleTrace:
    """Resultado de uma regra isolada, com uma linha por condição."""
    if not rule.is_enabled:
        return RuleTrace(
            rule.id, rule.label, rule.priority, RuleOutcome.DISABLED, "regra desligada"
        )
    if rule.model_id is None or not rule.model_is_usable:
        return RuleTrace(
            rule.id,
            rule.label,
            rule.priority,
            RuleOutcome.UNUSABLE,
            "o modelo desta regra não está disponível (sem modelo, modelo inativo "
            "ou provedor inativo)",
        )

    condicoes = tuple(
        trace for trace in (check(rule, signals) for check in _CHECKS) if trace is not None
    )
    if not condicoes:
        return RuleTrace(
            rule.id,
            rule.label,
            rule.priority,
            RuleOutcome.MATCHED,
            "sem condição cadastrada: vale para toda chamada da funcionalidade",
        )

    ausentes = [item for item in condicoes if item.outcome is RuleOutcome.NOT_EVALUATED]
    if ausentes:
        nomes = ", ".join(SIGNAL_LABELS[item.signal] for item in ausentes)
        return RuleTrace(
            rule.id,
            rule.label,
            rule.priority,
            RuleOutcome.NOT_EVALUATED,
            f"esta chamada não informou: {nomes}",
            condicoes,
        )

    nao_atende = [item for item in condicoes if item.outcome is RuleOutcome.NOT_MATCHED]
    if nao_atende:
        return RuleTrace(
            rule.id,
            rule.label,
            rule.priority,
            RuleOutcome.NOT_MATCHED,
            "; ".join(f"{item.description} — observado: {item.observed}" for item in nao_atende),
            condicoes,
        )

    return RuleTrace(
        rule.id,
        rule.label,
        rule.priority,
        RuleOutcome.MATCHED,
        "; ".join(f"{item.description} — observado: {item.observed}" for item in condicoes),
        condicoes,
    )


def choose(
    rules: list[Rule] | tuple[Rule, ...],
    signals: Signals,
    *,
    default_model_id: int | None,
    default_model_slug: str | None,
    default_provider_slug: str | None,
) -> Decision:
    """Escolhe o modelo da chamada e devolve a decisão com o rastro completo.

    A primeira regra que atende, na ordem de prioridade, vence. As demais
    continuam sendo avaliadas: um rastro que diz "não cheguei a olhar" não
    responde por que o modelo foi aquele.
    """
    ordenadas = sorted(rules, key=lambda item: (item.priority, item.id))
    rastro = tuple(evaluate(rule, signals) for rule in ordenadas)

    vencedora: Rule | None = None
    vencedora_trace: RuleTrace | None = None
    for rule, trace in zip(ordenadas, rastro, strict=True):
        if trace.outcome is RuleOutcome.MATCHED:
            vencedora, vencedora_trace = rule, trace
            break

    if vencedora is not None and vencedora_trace is not None:
        return Decision(
            model_id=vencedora.model_id,
            model_slug=vencedora.model_slug,
            provider_slug=vencedora.provider_slug,
            reason=RouteReason.RULE_MATCHED,
            explanation=f'regra "{vencedora.label}": {vencedora_trace.detail}',
            signals=signals,
            rule_id=vencedora.id,
            rule_label=vencedora.label,
            trace=rastro,
        )

    if ordenadas:
        explicacao = "nenhuma regra se aplicou: valeu o modelo vinculado à funcionalidade"
    else:
        explicacao = "nenhuma regra cadastrada: valeu o modelo vinculado à funcionalidade"
    return Decision(
        model_id=default_model_id,
        model_slug=default_model_slug,
        provider_slug=default_provider_slug,
        reason=RouteReason.BINDING_DEFAULT,
        explanation=explicacao,
        signals=signals,
        trace=rastro,
    )


def after_error(
    *,
    failed_model_slug: str,
    error_code: str,
    model_id: int | None,
    model_slug: str | None,
    provider_slug: str | None,
    signals: Signals | None = None,
) -> Decision:
    """Decisão de reserva: o modelo escolhido falhou e outro atendeu.

    Fica registrada como decisão própria, e não como detalhe da primeira. Duas
    chamadas aconteceram, cada uma com seu custo — somar as duas sob um único
    registro esconderia uma delas.
    """
    return Decision(
        model_id=model_id,
        model_slug=model_slug,
        provider_slug=provider_slug,
        reason=RouteReason.FALLBACK_AFTER_ERROR,
        explanation=(
            f"o modelo {failed_model_slug} falhou ({error_code}) e o modelo de reserva "
            "atendeu no lugar dele"
        ),
        signals=signals or Signals(),
    )


def budget_used_pct(spent_cents: Decimal, monthly_limit_cents: Decimal) -> Decimal | None:
    """Percentual do teto mensal já gasto, ou ``None`` quando não há teto.

    Sem teto não existe percentual de teto. Devolver zero aqui faria uma regra
    de pressão de orçamento parecer avaliada numa instalação que nunca definiu
    limite nenhum.
    """
    if monthly_limit_cents <= 0:
        return None
    return (spent_cents / monthly_limit_cents * Decimal("100")).quantize(Decimal("0.01"))
