"""Planos de geração em massa por tópico do edital.

O plano existe como registro porque **ninguém dispara centenas de chamadas de
IA no escuro**: ele é montado, mostrado com a estimativa, confirmado por uma
pessoa e só então roda. E roda incremental — cada item guarda o próprio
desfecho, então retomar não refaz o que já deu certo e não paga de novo pelo
que já foi gerado.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class GenerationPlan(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma passada de geração sobre o conteúdo programático de um concurso."""

    __tablename__ = "generation_plans"
    __table_args__ = (Index("ix_generation_plans_status_created_at", "status", "created_at"),)

    competition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)
    #: Tipos de conteúdo escolhidos para esta passada.
    kinds: Mapped[list[str]] = mapped_column(JsonType, default=list)
    #: Personagem, nível, duração, painéis — quem cria o plano decide, porque
    #: isso é escolha editorial, não constante de código.
    options: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    #: Estimativa a partir do custo **medido**; zero com ``is_known`` falso quer
    #: dizer "não deu para estimar", que é diferente de "não custa nada".
    estimate_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    estimate_is_known: Mapped[bool] = mapped_column(default=False)
    #: A conta à mostra: itens, tamanho da amostra e mediana por funcionalidade.
    estimate_basis: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    #: Gasto real, somado dos itens.
    spent_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Quem olhou a estimativa e mandou rodar. Sem isso, nada dispara.
    confirmed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list[GenerationItem]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class GenerationItem(IdMixin, TimestampMixin, Base):
    """Um tópico e um tipo de conteúdo dentro do plano."""

    __tablename__ = "generation_items"
    __table_args__ = (Index("ix_generation_items_plan_status", "plan_id", "status"),)

    plan_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("generation_plans.id", ondelete="CASCADE"), index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    #: Guardados em texto porque o plano precisa continuar legível mesmo se o
    #: catálogo mudar depois.
    topic_name: Mapped[str] = mapped_column(String(200))
    subject_name: Mapped[str] = mapped_column(String(140))
    kind: Mapped[str] = mapped_column(String(30))
    #: GENERATE ou REUSE, decidido quando o plano foi montado.
    decision: Mapped[str] = mapped_column(String(20), default="GENERATE")
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    #: Por que esta decisão, e depois o que aconteceu. Sempre em português.
    reason: Mapped[str | None] = mapped_column(MediumText)
    #: O conteúdo gerado — ou o que foi reaproveitado.
    target_public_id: Mapped[str | None] = mapped_column(String(26))
    cost_cents: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    plan: Mapped[GenerationPlan] = relationship(back_populates="items")
