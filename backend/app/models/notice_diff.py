"""Comparação entre duas versões de edital.

A comparação vira registro porque retificação é fato do mundo: alguém precisa
poder dizer, meses depois, **o que mudou e quando descobrimos**. O laudo também
guarda o impacto no conteúdo — e guardar não é apagar: tópico que saiu do edital
deixa a aula órfã, com o motivo escrito, nunca removida.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType


class NoticeDiff(IdMixin, PublicIdMixin, TimestampMixin, Base):
    __tablename__ = "notice_diffs"
    __table_args__ = (Index("ix_notice_diffs_competition_created", "competition_id", "created_at"),)

    competition_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="CASCADE"), index=True
    )
    #: As duas versões comparadas. ``SET NULL`` porque o registro do que mudou
    #: sobrevive ao edital ser removido do catálogo.
    from_notice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="SET NULL")
    )
    to_notice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="SET NULL")
    )
    from_notice_title: Mapped[str] = mapped_column(String(255))
    to_notice_title: Mapped[str] = mapped_column(String(255))
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    #: O que as mudanças atingem no conteúdo que já existe.
    impacts: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    #: Contagens derivadas, incluindo quantas mudanças vieram de dado deduzido.
    summary: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Quem já olhou. Sem isso, uma retificação lida some no meio das outras.
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
