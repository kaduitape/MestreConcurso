"""Schemas da configuração de IA."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# Os campos começam com "model_"; desativamos o namespace protegido do Pydantic.
_CONFIG = ConfigDict(from_attributes=True, protected_namespaces=())


class AIModelRead(BaseModel):
    model_config = _CONFIG

    slug: str
    display_name: str
    kind: str
    context_window: int | None = None
    max_output_tokens: int | None = None
    input_cost_per_1k: Decimal | None = None
    output_cost_per_1k: Decimal | None = None
    supports_tools: bool = False
    supports_json: bool = False
    is_active: bool = True


class AIProviderRead(BaseModel):
    model_config = _CONFIG

    slug: str
    display_name: str
    base_url: str | None = None
    organization: str | None = None
    is_active: bool
    has_api_key: bool
    api_key_hint: str | None = None
    api_key_set_at: datetime | None = None
    last_tested_at: datetime | None = None
    last_test_status: str | None = None
    last_test_message: str | None = None
    models: list[AIModelRead] = Field(default_factory=list)


class AIProviderCreate(BaseModel):
    slug: str = Field(description="Identificador do adaptador (ex.: openai)")
    display_name: str | None = Field(default=None, max_length=80)
    base_url: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=120)


class AIProviderUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=80)
    base_url: str | None = Field(default=None, max_length=255)
    organization: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class AIProviderKeyInput(BaseModel):
    api_key: str = Field(
        min_length=20,
        max_length=500,
        description="Chave de API do provedor. É gravada cifrada e nunca é devolvida.",
    )


class AIModelUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    is_active: bool | None = None
    input_cost_per_1k: Decimal | None = Field(default=None, ge=0)
    output_cost_per_1k: Decimal | None = Field(default=None, ge=0)


class ConnectionCheckRead(BaseModel):
    ok: bool
    message: str
    latency_ms: int
    models_available: int
    sample_models: list[str] = Field(default_factory=list)


class AIFeatureBindingRead(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    feature: str
    label: str
    description: str
    kind: str = "chat"
    #: Falso para embedding e voz, que não aceitam regra de roteamento.
    is_routable: bool = True
    is_enabled: bool = False
    provider_slug: str | None = None
    model_slug: str | None = None
    #: Modelo que atende quando o principal devolve limite de requisições ou
    #: indisponibilidade. Vazio = sem reserva, e o erro sobe.
    fallback_provider_slug: str | None = None
    fallback_model_slug: str | None = None
    fallback_is_usable: bool = False
    temperature: Decimal | None = None
    max_output_tokens: int | None = None
    cache_ttl_hours: int | None = None


class AIFeatureBindingUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_slug: str | None = None
    model_slug: str | None = None
    fallback_provider_slug: str | None = None
    fallback_model_slug: str | None = None
    is_enabled: bool = False
    temperature: Decimal | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, ge=64, le=32_000)
    cache_ttl_hours: int | None = Field(
        default=None, ge=1, le=8760, description="Validade do cache; vazio = permanente"
    )


class AICacheStatsRead(BaseModel):
    entries: int
    total_hits: int
    tokens_stored: int
    tokens_saved: int
    cost_saved_cents: Decimal
    expired_entries: int


class AIAvailableProviders(BaseModel):
    """Adaptadores implementados e ainda não cadastrados."""

    available: list[str]
    configured: list[str]


class AIBudgetRead(BaseModel):
    """Teto de gasto e o que já foi consumido no mês."""

    is_enabled: bool = False
    monthly_limit_cents: Decimal = Decimal("0")
    per_run_limit_cents: Decimal = Decimal("0")
    spent_month_cents: Decimal = Decimal("0")
    calls_month: int = 0
    #: Falso quando algum modelo usado no mês não tem preço cadastrado.
    is_complete: bool = True
    #: Quais modelos — é o que permite consertar o cadastro.
    models_without_price: list[str] = Field(default_factory=list)


class AIBudgetUpdate(BaseModel):
    is_enabled: bool = False
    #: Zero quer dizer "sem teto para este".
    monthly_limit_cents: Decimal = Field(default=Decimal("0"), ge=0)
    per_run_limit_cents: Decimal = Field(default=Decimal("0"), ge=0)


# --------------------------------------------------------------------------- #
# Roteador de modelos (Fase 6)
# --------------------------------------------------------------------------- #
class AIModelRouteRead(BaseModel):
    """Uma regra de roteamento como ela está cadastrada."""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    feature: str
    feature_label: str
    label: str
    priority: int
    is_enabled: bool
    provider_slug: str | None = None
    model_slug: str | None = None
    #: Falso quando o modelo da regra não está utilizável — e a regra, por
    #: isso, nunca se aplica. A tela precisa dizer isso em vez de mostrar uma
    #: regra ligada que não faz nada.
    model_is_usable: bool = False
    min_input_chars: int | None = None
    max_input_chars: int | None = None
    requires_json: bool | None = None
    min_budget_used_pct: Decimal | None = None
    #: Sinais de que esta regra depende; vazio quando ela vale sempre.
    required_signals: list[str] = Field(default_factory=list)


class AIModelRouteCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    feature: str
    label: str = Field(min_length=3, max_length=120)
    priority: int = Field(default=100, ge=0, le=1000)
    is_enabled: bool = False
    provider_slug: str
    model_slug: str
    min_input_chars: int | None = Field(default=None, ge=0, le=10_000_000)
    max_input_chars: int | None = Field(default=None, ge=0, le=10_000_000)
    requires_json: bool | None = None
    min_budget_used_pct: Decimal | None = Field(default=None, ge=0, le=999)


class AIModelRouteUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    label: str | None = Field(default=None, min_length=3, max_length=120)
    priority: int | None = Field(default=None, ge=0, le=1000)
    is_enabled: bool | None = None
    provider_slug: str | None = None
    model_slug: str | None = None
    min_input_chars: int | None = Field(default=None, ge=0, le=10_000_000)
    max_input_chars: int | None = Field(default=None, ge=0, le=10_000_000)
    requires_json: bool | None = None
    min_budget_used_pct: Decimal | None = Field(default=None, ge=0, le=999)
    #: Limpa todas as condições antes de aplicar as informadas. Sem este campo,
    #: um ``null`` no corpo seria indistinguível de "não quis mexer nesta".
    clear_conditions: bool = False


class AIRouteConditionTrace(BaseModel):
    signal: str
    description: str
    outcome: str
    observed: str | None = None


class AIRouteRuleTrace(BaseModel):
    rule_id: int
    label: str
    priority: int
    outcome: str
    detail: str
    missing_signals: list[str] = Field(default_factory=list)
    conditions: list[AIRouteConditionTrace] = Field(default_factory=list)


class AIRoutingDecisionRead(BaseModel):
    """Por que este modelo foi usado nesta execução."""

    model_config = ConfigDict(protected_namespaces=())

    id: int
    feature: str
    feature_label: str
    model_slug: str
    provider_slug: str
    reason: str
    route_id: int | None = None
    route_label: str | None = None
    explanation: str
    #: Só o que a chamada informou de verdade.
    signals: dict[str, object] = Field(default_factory=dict)
    trace: list[AIRouteRuleTrace] = Field(default_factory=list)
    created_at: datetime
