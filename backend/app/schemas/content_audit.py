"""Contratos do auditor de conteúdo."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditFindingRead(BaseModel):
    """Uma marca do laudo. ``NOT_CHECKED`` é o que não deu para conferir."""

    rule: str
    severity: str
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ContentAuditRead(BaseModel):
    public_id: str
    target_kind: str
    target_public_id: str
    verdict: str
    trigger: str
    blocked_publication: bool
    findings: list[AuditFindingRead] = Field(default_factory=list)
    #: Contagens e o **alcance** da conferência — quantas questões entraram na
    #: comparação de duplicata e quantos tópicos o edital trouxe.
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AuditRuleRead(BaseModel):
    key: str
    label: str
    description: str
    applies_to: list[str] = Field(default_factory=list)
    #: O padrão que o código traz; a configuração do painel vence.
    default_severity: str
    severity: str
    is_enabled: bool
    config: dict[str, Any] = Field(default_factory=dict)


class AuditRuleUpdate(BaseModel):
    is_enabled: bool = True
    severity: str = "BLOCKER"
    config: dict[str, Any] | None = None


class AuditRunRequest(BaseModel):
    target_kind: str
    target_public_id: str
