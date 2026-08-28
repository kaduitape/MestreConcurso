"""Analytics: a foto diária do Mestre Score.

O snapshot existe pelo mesmo motivo do histórico de rank: sem série temporal,
"meu score caiu" é sensação. Guardamos também a **faixa** de cada dia — um
gráfico de evolução sem incerteza sugeriria uma precisão que o número não tem.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin
from app.db.types import JsonType


class MasterScoreSnapshot(IdMixin, TimestampMixin, Base):
    __tablename__ = "master_score_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_master_score_snapshots_user_day"),
        Index("ix_master_score_snapshots_user_day", "user_id", "day"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date)
    value: Mapped[int] = mapped_column(Integer, default=0)
    # Os limites da faixa daquele dia, guardados junto com o valor central.
    low: Mapped[int] = mapped_column(Integer, default=0)
    high: Mapped[int] = mapped_column(Integer, default=0)
    band: Mapped[str] = mapped_column(String(30), default="Início")
    confidence: Mapped[str] = mapped_column(String(10), default="NONE")
    # Peso dos sinais disponíveis (0..1): diz o quanto o número se apoia.
    available_weight: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0"))
    components: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    missing_signals: Mapped[list[str]] = mapped_column(JsonType, default=list)
