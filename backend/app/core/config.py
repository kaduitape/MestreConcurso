"""Configuração da aplicação (12-factor, tipada e validada)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production", "test"]

# Senha apenas para bootstrap local; produção rejeita este valor (ver validador abaixo).
_DEFAULT_BOOTSTRAP_PASSWORD = "Admin@Mestre123"


def _split_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return value
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    """Todas as opções vêm de variáveis de ambiente — nada hardcoded."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Aplicação ---------------------------------------------------------
    app_name: str = "Concurso Mestre IA"
    environment: Environment = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: Annotated[list[str], Field(default_factory=lambda: ["http://localhost:5173"])]
    allowed_hosts: Annotated[list[str], Field(default_factory=lambda: ["*"])]

    # --- Segurança ---------------------------------------------------------
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    email_verification_expire_hours: int = 48
    password_reset_expire_minutes: int = 60
    password_min_length: int = 10
    max_login_attempts: int = 8
    login_lockout_minutes: int = 15
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4

    # --- Banco -------------------------------------------------------------
    mysql_host: str = "mysql"
    mysql_port: int = 3306
    mysql_database: str = "mestre_concurso"
    mysql_user: str = "mestre"
    mysql_password: str = ""
    database_url: str | None = None
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle: int = 1800
    db_echo: bool = False

    # --- Redis / Celery ----------------------------------------------------
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    cache_default_ttl: int = 300

    # --- Rate limit --------------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_default: str = "120/minute"
    rate_limit_auth: str = "10/minute"
    rate_limit_password_reset: str = "5/hour"

    # --- E-mail ------------------------------------------------------------
    email_backend: Literal["console", "smtp"] = "console"
    email_from: str = "Concurso Mestre IA <nao-responda@mestreconcurso.com.br>"
    smtp_host: str = "mailhog"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    smtp_ssl: bool = False

    # --- Observabilidade ---------------------------------------------------
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    metrics_enabled: bool = False

    # --- Uploads / armazenamento ------------------------------------------
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "/var/lib/mestre/uploads"
    max_upload_size_mb: int = 30
    max_pdf_pages: int = 400

    # --- Bootstrap ---------------------------------------------------------
    bootstrap_admin_email: EmailStr = "admin@mestreconcurso.com.br"
    bootstrap_admin_password: str = _DEFAULT_BOOTSTRAP_PASSWORD
    bootstrap_admin_name: str = "Administrador"

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def _parse_lists(cls, value: str | list[str]) -> list[str]:
        return _split_csv(value)

    @model_validator(mode="after")
    def _validate_production(self) -> Settings:
        if self.environment == "production":
            weak = len(self.secret_key) < 32 or "troque" in self.secret_key.lower()
            if weak:
                raise ValueError("SECRET_KEY inválida ou padrão em ambiente de produção.")
            if "*" in self.allowed_hosts:
                raise ValueError("ALLOWED_HOSTS não pode conter '*' em produção.")
            if self.debug:
                raise ValueError("DEBUG deve ser false em produção.")
            if self.bootstrap_admin_password == _DEFAULT_BOOTSTRAP_PASSWORD:
                raise ValueError("BOOTSTRAP_ADMIN_PASSWORD precisa ser alterada em produção.")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def sqlalchemy_url(self) -> str:
        """URL async do SQLAlchemy (permite override completo por DATABASE_URL)."""
        if self.database_url:
            return self.database_url
        return (
            f"mysql+asyncmy://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def alembic_url(self) -> str:
        """URL síncrona usada pelo Alembic."""
        return self.sqlalchemy_url.replace("+asyncmy", "+pymysql").replace("+aiosqlite", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
