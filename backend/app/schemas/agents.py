"""Contratos do orquestrador de agentes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AgentStepRead(BaseModel):
    """Um agente dentro de uma execução, como a tela precisa ver."""

    key: str
    label: str
    description: str
    status: str
    depends_on: list[str] = Field(default_factory=list)
    attempts: int = 0
    max_attempts: int = 1
    #: O que aconteceu, em português. Obrigatório quando o passo foi pulado.
    detail: str | None = None
    #: Falso quando o agente está declarado mas ainda não existe.
    is_implemented: bool = True


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
