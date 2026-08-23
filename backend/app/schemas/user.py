"""Schemas de usuário e perfil."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    avatar_url: str | None = None
    phone: str | None = None
    birth_date: date | None = None
    city: str | None = None
    state: str | None = None
    timezone: str = "America/Sao_Paulo"
    locale: str = "pt-BR"
    theme: str = "system"
    study_goal: str | None = None
    bio: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    onboarding_completed_at: datetime | None = None


class ProfileUpdate(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    birth_date: date | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=10)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    study_goal: str | None = Field(default=None, max_length=255)
    bio: str | None = Field(default=None, max_length=500)
    preferences: dict[str, Any] | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=3, max_length=160)


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    email: EmailStr
    full_name: str
    status: str
    is_superuser: bool
    email_verified_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    roles: list[RoleSummary] = Field(default_factory=list)


class MeRead(UserRead):
    profile: ProfileRead | None = None
    permissions: list[str] = Field(default_factory=list)

    @classmethod
    def from_user(cls, user: Any) -> MeRead:
        data = cls.model_validate(user)
        data.permissions = sorted(user.permission_slugs)
        return data
