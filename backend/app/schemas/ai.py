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
    is_enabled: bool = False
    provider_slug: str | None = None
    model_slug: str | None = None
    temperature: Decimal | None = None
    max_output_tokens: int | None = None
    cache_ttl_hours: int | None = None


class AIFeatureBindingUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    provider_slug: str | None = None
    model_slug: str | None = None
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
