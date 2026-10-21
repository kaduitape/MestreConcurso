"""O laudo do auditor e as regras que ele aplica.

Duas tabelas, e cada uma existe por um motivo diferente:

``content_audit_rules``
    As regras ficam **no banco**, com severidade e limiar editáveis no painel.
    O código traz o padrão; esta tabela vence. É o que permite baixar uma regra
    de bloqueio para aviso sem deploy — e deixa a mudança registrada em quem.

``content_audits``
    Cada conferência vira uma linha nova. Nada é sobrescrito: o histórico de
    correções é a sequência de laudos do mesmo conteúdo, mostrando o defeito
    aparecendo e sumindo. Laudo apagado é correção que ninguém consegue provar.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType


class ContentAuditRule(IdMixin, TimestampMixin, Base):
    """Regra de auditoria vigente. O código traz o padrão; esta tabela vence."""

    __tablename__ = "content_audit_rules"
    __table_args__ = (UniqueConstraint("key", name="uq_content_audit_rules_key"),)

    key: Mapped[str] = mapped_column(String(60), index=True)
    is_enabled: Mapped[bool] = mapped_column(default=True)
    severity: Mapped[str] = mapped_column(String(20), default="BLOCKER")
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )


class ContentAudit(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma conferência de um conteúdo, com o que foi achado e o que não deu para conferir."""

    __tablename__ = "content_audits"
    __table_args__ = (
        Index("ix_content_audits_target", "target_kind", "target_public_id"),
        Index("ix_content_audits_verdict_created", "verdict", "created_at"),
    )

    target_kind: Mapped[str] = mapped_column(String(30))
    target_public_id: Mapped[str] = mapped_column(String(26), index=True)
    #: CLEAN, WARNED ou BLOCKED — derivado das marcas, nunca acumulado.
    verdict: Mapped[str] = mapped_column(String(20))
    #: PUBLISH (portão), MANUAL (uma pessoa pediu) ou AGENT (o auditor rodou em lote).
    trigger: Mapped[str] = mapped_column(String(20), default="MANUAL")
    #: Se a publicação chegou a ser barrada por este laudo.
    blocked_publication: Mapped[bool] = mapped_column(default=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    #: Contagens e o alcance da conferência (quantas questões entraram na
    #: comparação de duplicata, por exemplo). Sem isso, "nada encontrado" vira
    #: uma garantia que o auditor não deu.
    summary: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
