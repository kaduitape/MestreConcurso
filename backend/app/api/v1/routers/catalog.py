"""Catálogo público — o que o candidato autenticado consulta."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, rate_limit
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.models.notice import NoticeStatus
from app.repositories.notice import NoticeRepository
from app.schemas.board_knowledge import BoardKnowledgeRead
from app.schemas.catalog import (
    CompetitionRead,
    CompetitionSummary,
    ExamBoardRead,
    SubjectRead,
    TopicRead,
)
from app.schemas.notice import NoticeRead, RadiographyRead
from app.services.board_knowledge import BoardKnowledgeService
from app.services.catalog import CatalogService
from app.services.notice import NoticeService
from app.services.radiography import RadiographyService

router = APIRouter(prefix="/catalog", tags=["catálogo"])

PageDep = Annotated[PageParams, Depends(page_params)]


@router.get(
    "/competitions",
    response_model=Page[CompetitionSummary],
    summary="Concursos publicados",
    dependencies=[Depends(rate_limit("120/minute", scope="catalog:list"))],
)
async def list_competitions(
    _: CurrentUser,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=140)] = None,
    exam_board: Annotated[str | None, Query(max_length=60)] = None,
    year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", pattern="^(ANNOUNCED|OPEN|IN_PROGRESS|CONCLUDED|CANCELED)$"),
    ] = None,
) -> Page[CompetitionSummary]:
    items, total = await CatalogService(db).list_competitions(
        limit=params.page_size,
        offset=params.offset,
        search=search,
        status=status_filter,
        exam_board_slug=exam_board,
        year=year,
        published_only=True,
    )
    return Page.create([CompetitionSummary.model_validate(item) for item in items], total, params)


@router.get(
    "/competitions/{public_id}",
    response_model=CompetitionRead,
    summary="Detalhe do concurso com cargos e disciplinas",
)
async def get_competition(public_id: str, _: CurrentUser, db: DbSession) -> CompetitionRead:
    competition = await CatalogService(db).get_competition(public_id, published_only=True)
    return CompetitionRead.model_validate(competition)


@router.get(
    "/competitions/{public_id}/notices",
    response_model=list[NoticeRead],
    summary="Editais do concurso",
)
async def list_competition_notices(
    public_id: str, _: CurrentUser, db: DbSession
) -> list[NoticeRead]:
    await CatalogService(db).get_competition(public_id, published_only=True)
    notices = await NoticeService(db).list_for_competition(public_id)
    return [NoticeRead.model_validate(notice) for notice in notices]


@router.get(
    "/notices/{public_id}/radiography",
    response_model=RadiographyRead,
    summary="Raio-X de um edital já confirmado",
)
async def notice_radiography(public_id: str, _: CurrentUser, db: DbSession) -> RadiographyRead:
    """Só edital confirmado aparece para o candidato: análise não revisada não vira verdade."""
    notice = await NoticeRepository(db).get_by_public_id(public_id)
    if notice is None or notice.status != NoticeStatus.CONFIRMED:
        raise NotFoundError("Raio-X indisponível para este edital.")
    result = await RadiographyService(db).build(notice)
    return RadiographyRead.model_validate(result, from_attributes=True)


@router.get("/boards", response_model=Page[ExamBoardRead], summary="Bancas ativas")
async def list_boards(_: CurrentUser, db: DbSession, params: PageDep) -> Page[ExamBoardRead]:
    boards, total = await CatalogService(db).list_boards(
        limit=params.page_size, offset=params.offset, search=None, only_active=True
    )
    return Page.create([ExamBoardRead.model_validate(item) for item in boards], total, params)


@router.get(
    "/boards/{public_id}/knowledge",
    response_model=list[BoardKnowledgeRead],
    summary="O que já se sabe sobre a banca",
)
async def board_knowledge(
    public_id: str,
    _: CurrentUser,
    db: DbSession,
    kind: Annotated[str | None, Query(max_length=40)] = None,
) -> list[BoardKnowledgeRead]:
    """Lê o conhecimento já gravado. Nenhuma chamada de IA acontece aqui."""
    entries = await BoardKnowledgeService(db).list_entries(public_id, kind=kind)
    return [BoardKnowledgeRead.model_validate(entry) for entry in entries if not entry.is_expired]


@router.get("/subjects", response_model=Page[SubjectRead], summary="Disciplinas ativas")
async def list_subjects(_: CurrentUser, db: DbSession, params: PageDep) -> Page[SubjectRead]:
    items, total = await CatalogService(db).list_subjects(
        limit=params.page_size, offset=params.offset, search=None, only_active=True
    )
    return Page.create([SubjectRead.model_validate(item) for item in items], total, params)


@router.get(
    "/subjects/{public_id}/topics",
    response_model=list[TopicRead],
    summary="Assuntos da disciplina",
)
async def list_topics(public_id: str, _: CurrentUser, db: DbSession) -> list[TopicRead]:
    topics = await CatalogService(db).list_topics(public_id)
    by_id = {topic.id: topic for topic in topics}
    return [
        TopicRead(
            public_id=topic.public_id,
            name=topic.name,
            slug=topic.slug,
            depth=topic.depth,
            path=topic.path,
            sort_order=topic.sort_order,
            description=topic.description,
            parent_public_id=(
                by_id[topic.parent_id].public_id
                if topic.parent_id and topic.parent_id in by_id
                else None
            ),
        )
        for topic in topics
    ]
