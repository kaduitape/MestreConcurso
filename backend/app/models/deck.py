"""Baralho oficial por tópico — o cartão que a equipe publica, não o do candidato.

O modelo de flashcard já previa isto desde a Fase 4: ``flashcards.user_id`` nulo
significa cartão global, e o estado de memória vive em outra tabela justamente
para que **um cartão seja revisado por muita gente, cada uma com o próprio
intervalo**. O que faltava não era onde guardar o cartão — era onde guardar o
*baralho*, e três coisas que só um baralho resolve:

* **Portão de conferência.** Cartão de IA não pode chegar a ninguém antes de uma
  pessoa olhar. Enquanto o baralho está ``DRAFT``, nenhum candidato o vê; quem
  publica fica registrado.
* **Escopo.** Um cartão global sem baralho entraria na fila de **todo mundo**,
  inclusive de quem estuda outro concurso. O baralho se liga a um tópico, e o
  candidato **escolhe** entrar nele. Nada aparece na fila de alguém por decisão
  da plataforma.
* **Reaproveitamento.** O vínculo é com o tópico canônico, não com o concurso —
  igual ao mapa mental. Um baralho de "Crase" serve a qualquer concurso que
  cobre "Crase", e é por isso que o tópico é único: "o baralho oficial do
  tópico" não pode ser ambíguo.

A assinatura é só o consentimento de entrar. O estado de memória continua sendo
do candidato: cancelar a assinatura tira os cartões da fila e **não apaga** o
histórico de revisão de ninguém.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import MediumText

if TYPE_CHECKING:
    from app.models.catalog import Subject, Topic


class DeckStatus(StrEnum):
    """Onde o baralho está. Só ``PUBLISHED`` chega a candidato."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class DeckSourceKind(StrEnum):
    """De onde o conteúdo do baralho veio. Governa o selo da interface."""

    #: Escrito pela equipe, à mão.
    EDITORIAL = "EDITORIAL"
    #: Gerado a partir de uma aula **publicada** — texto que alguém já conferiu.
    LESSON = "LESSON"
    #: Gerado a partir de um trecho de edital.
    NOTICE = "NOTICE"
    #: Gerado a partir de material colado por quem cura.
    MATERIAL = "MATERIAL"


class OfficialDeck(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um baralho oficial de um tópico do conteúdo programático."""

    __tablename__ = "official_decks"
    __table_args__ = (
        # Um tópico tem no máximo um baralho oficial: "o baralho do tópico"
        # precisa ser uma coisa só para o candidato e para o plano de geração.
        UniqueConstraint("topic_id", name="uq_official_decks_topic"),
        Index("ix_official_decks_status_created_at", "status", "created_at"),
    )

    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL"), index=True
    )

    title: Mapped[str] = mapped_column(String(200))
    #: O que este baralho cobre, para o candidato decidir se entra.
    description: Mapped[str | None] = mapped_column(MediumText)

    status: Mapped[str] = mapped_column(String(20), default=DeckStatus.DRAFT, index=True)
    source_kind: Mapped[str] = mapped_column(String(20), default=DeckSourceKind.EDITORIAL)
    #: Identificador público da origem concreta, quando existir (a aula, o edital).
    source_ref: Mapped[str | None] = mapped_column(String(60))

    created_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    #: Quem olhou os cartões e assumiu a publicação. Sem isso nada é publicado.
    published_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subject: Mapped[Subject | None] = relationship(lazy="selectin")
    topic: Mapped[Topic] = relationship(lazy="selectin")

    @property
    def is_published(self) -> bool:
        return self.status == DeckStatus.PUBLISHED


class DeckSubscription(IdMixin, TimestampMixin, Base):
    """O candidato escolheu receber os cartões deste baralho.

    É consentimento, não progresso: o avanço de cada cartão continua em
    ``flashcard_states``, que é por pessoa e sobrevive ao cancelamento.
    """

    __tablename__ = "official_deck_subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "deck_id", name="uq_deck_subscriptions_user_deck"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    deck_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("official_decks.id", ondelete="CASCADE"), index=True
    )
