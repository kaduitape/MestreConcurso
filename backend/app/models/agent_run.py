"""Execuções do orquestrador de agentes.

O worker roda em outro processo, então o estado precisa estar no banco: é ele
que alimenta o acompanhamento ao vivo e sobrevive a reinício do contêiner. É a
mesma razão pela qual o progresso da análise de edital já era persistido — aqui
o padrão vira cidadão de primeira classe, com dependências, tentativas e custo.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class AgentRun(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma passada do orquestrador sobre um concurso."""

    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_status_created_at", "status", "created_at"),)

    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="CASCADE"), index=True
    )
    started_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    #: Motivo da parada, quando houve. Vazio quando terminou inteira.
    error: Mapped[str | None] = mapped_column(MediumText)
    #: Soma do custo dos passos, em centavos.
    cost_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list[AgentStep]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class AgentStep(IdMixin, TimestampMixin, Base):
    """Um agente dentro de uma execução."""

    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "agent_key", name="uq_agent_steps_run_id_agent_key"),
        Index("ix_agent_steps_run_id_status", "run_id", "status"),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    agent_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    #: Quantas vezes já foi tentado. Tentativa manual também conta.
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    #: O que aconteceu, em português. É o que a tela mostra — e é obrigatório
    #: quando o passo foi pulado, senão "pulado" vira mistério.
    detail: Mapped[str | None] = mapped_column(MediumText)
    result: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    cost_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[AgentRun] = relationship(back_populates="steps")
