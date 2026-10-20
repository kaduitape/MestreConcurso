"""Vincular conteúdo ao catálogo — a ponte que faltava.

Questão e flashcard sempre souberam de qual tópico eram. Aula e mapa mental
nasceram guardando só texto livre. Sem essa ponte, retificar um edital não tem
como saber qual aula precisa ser refeita, e o painel do aluno não consegue
dizer quanto de um tópico já foi estudado.

Duas regras governam este serviço:

*A sugestão não aplica nada.* O casamento é calculado por
``app.domain.catalog_match`` — determinístico, auditável, sem IA — e devolvido
ordenado. Quem confirma é uma pessoa no painel. Casar no chute mandaria o
conteúdo para o tópico errado, e o aluno estudaria achando que está certo.

*Sem vínculo continua valendo.* Conteúdo não vinculado funciona exatamente como
hoje. A coluna é anulável porque "não sei" é uma resposta melhor que um palpite.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.domain.catalog_match import CatalogEntry, MatchResult, suggest
from app.models.audit import AuditAction
from app.models.catalog import Subject, Topic
from app.models.mindmap import MindMap
from app.models.training import TrainingLesson
from app.models.user import User
from app.services.audit import AuditService
from app.services.auth import RequestContext


class LinkableKind(StrEnum):
    """O que ainda pode precisar de vínculo."""

    TRAINING = "TRAINING"
    MINDMAP = "MINDMAP"


@dataclass(frozen=True, slots=True)
class PendingItem:
    """Um conteúdo sem vínculo, com o que o catálogo tem a oferecer."""

    kind: str
    public_id: str
    title: str
    subject_text: str
    topic_text: str
    subject_suggestions: MatchResult
    #: Já vinculado à disciplina, faltando o tópico.
    subject_public_id: str | None = None


class CatalogLinkService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Catálogo
    # ------------------------------------------------------------------ #
    async def _subject_entries(self) -> list[CatalogEntry]:
        rows = (
            (await self.session.execute(select(Subject).where(Subject.is_active.is_(True))))
            .scalars()
            .all()
        )
        return [CatalogEntry(public_id=item.public_id, name=item.name) for item in rows]

    async def _topic_entries(self, subject_id: int) -> list[CatalogEntry]:
        rows = (
            (await self.session.execute(select(Topic).where(Topic.subject_id == subject_id)))
            .scalars()
            .all()
        )
        return [
            CatalogEntry(public_id=item.public_id, name=item.name, path=item.path) for item in rows
        ]

    async def _subject(self, public_id: str) -> Subject:
        found = (
            await self.session.execute(select(Subject).where(Subject.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Disciplina não encontrada.")
        return found

    async def _topic(self, public_id: str, *, subject_id: int) -> Topic:
        found = (
            await self.session.execute(select(Topic).where(Topic.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Tópico não encontrado.")
        if found.subject_id != subject_id:
            # Deixar passar criaria um vínculo impossível: tópico de uma
            # disciplina pendurado em outra.
            raise ValidationError(
                "O tópico escolhido não pertence a essa disciplina.",
                code="topic_subject_mismatch",
            )
        return found

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def _record(self, kind: str, public_id: str) -> TrainingLesson | MindMap:
        model: Any = TrainingLesson if kind == LinkableKind.TRAINING else MindMap
        found = (
            await self.session.execute(select(model).where(model.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Conteúdo não encontrado.")
        return found  # type: ignore[no-any-return]

    async def pending(self, *, limit: int = 50, offset: int = 0) -> tuple[list[PendingItem], int]:
        """Conteúdo sem vínculo completo, já com as disciplinas candidatas.

        "Sem vínculo completo" inclui o que tem disciplina mas não tem tópico:
        meia ponte não serve para reprocessar nada.
        """
        subjects = await self._subject_entries()
        by_id = {}
        for row in (await self.session.execute(select(Subject))).scalars().all():
            by_id[row.id] = row.public_id

        items: list[PendingItem] = []
        for kind, model in (
            (LinkableKind.TRAINING, TrainingLesson),
            (LinkableKind.MINDMAP, MindMap),
        ):
            rows = (
                (
                    await self.session.execute(
                        select(model)
                        .where(or_(model.subject_id.is_(None), model.topic_id.is_(None)))
                        .order_by(model.created_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                items.append(
                    PendingItem(
                        kind=kind,
                        public_id=row.public_id,
                        title=row.title,
                        subject_text=row.subject,
                        topic_text=row.topic,
                        subject_public_id=by_id.get(row.subject_id or 0),
                        subject_suggestions=suggest(row.subject, subjects),
                    )
                )

        total = len(items)
        return items[offset : offset + limit], total

    async def topic_suggestions(
        self, kind: str, public_id: str, *, subject_public_id: str
    ) -> MatchResult:
        """Tópicos candidatos dentro de uma disciplina já escolhida."""
        record = await self._record(kind, public_id)
        subject = await self._subject(subject_public_id)
        return suggest(record.topic, await self._topic_entries(subject.id))

    # ------------------------------------------------------------------ #
    # Escrita
    # ------------------------------------------------------------------ #
    async def link(
        self,
        kind: str,
        public_id: str,
        *,
        subject_public_id: str | None,
        topic_public_id: str | None,
        actor: User,
        context: RequestContext,
    ) -> TrainingLesson | MindMap:
        """Grava o vínculo confirmado por uma pessoa.

        ``subject_public_id`` vazio desfaz o vínculo — quem revisa precisa poder
        dizer "isto não é disciplina nenhuma do catálogo" e seguir em frente.
        """
        record = await self._record(kind, public_id)

        if subject_public_id is None:
            if topic_public_id is not None:
                raise ValidationError(
                    "Tópico sem disciplina não é vínculo.", code="topic_without_subject"
                )
            record.subject_id = None
            record.topic_id = None
        else:
            subject = await self._subject(subject_public_id)
            record.subject_id = subject.id
            record.topic_id = (
                (await self._topic(topic_public_id, subject_id=subject.id)).id
                if topic_public_id
                else None
            )

        await self.audit.record(
            AuditAction.CATALOG_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type=f"link.{kind.lower()}",
            resource_id=public_id,
            meta={"subject": subject_public_id, "topic": topic_public_id},
        )
        await self.session.commit()
        return await self._record(kind, public_id)

    async def subject_public_id(self, subject_id: int) -> str | None:
        found = (
            await self.session.execute(select(Subject).where(Subject.id == subject_id))
        ).scalar_one_or_none()
        return found.public_id if found else None

    async def topic_public_id(self, topic_id: int) -> str | None:
        found = (
            await self.session.execute(select(Topic).where(Topic.id == topic_id))
        ).scalar_one_or_none()
        return found.public_id if found else None
