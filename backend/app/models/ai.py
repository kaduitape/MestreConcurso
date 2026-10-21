"""Configuração de IA: provedores, modelos, vínculos por funcionalidade e cache.

Nada aqui é hardcoded: o administrador cadastra o provedor (ex.: OpenAI/ChatGPT),
informa a chave — guardada cifrada — e escolhe qual modelo atende cada
funcionalidade. O cache persistente evita pagar duas vezes pela mesma resposta.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JsonType, LongText, Sha256Hex


class AIProviderSlug(StrEnum):
    """Provedores com adaptador implementado."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    AISA = "aisa"


class AIFeature(StrEnum):
    """Funcionalidades que consomem IA. O modelo de cada uma é escolhido no painel."""

    NOTICE_EXTRACTION = "notice.extraction"
    QUESTION_CLASSIFY = "question.classify"
    ERROR_CLASSIFY = "error.classify"
    BOARD_PROFILE = "board.profile"
    CHAT_TUTOR = "chat.tutor"
    FLASHCARD_GENERATION = "flashcard.generation"
    EMBEDDINGS = "embeddings.default"
    RERANK = "rerank.default"
    TRAINING_SCRIPT = "training.script"
    TRAINING_NARRATION = "training.narration"
    MINDMAP_GENERATION = "mindmap.generation"


class AIProviderConfig(IdMixin, TimestampMixin, Base):
    """Credenciais e endpoint de um provedor de LLM."""

    __tablename__ = "ai_providers"
    __table_args__ = (UniqueConstraint("slug", name="uq_ai_providers_slug"),)

    slug: Mapped[str] = mapped_column(String(40), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    base_url: Mapped[str | None] = mapped_column(String(255))
    organization: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)

    # A chave nunca sai da API: guardamos o texto cifrado e apenas uma dica visual.
    api_key_encrypted: Mapped[str | None] = mapped_column(LongText)
    api_key_hint: Mapped[str | None] = mapped_column(String(32))
    api_key_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    api_key_set_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )

    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_status: Mapped[str | None] = mapped_column(String(20))
    last_test_message: Mapped[str | None] = mapped_column(String(255))
    settings: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    models: Mapped[list[AIModel]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_encrypted)


class AIModel(IdMixin, TimestampMixin, Base):
    """Modelo disponível em um provedor, com preço para cálculo de custo."""

    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("provider_id", "slug", name="uq_ai_models_provider_id_slug"),
        Index("ix_ai_models_provider_id_is_active", "provider_id", "is_active"),
    )

    provider_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ai_providers.id", ondelete="CASCADE")
    )
    slug: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="chat")  # chat | embedding | rerank
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    input_cost_per_1k: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    output_cost_per_1k: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_json: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    provider: Mapped[AIProviderConfig] = relationship(back_populates="models")


class AIFeatureBinding(IdMixin, TimestampMixin, Base):
    """Qual modelo atende cada funcionalidade, com fallback opcional."""

    __tablename__ = "ai_feature_bindings"
    __table_args__ = (UniqueConstraint("feature", name="uq_ai_feature_bindings_feature"),)

    feature: Mapped[str] = mapped_column(String(60), index=True)
    model_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    fallback_model_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.20"))
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_ttl_hours: Mapped[int | None] = mapped_column(Integer)
    #: Parâmetros que só algumas funcionalidades têm — a voz da narração, por
    #: exemplo. JSON genérico em vez de uma coluna por capricho de uma feature.
    options: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    model: Mapped[AIModel | None] = relationship(foreign_keys=[model_id], lazy="selectin")
    fallback_model: Mapped[AIModel | None] = relationship(
        foreign_keys=[fallback_model_id], lazy="selectin"
    )


class AICacheEntry(IdMixin, Base):
    """Resposta de IA guardada por impressão digital da requisição.

    Enquanto a entrada existir e não expirar, a mesma pergunta não gasta tokens
    novamente — é a regra que impede recomputar o perfil de uma banca a cada acesso.
    """

    __tablename__ = "ai_cache_entries"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_ai_cache_entries_fingerprint"),
        Index("ix_ai_cache_entries_feature_created_at", "feature", "created_at"),
        Index("ix_ai_cache_entries_expires_at", "expires_at"),
    )

    fingerprint: Mapped[str] = mapped_column(Sha256Hex)
    feature: Mapped[str] = mapped_column(String(60), index=True)
    provider_slug: Mapped[str] = mapped_column(String(40))
    model_slug: Mapped[str] = mapped_column(String(120))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIBudget(IdMixin, TimestampMixin, Base):
    """Teto de gasto com IA. **Não mora no código** — mora aqui e é editável.

    Zero em um limite quer dizer "sem teto para este". ``is_enabled`` desligado
    não interrompe a medição: continuar medindo com o corte desligado é o que
    permite descobrir qual teto faz sentido antes de ligá-lo.
    """

    __tablename__ = "ai_budgets"
    __table_args__ = (UniqueConstraint("scope", name="uq_ai_budgets_scope"),)

    scope: Mapped[str] = mapped_column(String(40), default="GLOBAL")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    monthly_limit_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    per_run_limit_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))


class AIUsage(IdMixin, Base):
    """Consumo real de tokens — base para custo, limites e auditoria."""

    __tablename__ = "ai_usage"
    __table_args__ = (
        Index("ix_ai_usage_feature_created_at", "feature", "created_at"),
        Index("ix_ai_usage_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    feature: Mapped[str] = mapped_column(String(60))
    provider_slug: Mapped[str] = mapped_column(String(40))
    model_slug: Mapped[str] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    error_code: Mapped[str | None] = mapped_column(String(60))
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Qual decisão de roteamento escolheu este modelo. É o que liga o gasto à
    #: explicação: sem esta coluna, "por que este modelo?" só se responde por
    #: aproximação de horário.
    routing_decision_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_routing_decisions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AIModelRoute(IdMixin, TimestampMixin, Base):
    """Regra de roteamento de modelo. **Não mora no código** — mora aqui.

    Trocar "edital acima de 80 mil caracteres usa o modelo grande" é um
    ``UPDATE``, não um deploy. As condições são colunas, e não um JSON de
    expressão, porque uma condição que o banco sabe ler é uma condição que a
    tela sabe mostrar e o teste sabe conferir — e porque uma linguagem de
    expressão guardada em texto é uma caixa preta com passo extra.

    Condição nula quer dizer "não condiciona por isto". Regra sem nenhuma
    condição vale para toda chamada da funcionalidade, e o rastro diz isso em
    texto em vez de deixar a pessoa deduzir.
    """

    __tablename__ = "ai_model_routes"
    __table_args__ = (Index("ix_ai_model_routes_feature_priority", "feature", "priority"),)

    feature: Mapped[str] = mapped_column(String(60), index=True)
    label: Mapped[str] = mapped_column(String(120))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    model_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_models.id", ondelete="SET NULL")
    )

    #: Condições. Todas as preenchidas precisam valer ao mesmo tempo.
    min_input_chars: Mapped[int | None] = mapped_column(Integer)
    max_input_chars: Mapped[int | None] = mapped_column(Integer)
    requires_json: Mapped[bool | None] = mapped_column(Boolean)
    min_budget_used_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    model: Mapped[AIModel | None] = relationship(lazy="selectin")


class AIRoutingDecision(IdMixin, Base):
    """Por que este modelo foi usado nesta execução.

    Uma linha por resolução de funcionalidade. ``model_slug`` e
    ``provider_slug`` são texto, além da chave estrangeira: o registro precisa
    continuar legível depois que alguém apagar o modelo do cadastro, e um
    histórico que vira ``NULL`` não explica nada.
    """

    __tablename__ = "ai_routing_decisions"
    __table_args__ = (Index("ix_ai_routing_decisions_feature_created_at", "feature", "created_at"),)

    feature: Mapped[str] = mapped_column(String(60))
    model_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_models.id", ondelete="SET NULL")
    )
    model_slug: Mapped[str] = mapped_column(String(120))
    provider_slug: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(30))
    route_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ai_model_routes.id", ondelete="SET NULL")
    )
    #: O rótulo da regra também em texto, pelo mesmo motivo do ``model_slug``.
    route_label: Mapped[str | None] = mapped_column(String(120))
    explanation: Mapped[str] = mapped_column(String(500))
    #: Só os sinais realmente informados pela chamada.
    signals: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    #: Uma entrada por regra avaliada, com resultado e condições.
    trace: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
