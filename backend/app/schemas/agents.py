"""Contratos do orquestrador de agentes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AgentAttemptRead(BaseModel):
    """Uma tentativa do passo, com o que aconteceu nela.

    A tela precisa das duas quando um passo falha duas vezes por motivos
    diferentes: o detalhe do passo guarda só a última. A pilha de erro **não**
    vem para cá — ela fica no servidor.
    """

    number: int
    status: str
    detail: str | None = None
    error_code: str | None = None
    request_id: str | None = None
    duration_ms: int | None = None
    cost_cents: Decimal = Decimal("0")
    provider: str | None = None
    model_slug: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AgentStepRead(BaseModel):
    """Um agente dentro de uma execução, como a tela precisa ver."""

    key: str
    label: str
    description: str
    status: str
    #: O estado em português, para a tela não ter de traduzir chave por chave.
    status_label: str = ""
    depends_on: list[str] = Field(default_factory=list)
    attempts: int = 0
    max_attempts: int = 1
    #: O que aconteceu, em português. Obrigatório quando o passo não concluiu.
    detail: str | None = None
    #: Falso quando o agente está declarado mas ainda não existe.
    is_implemented: bool = True
    #: ``True`` quando não cabe mais tentativa automática. É derivado — a causa
    #: da última falha continua em ``detail``, não é substituída por isto.
    attempts_exhausted: bool = False
    #: O que a tela deve oferecer para destravar: anexar PDF, configurar
    #: provedor, elevar o teto, tentar de novo.
    action: str | None = None
    #: O que ficou de fora apesar de o passo ter cumprido o contrato.
    notes: list[str] = Field(default_factory=list)
    #: O histórico, uma linha por tentativa.
    attempts_history: list[AgentAttemptRead] = Field(default_factory=list)


class AgentRunRead(BaseModel):
    public_id: str
    competition_public_id: str | None = None
    status: str
    error: str | None = None
    cost_cents: Decimal = Decimal("0")
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    steps: list[AgentStepRead] = Field(default_factory=list)


class AgentRunCreate(BaseModel):
    competition_public_id: str = Field(min_length=1)


class PrecheckRead(BaseModel):
    """Uma conferência de pré-requisito, com a ação que resolve a pendência."""

    key: str
    label: str
    ok: bool
    detail: str | None = None
    action: str | None = None
    resource_id: str | None = None


class PreflightRead(BaseModel):
    """O que falta antes de disparar os oito agentes.

    Existe para a pessoa descobrir que o edital não tem PDF **antes** de ver
    sete passos bloqueados em cascata.
    """

    ready: bool
    checks: list[PrecheckRead] = Field(default_factory=list)


class AgentCatalogRead(BaseModel):
    """O catálogo, para o painel explicar o que cada agente faz."""

    key: str
    label: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    is_implemented: bool = True
    pending_reason: str | None = None


class AgentLayersRead(BaseModel):
    """As camadas que podem rodar em paralelo."""

    layers: list[list[str]] = Field(default_factory=list)
    agents: list[AgentCatalogRead] = Field(default_factory=list)


class AgentStepResult(BaseModel):
    result: dict[str, Any] = Field(default_factory=dict)
