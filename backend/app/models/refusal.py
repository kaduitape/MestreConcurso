"""Recusas por falta de acervo — o que a plataforma **não** conseguiu entregar.

A plataforma já recusa com honestidade: simulado sem questões suficientes não é
montado com questão repetida, rodada de desafio não acontece com enunciado
duplicado e o tutor se recusa a responder sem base. Em todos os três casos ela
explica o motivo para o candidato e **esquecia o fato**.

Essa era a lacuna de instrumentação anotada no desenho do Agente 8: a recusa é o
sinal mais direto de "o que falta no acervo", porque não é opinião de ninguém —
é alguém tendo pedido algo que não existia. Esta tabela guarda isso.

É um log, append-only, como ``ai_usage``: uma linha por recusa, nunca
atualizada. Nada aqui é contador acumulado.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin
from app.db.types import MediumText


class RefusalKind(StrEnum):
    """O que foi pedido e não pôde ser entregue."""

    SIMULATION = "SIMULATION"
    CHALLENGE = "CHALLENGE"
    TUTOR_ANSWER = "TUTOR_ANSWER"


class ResourceRefusal(IdMixin, Base):
    """Uma recusa por falta de acervo, com o que se sabia no momento dela."""

    __tablename__ = "resource_refusals"
    __table_args__ = (
        Index("ix_resource_refusals_kind_created_at", "kind", "created_at"),
        Index("ix_resource_refusals_subject_created_at", "subject_id", "created_at"),
    )

    kind: Mapped[str] = mapped_column(String(20))
    #: O código de erro que a API devolveu — o mesmo que o candidato viu.
    reason_code: Mapped[str] = mapped_column(String(60))
    #: O texto que foi mostrado a ele. Guardar isto evita reescrever depois uma
    #: explicação diferente da que a pessoa recebeu.
    detail: Mapped[str] = mapped_column(MediumText)
    #: Tipo de simulado ou modo de desafio, quando houver.
    variant: Mapped[str | None] = mapped_column(String(40))

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    topic_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="SET NULL")
    )

    #: Quanto foi pedido e quanto havia. Nulos quando o fluxo não trabalha com
    #: número — a recusa do tutor é por ausência de base, não por contagem.
    requested: Mapped[int | None] = mapped_column(Integer)
    available: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
