"""Achados do analista de melhorias — as duas únicas tabelas que ele escreve.

O limite L1 do desenho aprovado é este: o serviço do Agente 8 escreve aqui e em
nenhum outro lugar. Nem na configuração de IA, nem no teto de custo, nem nas
regras do auditor — nem para aplicar o que ele mesmo propôs.

A garantia em código é o serviço. A garantia de verdade é a credencial de banco
somente-leitura (limite L4), que concede ``SELECT`` em tudo e escrita apenas
nestas duas tabelas.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class ImprovementDetectorSetting(IdMixin, TimestampMixin, Base):
    """Estado e limiares de um detector. **Não moram no código** — moram aqui.

    ``last_*`` é o registro da última passada, sobrescrito a cada execução. Não
    é estado acumulado: é o log do que a última varredura viu, e é o que permite
    a tela dizer "este detector não rodou por falta de amostra" em vez de deixar
    a ausência de achados parecer ausência de problema.
    """

    __tablename__ = "improvement_detector_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_improvement_detectors_key"),)

    key: Mapped[str] = mapped_column(String(60), index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    #: Limiares vigentes. Mudar um é ``UPDATE``, não deploy.
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: FOUND, CLEAN, NOT_ENOUGH_DATA ou DISABLED.
    last_status: Mapped[str | None] = mapped_column(String(20))
    #: O que a passada viu, em texto — inclusive o que faltou para ela rodar.
    last_detail: Mapped[str | None] = mapped_column(String(500))
    last_found: Mapped[int] = mapped_column(Integer, default=0)


class ImprovementFinding(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um achado: o problema, a evidência que o produziu e a decisão humana.

    ``fingerprint`` é único: a segunda passada **atualiza** o achado aberto em
    vez de criar o segundo igual. Um painel com o mesmo problema repetido
    quarenta vezes é um painel que ninguém abre.
    """

    __tablename__ = "improvement_findings"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_improvement_findings_fingerprint"),
        Index("ix_improvement_findings_status_severity", "status", "severity"),
        Index("ix_improvement_findings_detector", "detector", "status"),
    )

    detector: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    #: ADMIN (há tela para resolver) ou DEVELOPMENT (precisa de código).
    destination: Mapped[str] = mapped_column(String(20), default="ADMIN")
    fingerprint: Mapped[str] = mapped_column(String(200))

    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(MediumText)
    #: A mudança proposta, em texto. Nunca um patch — o agente não lê o
    #: repositório (decisão D1, opção A do desenho).
    proposal: Mapped[str] = mapped_column(MediumText)
    #: Os números que produziram o achado. Sem isto, é opinião.
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    target_kind: Mapped[str | None] = mapped_column(String(30))
    target_public_id: Mapped[str | None] = mapped_column(String(60), index=True)
    #: Gasto medido que o problema consumiu. Nulo quando não há custo medido —
    #: e aí nenhuma economia é afirmada.
    measured_waste_cents: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    #: Quantas passadas acharam este mesmo problema. É o que separa um caso
    #: isolado de um que já foi visto vinte vezes.
    seen_count: Mapped[int] = mapped_column(Integer, default=1)

    decided_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Obrigatório na recusa: recusar sem motivo não ensina nada a ninguém.
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    #: Até quando um achado recusado não volta pela mesma impressão digital.
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Fechado porque o detector deixou de achar — nunca porque alguém disse.
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Quantas vezes o achado reabriu depois de alguém marcar como feito.
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)
