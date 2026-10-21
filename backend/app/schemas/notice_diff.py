"""Contratos da retificação de edital."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NoticeChangeRead(BaseModel):
    scope: str
    kind: str
    label: str
    before: str | None = None
    after: str | None = None
    detail: str = ""
    topic_id: int | None = None
    subject_id: int | None = None
    #: Procedência do dado novo — a tela mostra conferido e deduzido diferente.
    evidence_level: str | None = None


class NoticeImpactRead(BaseModel):
    action: str
    topic_label: str
    topic_id: int | None = None
    reason: str
    content: dict[str, Any] | None = None


class NoticeDiffRead(BaseModel):
    public_id: str
    competition_public_id: str | None = None
    from_notice_title: str
    to_notice_title: str
    changes: list[NoticeChangeRead] = Field(default_factory=list)
    impacts: list[NoticeImpactRead] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    reviewed_at: datetime | None = None
    created_at: datetime


class NoticeDiffCreate(BaseModel):
    competition_public_id: str
    #: Deixe os dois vazios para comparar as duas versões analisadas mais recentes.
    from_notice_public_id: str | None = None
    to_notice_public_id: str | None = None
