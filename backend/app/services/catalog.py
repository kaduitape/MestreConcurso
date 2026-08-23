"""Casos de uso do catálogo: bancas, órgãos, concursos, cargos e disciplinas."""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.slugify import slugify
from app.models.audit import AuditAction
from app.models.catalog import (
    Competition,
    ExamBoard,
    Organization,
    Position,
    PositionSubject,
    Subject,
    Topic,
)
from app.models.user import User
from app.repositories.catalog import (
    CompetitionRepository,
    ExamBoardRepository,
    OrganizationRepository,
    PositionRepository,
    SubjectRepository,
    TopicRepository,
)
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

MAX_TOPIC_DEPTH = 4
MAX_IMPORT_ROWS = 2000


@dataclass(frozen=True, slots=True)
class ImportResult:
    created: int
    updated: int
    skipped: int
    errors: list[str]


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.boards = ExamBoardRepository(session)
        self.organizations = OrganizationRepository(session)
        self.competitions = CompetitionRepository(session)
        self.positions = PositionRepository(session)
        self.subjects = SubjectRepository(session)
        self.topics = TopicRepository(session)
        self.audit = AuditService(session)

    async def _audit(
        self,
        action: str,
        actor: User,
        context: RequestContext,
        resource_type: str,
        resource_id: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        await self.audit.record(
            action,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            meta=meta or {},
        )

    # ------------------------------------------------------------------ #
    # Bancas
    # ------------------------------------------------------------------ #
    async def list_boards(
        self, *, limit: int, offset: int, search: str | None, only_active: bool
    ) -> tuple[Sequence[ExamBoard], int]:
        return await self.boards.search(
            limit=limit, offset=offset, search=search, only_active=only_active
        )

    async def get_board(self, public_id: str) -> ExamBoard:
        board = await self.boards.get_by_public_id(public_id)
        if board is None:
            raise NotFoundError("Banca não encontrada.")
        return board

    async def create_board(
        self, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> ExamBoard:
        slug = data.get("slug") or slugify(data["short_name"])
        if await self.boards.get_by_slug(slug) is not None:
            raise ConflictError("Já existe uma banca com este identificador.")
        board = ExamBoard(slug=slug, **{k: v for k, v in data.items() if k != "slug"})
        self.session.add(board)
        await self.session.flush()
        await self._audit(
            AuditAction.CATALOG_CREATED, actor, context, "exam_board", board.public_id
        )
        await self.session.commit()
        return board

    async def update_board(
        self, public_id: str, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> ExamBoard:
        board = await self.get_board(public_id)
        for field, value in data.items():
            setattr(board, field, value)
        await self._audit(
            AuditAction.CATALOG_UPDATED,
            actor,
            context,
            "exam_board",
            board.public_id,
            {"fields": sorted(data)},
        )
        await self.session.commit()
        return board

    async def delete_board(self, public_id: str, *, actor: User, context: RequestContext) -> None:
        board = await self.get_board(public_id)
        linked = await self.competitions.count(exam_board_id=board.id)
        if linked:
            raise ConflictError(
                "Esta banca está vinculada a concursos e não pode ser removida.",
                details={"competitions": linked},
            )
        await self.boards.delete(board)
        await self._audit(AuditAction.CATALOG_DELETED, actor, context, "exam_board", public_id)
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Órgãos
    # ------------------------------------------------------------------ #
    async def list_organizations(
        self, *, limit: int, offset: int, search: str | None, uf: str | None
    ) -> tuple[Sequence[Organization], int]:
        return await self.organizations.search(limit=limit, offset=offset, search=search, uf=uf)

    async def get_organization(self, public_id: str) -> Organization:
        organization = await self.organizations.get_by_public_id(public_id)
        if organization is None:
            raise NotFoundError("Órgão não encontrado.")
        return organization

    async def create_organization(
        self, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> Organization:
        slug = data.get("slug") or slugify(data["short_name"])
        if await self.organizations.get_by_slug(slug) is not None:
            raise ConflictError("Já existe um órgão com este identificador.")
        organization = Organization(slug=slug, **{k: v for k, v in data.items() if k != "slug"})
        self.session.add(organization)
        await self.session.flush()
        await self._audit(
            AuditAction.CATALOG_CREATED, actor, context, "organization", organization.public_id
        )
        await self.session.commit()
        return organization

    async def update_organization(
        self, public_id: str, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> Organization:
        organization = await self.get_organization(public_id)
        for field, value in data.items():
            setattr(organization, field, value)
        await self._audit(AuditAction.CATALOG_UPDATED, actor, context, "organization", public_id)
        await self.session.commit()
        return organization

    # ------------------------------------------------------------------ #
    # Concursos e cargos
    # ------------------------------------------------------------------ #
    async def list_competitions(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        status: str | None = None,
        exam_board_slug: str | None = None,
        year: int | None = None,
        published_only: bool = False,
    ) -> tuple[Sequence[Competition], int]:
        return await self.competitions.search(
            limit=limit,
            offset=offset,
            search=search,
            status=status,
            exam_board_slug=exam_board_slug,
            year=year,
            published_only=published_only,
        )

    async def get_competition(self, public_id: str, *, published_only: bool = False) -> Competition:
        competition = await self.competitions.get_by_public_id(public_id)
        if competition is None or (published_only and not competition.is_published):
            raise NotFoundError("Concurso não encontrado.")
        return competition

    async def create_competition(
        self,
        data: dict[str, Any],
        *,
        organization_public_id: str,
        exam_board_public_id: str | None,
        actor: User,
        context: RequestContext,
    ) -> Competition:
        organization = await self.get_organization(organization_public_id)
        board = await self.get_board(exam_board_public_id) if exam_board_public_id else None
        slug = data.get("slug") or slugify(
            f"{organization.short_name}-{data['name']}-{data['year']}"
        )
        if await self.competitions.get_by_slug(slug) is not None:
            raise ConflictError("Já existe um concurso com este identificador.")

        competition = Competition(
            slug=slug,
            organization_id=organization.id,
            exam_board_id=board.id if board else None,
            **{k: v for k, v in data.items() if k != "slug"},
        )
        self.session.add(competition)
        await self.session.flush()
        await self._audit(
            AuditAction.CATALOG_CREATED, actor, context, "competition", competition.public_id
        )
        await self.session.commit()
        return await self.get_competition(competition.public_id)

    async def update_competition(
        self,
        public_id: str,
        data: dict[str, Any],
        *,
        organization_public_id: str | None = None,
        exam_board_public_id: str | None = None,
        actor: User,
        context: RequestContext,
    ) -> Competition:
        competition = await self.get_competition(public_id)
        if organization_public_id:
            competition.organization_id = (await self.get_organization(organization_public_id)).id
        if exam_board_public_id is not None:
            competition.exam_board_id = (
                (await self.get_board(exam_board_public_id)).id if exam_board_public_id else None
            )
        for field, value in data.items():
            setattr(competition, field, value)

        await self._audit(
            AuditAction.CATALOG_UPDATED,
            actor,
            context,
            "competition",
            public_id,
            {"fields": sorted(data)},
        )
        await self.session.commit()
        return await self.get_competition(public_id)

    async def delete_competition(
        self, public_id: str, *, actor: User, context: RequestContext
    ) -> None:
        competition = await self.get_competition(public_id)
        await self.competitions.delete(competition)
        await self._audit(AuditAction.CATALOG_DELETED, actor, context, "competition", public_id)
        await self.session.commit()

    async def get_position(self, public_id: str) -> Position:
        position = await self.positions.get_by_public_id(public_id)
        if position is None:
            raise NotFoundError("Cargo não encontrado.")
        return position

    async def create_position(
        self,
        competition_public_id: str,
        data: dict[str, Any],
        *,
        actor: User,
        context: RequestContext,
    ) -> Position:
        competition = await self.get_competition(competition_public_id)
        position = Position(competition_id=competition.id, **data)
        self.session.add(position)
        await self.session.flush()
        await self._audit(
            AuditAction.CATALOG_CREATED, actor, context, "position", position.public_id
        )
        await self.session.commit()
        return await self.get_position(position.public_id)

    async def update_position(
        self, public_id: str, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> Position:
        position = await self.get_position(public_id)
        for field, value in data.items():
            setattr(position, field, value)
        await self._audit(AuditAction.CATALOG_UPDATED, actor, context, "position", public_id)
        await self.session.commit()
        return await self.get_position(public_id)

    async def delete_position(
        self, public_id: str, *, actor: User, context: RequestContext
    ) -> None:
        position = await self.get_position(public_id)
        await self.positions.delete(position)
        await self._audit(AuditAction.CATALOG_DELETED, actor, context, "position", public_id)
        await self.session.commit()

    async def set_position_subject(
        self,
        position_public_id: str,
        subject_public_id: str,
        data: dict[str, Any],
        *,
        actor: User,
        context: RequestContext,
    ) -> PositionSubject:
        """Vincula (ou atualiza) uma disciplina cobrada pelo cargo."""
        position = await self.get_position(position_public_id)
        subject = await self.get_subject(subject_public_id)

        link = next((item for item in position.subjects if item.subject_id == subject.id), None)
        if link is None:
            link = PositionSubject(position_id=position.id, subject_id=subject.id)
            self.session.add(link)
        for field, value in data.items():
            setattr(link, field, value)

        await self._audit(
            AuditAction.CATALOG_UPDATED,
            actor,
            context,
            "position_subject",
            position.public_id,
            {"subject": subject.slug},
        )
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def remove_position_subject(
        self,
        position_public_id: str,
        subject_public_id: str,
        *,
        actor: User,
        context: RequestContext,
    ) -> None:
        position = await self.get_position(position_public_id)
        subject = await self.get_subject(subject_public_id)
        link = next((item for item in position.subjects if item.subject_id == subject.id), None)
        if link is None:
            raise NotFoundError("Disciplina não vinculada a este cargo.")
        await self.session.delete(link)
        await self._audit(
            AuditAction.CATALOG_DELETED,
            actor,
            context,
            "position_subject",
            position.public_id,
            {"subject": subject.slug},
        )
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Disciplinas e assuntos
    # ------------------------------------------------------------------ #
    async def list_subjects(
        self, *, limit: int, offset: int, search: str | None, only_active: bool
    ) -> tuple[Sequence[Subject], int]:
        return await self.subjects.search(
            limit=limit, offset=offset, search=search, only_active=only_active
        )

    async def get_subject(self, public_id: str) -> Subject:
        subject = await self.subjects.get_by_public_id(public_id)
        if subject is None:
            raise NotFoundError("Disciplina não encontrada.")
        return subject

    async def create_subject(
        self, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> Subject:
        slug = data.get("slug") or slugify(data["name"])
        if await self.subjects.get_by_slug(slug) is not None:
            raise ConflictError("Já existe uma disciplina com este identificador.")
        subject = Subject(slug=slug, **{k: v for k, v in data.items() if k != "slug"})
        self.session.add(subject)
        await self.session.flush()
        await self._audit(AuditAction.CATALOG_CREATED, actor, context, "subject", subject.public_id)
        await self.session.commit()
        return subject

    async def update_subject(
        self, public_id: str, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> Subject:
        subject = await self.get_subject(public_id)
        for field, value in data.items():
            setattr(subject, field, value)
        await self._audit(AuditAction.CATALOG_UPDATED, actor, context, "subject", public_id)
        await self.session.commit()
        return subject

    async def list_topics(self, subject_public_id: str) -> Sequence[Topic]:
        subject = await self.get_subject(subject_public_id)
        return await self.topics.list_for_subject(subject.id)

    async def create_topic(
        self,
        subject_public_id: str,
        *,
        name: str,
        parent_public_id: str | None,
        sort_order: int,
        description: str | None,
        actor: User,
        context: RequestContext,
    ) -> Topic:
        subject = await self.get_subject(subject_public_id)
        parent: Topic | None = None
        if parent_public_id:
            parent = await self.topics.get_by_public_id(parent_public_id)
            if parent is None or parent.subject_id != subject.id:
                raise NotFoundError("Assunto pai não encontrado nesta disciplina.")
            if parent.depth + 1 >= MAX_TOPIC_DEPTH:
                raise ValidationError(
                    f"A árvore de assuntos aceita no máximo {MAX_TOPIC_DEPTH} níveis."
                )

        topic = await self._build_topic(subject, parent, name, sort_order, description)
        await self._audit(AuditAction.CATALOG_CREATED, actor, context, "topic", topic.public_id)
        await self.session.commit()
        return topic

    async def _build_topic(
        self,
        subject: Subject,
        parent: Topic | None,
        name: str,
        sort_order: int,
        description: str | None,
    ) -> Topic:
        base_slug = slugify(f"{parent.slug}-{name}" if parent else name, max_length=200)
        existing = await self.topics.get_by_slug(subject.id, base_slug)
        if existing is not None:
            raise ConflictError("Já existe um assunto com este nome nesta disciplina.")

        topic = Topic(
            subject_id=subject.id,
            parent_id=parent.id if parent else None,
            name=name.strip(),
            slug=base_slug,
            depth=(parent.depth + 1) if parent else 0,
            sort_order=sort_order,
            description=description,
        )
        self.session.add(topic)
        await self.session.flush()
        topic.path = f"{parent.path}/{topic.id}" if parent else str(topic.id)
        return topic

    async def delete_topic(self, public_id: str, *, actor: User, context: RequestContext) -> None:
        topic = await self.topics.get_by_public_id(public_id)
        if topic is None:
            raise NotFoundError("Assunto não encontrado.")
        await self.topics.delete_subtree(topic)
        await self._audit(AuditAction.CATALOG_DELETED, actor, context, "topic", public_id)
        await self.session.commit()

    async def import_topics_csv(
        self,
        subject_public_id: str,
        content: bytes,
        *,
        actor: User,
        context: RequestContext,
    ) -> ImportResult:
        """Importa a árvore de assuntos a partir de CSV (``assunto;subassunto;ordem``)."""
        subject = await self.get_subject(subject_public_id)
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValidationError("O arquivo precisa estar em UTF-8.") from exc

        dialect_sample = text[:2048]
        delimiter = ";" if dialect_sample.count(";") >= dialect_sample.count(",") else ","
        rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
        if not rows:
            raise ValidationError("Arquivo CSV vazio.")
        if len(rows) > MAX_IMPORT_ROWS:
            raise ValidationError(
                f"O arquivo excede o limite de {MAX_IMPORT_ROWS} linhas.",
                details={"rows": len(rows)},
            )

        header = [cell.strip().lower() for cell in rows[0]]
        start = 1 if header and header[0] in {"assunto", "topico", "tópico", "topic"} else 0

        created = skipped = 0
        errors: list[str] = []
        parents: dict[str, Topic] = {}

        for index, row in enumerate(rows[start:], start=start + 1):
            cells = [cell.strip() for cell in row if cell.strip()]
            if not cells:
                continue
            try:
                parent_name = cells[0]
                child_name = cells[1] if len(cells) > 1 else None
                order = int(cells[2]) if len(cells) > 2 and cells[2].isdigit() else 0

                parent = parents.get(parent_name.lower())
                if parent is None:
                    parent_slug = slugify(parent_name, max_length=200)
                    parent = await self.topics.get_by_slug(subject.id, parent_slug)
                    if parent is None:
                        parent = await self._build_topic(subject, None, parent_name, order, None)
                        created += 1
                    parents[parent_name.lower()] = parent

                if child_name:
                    child_slug = slugify(f"{parent.slug}-{child_name}", max_length=200)
                    if await self.topics.get_by_slug(subject.id, child_slug) is not None:
                        skipped += 1
                        continue
                    await self._build_topic(subject, parent, child_name, order, None)
                    created += 1
                else:
                    skipped += 0
            except (ConflictError, ValidationError) as exc:
                skipped += 1
                errors.append(f"linha {index}: {exc.message}")
            except (IndexError, ValueError) as exc:
                skipped += 1
                errors.append(f"linha {index}: formato inválido ({exc})")

        await self._audit(
            AuditAction.CATALOG_IMPORTED,
            actor,
            context,
            "subject",
            subject.public_id,
            {"created": created, "skipped": skipped},
        )
        await self.session.commit()
        logger.info(
            "catalog.topics_imported", subject=subject.slug, created=created, skipped=skipped
        )
        return ImportResult(created=created, updated=0, skipped=skipped, errors=errors[:20])
