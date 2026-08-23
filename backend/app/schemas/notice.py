"""Schemas de editais."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

_READ = ConfigDict(from_attributes=True)


class NoticeFileRead(BaseModel):
    model_config = _READ

    public_id: str
    original_name: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    page_count: int | None = None
    status: str
    error_message: str | None = None
    created_at: datetime


class NoticeRead(BaseModel):
    model_config = _READ

    public_id: str
    title: str
    kind: str
    number: str | None = None
    published_at: datetime | None = None
    source_url: str | None = None
    status: str
    summary: str | None = None
    created_at: datetime
    files: list[NoticeFileRead] = Field(default_factory=list)


class NoticeCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    competition_public_id: str | None = None
    kind: str = Field(default="MAIN", pattern="^(MAIN|RECTIFICATION|ADDENDUM|RESULT)$")
    number: str | None = Field(default=None, max_length=60)
    published_at: datetime | None = None
    source_url: str | None = Field(default=None, max_length=500)
    summary: str | None = None


class NoticeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    kind: str | None = Field(default=None, pattern="^(MAIN|RECTIFICATION|ADDENDUM|RESULT)$")
    number: str | None = Field(default=None, max_length=60)
    published_at: datetime | None = None
    source_url: str | None = Field(default=None, max_length=500)
    summary: str | None = None
