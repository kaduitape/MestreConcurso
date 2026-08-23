"""Schemas de autenticação."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=3, max_length=160)
    accepted_terms: bool = Field(description="Aceite dos Termos de Uso e Política de Privacidade")

    @field_validator("full_name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("accepted_terms")
    @classmethod
    def _require_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("É necessário aceitar os termos para criar a conta.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_label: str | None = Field(default=None, max_length=120)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Validade do access token em segundos")
    session_id: str


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=10)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class SessionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_id: str
    device_label: str | None
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    is_current: bool = False
