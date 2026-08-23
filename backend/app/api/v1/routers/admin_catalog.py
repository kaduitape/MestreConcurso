"""CRUD do catálogo de concursos — painel administrativo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.errors import ValidationError
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.user import User
from app.schemas.board_knowledge import (
    BoardKnowledgeCoverage,
    BoardKnowledgeInput,
    BoardKnowledgeRead,
)
from app.schemas.catalog import (
    CompetitionCreate,
    CompetitionRead,
    CompetitionSummary,
    CompetitionUpdate,
    ExamBoardCreate,
    ExamBoardRead,
    ExamBoardUpdate,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
    PositionCreate,
    PositionRead,
    PositionSubjectInput,
    PositionUpdate,
    SubjectCreate,
    SubjectRead,
    SubjectUpdate,
    TopicCreate,
    TopicImportResult,
    TopicRead,
)
from app.schemas.common import MessageResponse
from app.services.board_knowledge import BoardKnowledgeService, KnowledgeInput
from app.services.catalog import CatalogService

router = APIRouter(prefix="/admin/catalog", tags=["admin · catálogo"])

CatalogReader = Annotated[User, Depends(require_permissions(perms.CATALOG_READ))]
CatalogWriter = Annotated[User, Depends(require_permissions(perms.CATALOG_WRITE))]
PageDep = Annotated[PageParams, Depends(page_params)]

MAX_CSV_BYTES = 2 * 1024 * 1024


# --------------------------------------------------------------------------- #
# Bancas
# --------------------------------------------------------------------------- #
@router.get("/boards", response_model=Page[ExamBoardRead], summary="Listar bancas")
async def list_boards(
    _: CatalogReader,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[ExamBoardRead]:
    boards, total = await CatalogService(db).list_boards(
        limit=params.page_size, offset=params.offset, search=search, only_active=False
    )
    return Page.create([ExamBoardRead.model_validate(item) for item in boards], total, params)


@router.post(
    "/boards",
    status_code=status.HTTP_201_CREATED,
    response_model=ExamBoardRead,
    summary="Cadastrar banca",
)
async def create_board(
    payload: ExamBoardCreate, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> ExamBoardRead:
    board = await CatalogService(db).create_board(
        payload.model_dump(exclude_none=True), actor=actor, context=ctx
    )
    return ExamBoardRead.model_validate(board)


@router.patch("/boards/{public_id}", response_model=ExamBoardRead, summary="Editar banca")
async def update_board(
    public_id: str,
    payload: ExamBoardUpdate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> ExamBoardRead:
    board = await CatalogService(db).update_board(
        public_id, payload.model_dump(exclude_unset=True), actor=actor, context=ctx
    )
    return ExamBoardRead.model_validate(board)


@router.delete("/boards/{public_id}", response_model=MessageResponse, summary="Remover banca")
async def delete_board(
    public_id: str, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await CatalogService(db).delete_board(public_id, actor=actor, context=ctx)
    return MessageResponse(message="Banca removida.")


# --------------------------------------------------------------------------- #
# Conhecimento da banca (persistido para não repetir apuração)
# --------------------------------------------------------------------------- #
@router.get(
    "/boards/{public_id}/knowledge",
    response_model=list[BoardKnowledgeRead],
    summary="Conhecimento acumulado sobre a banca",
)
async def list_board_knowledge(
    public_id: str,
    _: CatalogReader,
    db: DbSession,
    kind: Annotated[str | None, Query(max_length=40)] = None,
) -> list[BoardKnowledgeRead]:
    entries = await BoardKnowledgeService(db).list_entries(public_id, kind=kind)
    return [BoardKnowledgeRead.model_validate(entry) for entry in entries]


@router.get(
    "/boards/{public_id}/knowledge/coverage",
    response_model=BoardKnowledgeCoverage,
    summary="Cobertura do que já está guardado",
)
async def board_knowledge_coverage(
    public_id: str, _: CatalogReader, db: DbSession
) -> BoardKnowledgeCoverage:
    return BoardKnowledgeCoverage.model_validate(
        await BoardKnowledgeService(db).coverage(public_id)
    )


@router.put(
    "/boards/{public_id}/knowledge",
    response_model=BoardKnowledgeRead,
    summary="Gravar conhecimento sobre a banca",
)
async def upsert_board_knowledge(
    public_id: str,
    payload: BoardKnowledgeInput,
    actor: CatalogWriter,
    db: DbSession,
) -> BoardKnowledgeRead:
    entry = await BoardKnowledgeService(db).upsert(
        public_id,
        KnowledgeInput(
            kind=payload.kind,
            entry_key=payload.entry_key,
            title=payload.title,
            content=payload.content,
            data=payload.data,
            source=payload.source,
            confidence=payload.confidence,
            sample_exams=payload.sample_exams,
            sample_questions=payload.sample_questions,
            period_start_year=payload.period_start_year,
            period_end_year=payload.period_end_year,
            ttl_days=payload.ttl_days,
        ),
        actor=actor,
    )
    return BoardKnowledgeRead.model_validate(entry)


@router.delete(
    "/boards/{public_id}/knowledge/{entry_id}",
    response_model=MessageResponse,
    summary="Remover um registro de conhecimento",
)
async def delete_board_knowledge(
    public_id: str, entry_id: int, _: CatalogWriter, db: DbSession
) -> MessageResponse:
    await BoardKnowledgeService(db).delete(public_id, entry_id)
    return MessageResponse(message="Registro removido.")


# --------------------------------------------------------------------------- #
# Órgãos
# --------------------------------------------------------------------------- #
@router.get("/organizations", response_model=Page[OrganizationRead], summary="Listar órgãos")
async def list_organizations(
    _: CatalogReader,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=120)] = None,
    uf: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
) -> Page[OrganizationRead]:
    items, total = await CatalogService(db).list_organizations(
        limit=params.page_size, offset=params.offset, search=search, uf=uf
    )
    return Page.create([OrganizationRead.model_validate(item) for item in items], total, params)


@router.post(
    "/organizations",
    status_code=status.HTTP_201_CREATED,
    response_model=OrganizationRead,
    summary="Cadastrar órgão",
)
async def create_organization(
    payload: OrganizationCreate, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> OrganizationRead:
    organization = await CatalogService(db).create_organization(
        payload.model_dump(exclude_none=True), actor=actor, context=ctx
    )
    return OrganizationRead.model_validate(organization)


@router.patch("/organizations/{public_id}", response_model=OrganizationRead, summary="Editar órgão")
async def update_organization(
    public_id: str,
    payload: OrganizationUpdate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> OrganizationRead:
    organization = await CatalogService(db).update_organization(
        public_id, payload.model_dump(exclude_unset=True), actor=actor, context=ctx
    )
    return OrganizationRead.model_validate(organization)


# --------------------------------------------------------------------------- #
# Concursos e cargos
# --------------------------------------------------------------------------- #
@router.get("/competitions", response_model=Page[CompetitionSummary], summary="Listar concursos")
async def list_competitions(
    _: CatalogReader,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=140)] = None,
    status_filter: Annotated[
        str | None,
        Query(alias="status", pattern="^(ANNOUNCED|OPEN|IN_PROGRESS|CONCLUDED|CANCELED)$"),
    ] = None,
    exam_board: Annotated[str | None, Query(max_length=60)] = None,
    year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> Page[CompetitionSummary]:
    items, total = await CatalogService(db).list_competitions(
        limit=params.page_size,
        offset=params.offset,
        search=search,
        status=status_filter,
        exam_board_slug=exam_board,
        year=year,
    )
    return Page.create([CompetitionSummary.model_validate(item) for item in items], total, params)


@router.post(
    "/competitions",
    status_code=status.HTTP_201_CREATED,
    response_model=CompetitionRead,
    summary="Cadastrar concurso",
)
async def create_competition(
    payload: CompetitionCreate, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> CompetitionRead:
    data = payload.model_dump(
        exclude_none=True, exclude={"organization_public_id", "exam_board_public_id"}
    )
    competition = await CatalogService(db).create_competition(
        data,
        organization_public_id=payload.organization_public_id,
        exam_board_public_id=payload.exam_board_public_id,
        actor=actor,
        context=ctx,
    )
    return CompetitionRead.model_validate(competition)


@router.get(
    "/competitions/{public_id}", response_model=CompetitionRead, summary="Detalhar concurso"
)
async def get_competition(public_id: str, _: CatalogReader, db: DbSession) -> CompetitionRead:
    return CompetitionRead.model_validate(await CatalogService(db).get_competition(public_id))


@router.patch(
    "/competitions/{public_id}", response_model=CompetitionRead, summary="Editar concurso"
)
async def update_competition(
    public_id: str,
    payload: CompetitionUpdate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> CompetitionRead:
    data = payload.model_dump(
        exclude_unset=True, exclude={"organization_public_id", "exam_board_public_id"}
    )
    competition = await CatalogService(db).update_competition(
        public_id,
        data,
        organization_public_id=payload.organization_public_id,
        exam_board_public_id=payload.exam_board_public_id,
        actor=actor,
        context=ctx,
    )
    return CompetitionRead.model_validate(competition)


@router.delete(
    "/competitions/{public_id}", response_model=MessageResponse, summary="Remover concurso"
)
async def delete_competition(
    public_id: str, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await CatalogService(db).delete_competition(public_id, actor=actor, context=ctx)
    return MessageResponse(message="Concurso removido.")


@router.post(
    "/competitions/{public_id}/positions",
    status_code=status.HTTP_201_CREATED,
    response_model=PositionRead,
    summary="Adicionar cargo",
)
async def create_position(
    public_id: str,
    payload: PositionCreate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> PositionRead:
    position = await CatalogService(db).create_position(
        public_id, payload.model_dump(exclude_none=True), actor=actor, context=ctx
    )
    return PositionRead.model_validate(position)


@router.patch("/positions/{public_id}", response_model=PositionRead, summary="Editar cargo")
async def update_position(
    public_id: str,
    payload: PositionUpdate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> PositionRead:
    position = await CatalogService(db).update_position(
        public_id, payload.model_dump(exclude_unset=True), actor=actor, context=ctx
    )
    return PositionRead.model_validate(position)


@router.delete("/positions/{public_id}", response_model=MessageResponse, summary="Remover cargo")
async def delete_position(
    public_id: str, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await CatalogService(db).delete_position(public_id, actor=actor, context=ctx)
    return MessageResponse(message="Cargo removido.")


@router.put(
    "/positions/{public_id}/subjects",
    response_model=PositionRead,
    summary="Vincular disciplina ao cargo",
)
async def set_position_subject(
    public_id: str,
    payload: PositionSubjectInput,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> PositionRead:
    service = CatalogService(db)
    await service.set_position_subject(
        public_id,
        payload.subject_public_id,
        payload.model_dump(exclude={"subject_public_id"}, exclude_none=True),
        actor=actor,
        context=ctx,
    )
    return PositionRead.model_validate(await service.get_position(public_id))


@router.delete(
    "/positions/{public_id}/subjects/{subject_public_id}",
    response_model=PositionRead,
    summary="Desvincular disciplina do cargo",
)
async def remove_position_subject(
    public_id: str,
    subject_public_id: str,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> PositionRead:
    service = CatalogService(db)
    await service.remove_position_subject(public_id, subject_public_id, actor=actor, context=ctx)
    return PositionRead.model_validate(await service.get_position(public_id))


# --------------------------------------------------------------------------- #
# Disciplinas e assuntos
# --------------------------------------------------------------------------- #
@router.get("/subjects", response_model=Page[SubjectRead], summary="Listar disciplinas")
async def list_subjects(
    _: CatalogReader,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> Page[SubjectRead]:
    items, total = await CatalogService(db).list_subjects(
        limit=params.page_size, offset=params.offset, search=search, only_active=False
    )
    return Page.create([SubjectRead.model_validate(item) for item in items], total, params)


@router.post(
    "/subjects",
    status_code=status.HTTP_201_CREATED,
    response_model=SubjectRead,
    summary="Cadastrar disciplina",
)
async def create_subject(
    payload: SubjectCreate, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> SubjectRead:
    subject = await CatalogService(db).create_subject(
        payload.model_dump(exclude_none=True), actor=actor, context=ctx
    )
    return SubjectRead.model_validate(subject)


@router.patch("/subjects/{public_id}", response_model=SubjectRead, summary="Editar disciplina")
async def update_subject(
    public_id: str,
    payload: SubjectUpdate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> SubjectRead:
    subject = await CatalogService(db).update_subject(
        public_id, payload.model_dump(exclude_unset=True), actor=actor, context=ctx
    )
    return SubjectRead.model_validate(subject)


@router.get(
    "/subjects/{public_id}/topics",
    response_model=list[TopicRead],
    summary="Árvore de assuntos",
)
async def list_topics(public_id: str, _: CatalogReader, db: DbSession) -> list[TopicRead]:
    service = CatalogService(db)
    topics = await service.list_topics(public_id)
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


@router.post(
    "/subjects/{public_id}/topics",
    status_code=status.HTTP_201_CREATED,
    response_model=TopicRead,
    summary="Adicionar assunto",
)
async def create_topic(
    public_id: str,
    payload: TopicCreate,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> TopicRead:
    topic = await CatalogService(db).create_topic(
        public_id,
        name=payload.name,
        parent_public_id=payload.parent_public_id,
        sort_order=payload.sort_order,
        description=payload.description,
        actor=actor,
        context=ctx,
    )
    return TopicRead(
        public_id=topic.public_id,
        name=topic.name,
        slug=topic.slug,
        depth=topic.depth,
        path=topic.path,
        sort_order=topic.sort_order,
        description=topic.description,
        parent_public_id=payload.parent_public_id,
    )


@router.post(
    "/subjects/{public_id}/topics/import",
    response_model=TopicImportResult,
    summary="Importar assuntos via CSV",
)
async def import_topics(
    public_id: str,
    actor: CatalogWriter,
    db: DbSession,
    ctx: RequestCtx,
    file: Annotated[UploadFile, File(description="CSV: assunto;subassunto;ordem")],
) -> TopicImportResult:
    content = await file.read()
    if len(content) > MAX_CSV_BYTES:
        raise ValidationError("O CSV excede 2 MB.", code="file_too_large")
    result = await CatalogService(db).import_topics_csv(
        public_id, content, actor=actor, context=ctx
    )
    return TopicImportResult(
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
    )


@router.delete("/topics/{public_id}", response_model=MessageResponse, summary="Remover assunto")
async def delete_topic(
    public_id: str, actor: CatalogWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await CatalogService(db).delete_topic(public_id, actor=actor, context=ctx)
    return MessageResponse(message="Assunto removido (subassuntos incluídos).")
