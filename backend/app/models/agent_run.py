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
    #: Motivo da parada, quando houve. Vazio quando terminou inteira. É
    #: preenchido a partir dos passos que falharam — antes era lido pela API e
    #: nunca escrito por ninguém, então a tela recebia sempre nulo.
    error: Mapped[str | None] = mapped_column(MediumText)
    #: Id de correlação do pedido que criou a execução, para cruzar com a
    #: auditoria e com o log do servidor.
    request_id: Mapped[str | None] = mapped_column(String(64))
    #: Quem pediu para parar, e quando.
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
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

    #: Quando o passo começou a rodar nesta tentativa. Serve para o varredor
    #: de passos travados: processo morto deixa ``RUNNING`` para sempre, e sem
    #: marca de tempo não há como saber que ele morreu.
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped[AgentRun] = relationship(back_populates="steps")
    tries: Mapped[list[AgentStepAttempt]] = relationship(
        back_populates="step",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AgentStepAttempt.number",
    )


class AgentStepAttempt(IdMixin, TimestampMixin, Base):
    """Uma tentativa de um passo, com o que aconteceu nela.

    Existe porque o detalhe do passo guarda só a **última** coisa que
    aconteceu, e o diagnóstico de um passo que falhou duas vezes por motivos
    diferentes mora nas duas. Era aqui que a informação se perdia: a segunda
    falha sobrescrevia a primeira, e a mensagem de "esgotou as tentativas"
    sobrescrevia as duas.
    """

    __tablename__ = "agent_step_attempts"
    __table_args__ = (
        UniqueConstraint("step_id", "number", name="uq_agent_step_attempts_step_id_number"),
        Index("ix_agent_step_attempts_step", "step_id", "number"),
    )

    step_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("agent_steps.id", ondelete="CASCADE"), index=True
    )
    #: 1, 2, 3… na ordem em que foram tentadas.
    number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    #: O que aconteceu, em português — a mensagem que vai para a tela.
    detail: Mapped[str | None] = mapped_column(MediumText)
    #: Código estável do erro, quando houve, para agrupar falhas iguais.
    error_code: Mapped[str | None] = mapped_column(String(80))
    #: O tipo da exceção e o caminho dela, quando quebrou. Fica no servidor:
    #: a tela recebe o detalhe em português, não a pilha.
    error_class: Mapped[str | None] = mapped_column(String(160))
    traceback: Mapped[str | None] = mapped_column(MediumText)
    #: Id de correlação desta tentativa.
    request_id: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cost_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    #: Provedor e modelo de IA usados, quando houve chamada.
    provider: Mapped[str | None] = mapped_column(String(40))
    model_slug: Mapped[str | None] = mapped_column(String(120))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    step: Mapped[AgentStep] = relationship(back_populates="tries")
