"""Schemas utilitários compartilhados."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str
    detail: dict[str, Any] | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, bool]
