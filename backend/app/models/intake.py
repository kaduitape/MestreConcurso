"""Cadastro de concurso a partir de uma URL — o registro do que foi lido.

A tabela guarda uma **passagem inteira**: o endereço informado, os PDFs que a
página oferecia com a pontuação de cada um, qual foi escolhido e por quê, a
proposta de cadastro campo por campo com a citação que a sustenta, e o que uma
pessoa decidiu no fim.

Isso não é log por capricho. O cadastro de um concurso governa o estudo de
quem usa a plataforma: data de prova, pesos, conteúdo programático. Quando
alguém perguntar, em março, de onde veio a data que está na tela, a resposta
precisa ser "desta página, deste PDF, desta citação na página 7" — e não "a IA
leu em algum lugar".

As colunas em JSON são **instantâneos**, não dados relacionais: elas registram o
que a tela mostrou no momento da decisão. Normalizá-las faria o registro mudar
quando o catálogo mudasse, que é o oposto do que ele serve.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class IntakeSourceKind(StrEnum):
    """De onde veio o edital."""

    #: Alguém colou o endereço de uma página ou de um PDF.
    URL = "URL"
    #: Alguém subiu o arquivo. Não há link para escolher, nem página para ler.
    UPLOAD = "UPLOAD"


class IntakeStatus(StrEnum):
    """Onde a passagem está."""

    #: Buscando a URL.
    FETCHING = "FETCHING"
    #: A página tem PDFs, mas o serviço **não escolheu**: uma pessoa aponta qual.
    AWAITING_CHOICE = "AWAITING_CHOICE"
    #: Analisando o PDF escolhido pelo pipeline do edital.
    ANALYZING = "ANALYZING"
    #: Proposta pronta, esperando revisão humana. Nada foi cadastrado ainda.
    AWAITING_REVIEW = "AWAITING_REVIEW"
    #: Uma pessoa revisou e aplicou: o concurso existe no catálogo.
    APPLIED = "APPLIED"
    #: Uma pessoa descartou a proposta, com motivo.
    REJECTED = "REJECTED"
    #: Quebrou, e o motivo está escrito.
    FAILED = "FAILED"


class CompetitionIntake(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma tentativa de cadastrar um concurso a partir de um endereço."""

    __tablename__ = "competition_intakes"
    __table_args__ = (Index("ix_competition_intakes_status_created", "status", "created_at"),)

    source_kind: Mapped[str] = mapped_column(String(10), default=IntakeSourceKind.URL)
    #: Nulo quando o PDF foi subido: não houve endereço nenhum envolvido.
    source_url: Mapped[str | None] = mapped_column(String(500))
    #: O nome do arquivo subido, como a pessoa o tinha. Serve para ela
    #: reconhecer a passagem na lista.
    source_name: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default=IntakeStatus.FETCHING, index=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )

    #: O edital criado a partir do PDF escolhido. O pipeline da Fase 3 roda nele.
    notice_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("notices.id", ondelete="SET NULL")
    )
    #: Preenchido quando uma pessoa aplica a proposta.
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("competitions.id", ondelete="SET NULL")
    )

    #: Os PDFs que a página oferecia, com pontuação e explicação de cada um.
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    chosen_url: Mapped[str | None] = mapped_column(String(500))
    #: Por que este PDF — ou, quando o serviço recusou escolher, por que recusou.
    choice_reason: Mapped[str | None] = mapped_column(MediumText)

    #: Campo a campo: valor, citação, página e nível de evidência. É o que a
    #: tela de revisão mostra, e o que fica registrado depois de aplicada.
    proposal: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    #: O que já existe no catálogo e combina com a proposta — para não cadastrar
    #: o mesmo concurso duas vezes.
    matches: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    #: A última mensagem: erro, recusa ou motivo do descarte.
    detail: Mapped[str | None] = mapped_column(MediumText)

    #: Verdadeiro quando o cadastro saiu sem ninguém digitar nada — só com o
    #: que o edital sustenta por citação conferida. Fica gravado porque a
    #: pergunta "quem preencheu este campo?" tem resposta diferente nos dois
    #: casos, e quem audita precisa saber qual foi.
    auto_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    #: O que o cadastro automático **não** preencheu, nomeado item por item.
    #: É a parte que ainda espera uma pessoa, e aparecer aqui é o que impede
    #: "cadastrado" de ser lido como "completo".
    gaps: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)

    applied_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    notice: Mapped[Any | None] = relationship("Notice", lazy="selectin")
    competition: Mapped[Any | None] = relationship("Competition", lazy="selectin")
