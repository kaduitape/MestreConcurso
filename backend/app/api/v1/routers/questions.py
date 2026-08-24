"""Questões e simulados: banco (admin), prática e execução (candidato)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, RequestCtx, rate_limit, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.question import Question, QuestionStatus, SimulationAttempt
from app.models.user import User
from app.repositories.question import QuestionRepository
from app.schemas.common import MessageResponse
from app.schemas.question import (
    AlternativeAdminRead,
    AlternativeRead,
    AnswerFeedbackRead,
    AnswerInputSchema,
    ApplyClassificationInput,
    AttemptHistoryRead,
    ClassificationSuggestionRead,
    ExamCreate,
    ExamRead,
    ImportSummaryRead,
    QuestionAdminRead,
    QuestionCreate,
    QuestionImportInput,
    QuestionRead,
    QuestionStatsRead,
    QuestionUpdate,
    SaveAnswerInput,
    SimulationAttemptRead,
    SimulationCreate,
    SimulationQuestionRead,
    SimulationRead,
    SimulationRunRead,
)
from app.services.practice import PracticeService
from app.services.question_bank import QuestionBankService
from app.services.simulation import SimulationService

router = APIRouter(tags=["questões"])

QuestionReader = Annotated[User, Depends(require_permissions(perms.QUESTIONS_READ))]
QuestionWriter = Annotated[User, Depends(require_permissions(perms.QUESTIONS_WRITE))]
PageDep = Annotated[PageParams, Depends(page_params)]


def _stats_read(question: Question) -> QuestionStatsRead | None:
    if question.stats is None:
        return None
    accuracy = question.stats.accuracy
    return QuestionStatsRead(
        attempts=question.stats.attempts,
        accuracy=float(accuracy) if accuracy is not None else None,
        average_time_seconds=question.stats.average_time_seconds,
    )


def _question_read(question: Question) -> QuestionRead:
    """Visão do candidato: alternativas sem indicar qual é a correta."""
    return QuestionRead(
        public_id=question.public_id,
        statement=question.statement,
        kind=question.kind,
        difficulty=question.difficulty,
        origin=question.origin,
        year=question.year,
        subject_name=question.subject.name if question.subject else None,
        tags=question.tags or [],
        alternatives=[
            AlternativeRead(public_id=item.public_id, letter=item.letter, content=item.content)
            for item in question.alternatives
        ],
        stats=_stats_read(question),
    )


def _question_admin_read(question: Question) -> QuestionAdminRead:
    return QuestionAdminRead(
        public_id=question.public_id,
        statement=question.statement,
        kind=question.kind,
        difficulty=question.difficulty,
        origin=question.origin,
        status=question.status,
        year=question.year,
        subject_name=question.subject.name if question.subject else None,
        explanation=question.explanation,
        source_note=question.source_note,
        tags=question.tags or [],
        alternatives=[
            AlternativeAdminRead(
                public_id=item.public_id,
                letter=item.letter,
                content=item.content,
                is_correct=item.is_correct,
                feedback=item.feedback,
            )
            for item in question.alternatives
        ],
        ai_suggestion=question.ai_suggestion or {},
        stats=_stats_read(question),
        created_at=question.created_at,
    )


# --------------------------------------------------------------------------- #
# Banco de questões (administração)
# --------------------------------------------------------------------------- #
admin_router = APIRouter(prefix="/admin/questions", tags=["admin · questões"])


@admin_router.get("", response_model=Page[QuestionAdminRead], summary="Listar questões")
async def list_questions(
    _: QuestionReader,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    subject: Annotated[str | None, Query(max_length=26)] = None,
    difficulty: Annotated[str | None, Query(pattern="^(EASY|MEDIUM|HARD)$")] = None,
    status_filter: Annotated[
        str | None, Query(alias="status", pattern="^(DRAFT|PUBLISHED|ARCHIVED|NEEDS_REVIEW)$")
    ] = None,
) -> Page[QuestionAdminRead]:
    subject_id = None
    if subject:
        from sqlalchemy import select

        from app.models.catalog import Subject

        row = (
            await db.execute(select(Subject.id).where(Subject.public_id == subject))
        ).scalar_one_or_none()
        subject_id = int(row) if row else None

    questions, total = await QuestionRepository(db).search(
        limit=params.page_size,
        offset=params.offset,
        search=search,
        subject_id=subject_id,
        difficulty=difficulty,
        status=status_filter,
    )
    return Page.create([_question_admin_read(item) for item in questions], total, params)


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=QuestionAdminRead,
    summary="Cadastrar questão",
)
async def create_question(
    payload: QuestionCreate, actor: QuestionWriter, db: DbSession, ctx: RequestCtx
) -> QuestionAdminRead:
    data = payload.model_dump(
        exclude={"alternatives", "subject_public_id", "exam_public_id", "board_slug"},
        exclude_none=True,
    )
    question = await QuestionBankService(db).create_question(
        data,
        [item.model_dump() for item in payload.alternatives],
        subject_public_id=payload.subject_public_id,
        exam_public_id=payload.exam_public_id,
        board_slug=payload.board_slug,
        actor=actor,
        context=ctx,
    )
    return _question_admin_read(question)


@admin_router.get("/{public_id}", response_model=QuestionAdminRead, summary="Detalhar questão")
async def get_question(public_id: str, _: QuestionReader, db: DbSession) -> QuestionAdminRead:
    return _question_admin_read(await QuestionBankService(db).get_question(public_id))


@admin_router.patch("/{public_id}", response_model=QuestionAdminRead, summary="Editar questão")
async def update_question(
    public_id: str,
    payload: QuestionUpdate,
    actor: QuestionWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> QuestionAdminRead:
    question = await QuestionBankService(db).update_question(
        public_id,
        payload.model_dump(exclude_unset=True, exclude={"subject_public_id"}),
        subject_public_id=payload.subject_public_id,
        actor=actor,
        context=ctx,
    )
    return _question_admin_read(question)


@admin_router.delete("/{public_id}", response_model=MessageResponse, summary="Remover questão")
async def delete_question(
    public_id: str, actor: QuestionWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    await QuestionBankService(db).delete_question(public_id, actor=actor, context=ctx)
    return MessageResponse(message="Questão removida.")


@admin_router.post("/import", response_model=ImportSummaryRead, summary="Importar questões em lote")
async def import_questions(
    payload: QuestionImportInput, actor: QuestionWriter, db: DbSession, ctx: RequestCtx
) -> ImportSummaryRead:
    summary = await QuestionBankService(db).import_questions(
        payload.questions,
        subject_public_id=payload.subject_public_id,
        exam_public_id=payload.exam_public_id,
        board_slug=payload.board_slug,
        actor=actor,
        context=ctx,
    )
    return ImportSummaryRead(
        created=summary.created,
        skipped_duplicates=summary.skipped_duplicates,
        errors=summary.errors,
    )


@admin_router.post(
    "/{public_id}/suggest-classification",
    response_model=ClassificationSuggestionRead,
    summary="Pedir sugestão de classificação à IA",
)
async def suggest_classification(
    public_id: str, _: QuestionWriter, db: DbSession
) -> ClassificationSuggestionRead:
    """A sugestão fica guardada aguardando revisão; nada é aplicado automaticamente."""
    suggestion = await QuestionBankService(db).suggest_classification(public_id)
    return ClassificationSuggestionRead.model_validate(suggestion)


@admin_router.post(
    "/{public_id}/apply-classification",
    response_model=QuestionAdminRead,
    summary="Aplicar a classificação revisada",
)
async def apply_classification(
    public_id: str,
    payload: ApplyClassificationInput,
    actor: QuestionWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> QuestionAdminRead:
    question = await QuestionBankService(db).apply_suggestion(
        public_id,
        subject_public_id=payload.subject_public_id,
        difficulty=payload.difficulty,
        actor=actor,
        context=ctx,
    )
    return _question_admin_read(question)


@admin_router.post(
    "/exams",
    status_code=status.HTTP_201_CREATED,
    response_model=ExamRead,
    summary="Cadastrar prova",
)
async def create_exam(
    payload: ExamCreate, actor: QuestionWriter, db: DbSession, ctx: RequestCtx
) -> ExamRead:
    exam = await QuestionBankService(db).create_exam(
        payload.model_dump(exclude={"board_slug"}, exclude_none=True),
        board_slug=payload.board_slug,
        actor=actor,
        context=ctx,
    )
    return ExamRead.model_validate(exam)


# --------------------------------------------------------------------------- #
# Prática (candidato)
# --------------------------------------------------------------------------- #
practice_router = APIRouter(prefix="/questions", tags=["questões"])


@practice_router.get("", response_model=Page[QuestionRead], summary="Buscar questões")
async def search_questions(
    _: CurrentUser,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    subject: Annotated[str | None, Query(max_length=26)] = None,
    difficulty: Annotated[str | None, Query(pattern="^(EASY|MEDIUM|HARD)$")] = None,
    board: Annotated[str | None, Query(max_length=60)] = None,
    year: Annotated[int | None, Query(ge=1990, le=2100)] = None,
) -> Page[QuestionRead]:
    subject_id = None
    if subject:
        from sqlalchemy import select

        from app.models.catalog import Subject

        row = (
            await db.execute(select(Subject.id).where(Subject.public_id == subject))
        ).scalar_one_or_none()
        subject_id = int(row) if row else None

    questions, total = await PracticeService(db).search(
        limit=params.page_size,
        offset=params.offset,
        search=search,
        subject_id=subject_id,
        difficulty=difficulty,
        board_slug=board,
        year=year,
        status=QuestionStatus.PUBLISHED,
    )
    return Page.create([_question_read(item) for item in questions], total, params)


@practice_router.post(
    "/{public_id}/answer",
    response_model=AnswerFeedbackRead,
    summary="Responder uma questão",
    dependencies=[Depends(rate_limit("240/minute", scope="questions:answer"))],
)
async def answer_question(
    public_id: str, payload: AnswerInputSchema, user: CurrentUser, db: DbSession
) -> AnswerFeedbackRead:
    feedback = await PracticeService(db).answer(
        user,
        public_id,
        letter=payload.letter,
        time_seconds=payload.time_seconds,
        confidence=payload.confidence,
    )
    return AnswerFeedbackRead(
        is_correct=feedback.attempt.is_correct,
        is_blank=feedback.attempt.is_blank,
        selected_letter=feedback.attempt.selected_letter,
        correct_letter=feedback.correct_letter,
        correct_feedback=feedback.correct_feedback,
        selected_feedback=feedback.selected_feedback,
        explanation=feedback.explanation,
        time_seconds=feedback.attempt.time_seconds,
    )


@practice_router.get(
    "/history", response_model=Page[AttemptHistoryRead], summary="Minhas respostas"
)
async def history(user: CurrentUser, db: DbSession, params: PageDep) -> Page[AttemptHistoryRead]:
    attempts, total = await PracticeService(db).history(
        user, limit=params.page_size, offset=params.offset
    )
    items = [
        AttemptHistoryRead(
            public_id=item.public_id,
            question_public_id=item.question.public_id,
            question_statement=item.question.statement[:280],
            selected_letter=item.selected_letter,
            is_correct=item.is_correct,
            is_blank=item.is_blank,
            time_seconds=item.time_seconds,
            created_at=item.created_at,
        )
        for item in attempts
    ]
    return Page.create(items, total, params)


# --------------------------------------------------------------------------- #
# Simulados (candidato)
# --------------------------------------------------------------------------- #
simulation_router = APIRouter(prefix="/simulations", tags=["simulados"])


def _run_read(attempt: SimulationAttempt, answers: dict[str, str | None]) -> SimulationRunRead:
    duration = attempt.simulation.duration_minutes
    remaining = None
    if duration is not None and attempt.status != "FINISHED":
        remaining = max(0, duration * 60 - attempt.elapsed_seconds)

    return SimulationRunRead(
        attempt=SimulationAttemptRead.model_validate(attempt),
        questions=[
            SimulationQuestionRead(
                order_index=item.order_index,
                question=_question_read(item.question),
                selected_letter=answers.get(item.question.public_id),
            )
            for item in attempt.simulation.questions
        ],
        remaining_seconds=remaining,
    )


@simulation_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SimulationRead,
    summary="Montar simulado",
    dependencies=[Depends(rate_limit("30/hour", scope="simulations:create"))],
)
async def create_simulation(
    payload: SimulationCreate, user: CurrentUser, db: DbSession, ctx: RequestCtx
) -> SimulationRead:
    simulation = await SimulationService(db).create(
        user,
        kind=payload.kind,
        questions_count=payload.questions_count,
        subject_public_id=payload.subject_public_id,
        board_slug=payload.board_slug,
        duration_minutes=payload.duration_minutes,
        context=ctx,
    )
    return SimulationRead.model_validate(simulation)


@simulation_router.post(
    "/{public_id}/start",
    status_code=status.HTTP_201_CREATED,
    response_model=SimulationRunRead,
    summary="Iniciar execução",
)
async def start_simulation(public_id: str, user: CurrentUser, db: DbSession) -> SimulationRunRead:
    attempt = await SimulationService(db).start(user, public_id)
    return _run_read(attempt, {})


@simulation_router.get(
    "/attempts/{public_id}",
    response_model=SimulationRunRead,
    summary="Retomar execução de onde parou",
)
async def get_attempt(public_id: str, user: CurrentUser, db: DbSession) -> SimulationRunRead:
    from sqlalchemy import select

    from app.models.question import Question as QuestionModel
    from app.models.question import QuestionAttempt

    service = SimulationService(db)
    attempt = await service.get_attempt(user, public_id)

    rows = (
        await db.execute(
            select(QuestionModel.public_id, QuestionAttempt.selected_letter)
            .join(QuestionAttempt, QuestionAttempt.question_id == QuestionModel.id)
            .where(QuestionAttempt.simulation_attempt_id == attempt.id)
        )
    ).all()
    answers = {str(row[0]): row[1] for row in rows}
    return _run_read(attempt, answers)


@simulation_router.post(
    "/attempts/{public_id}/answer",
    response_model=MessageResponse,
    summary="Salvar resposta (automático)",
    dependencies=[Depends(rate_limit("600/minute", scope="simulations:answer"))],
)
async def save_answer(
    public_id: str, payload: SaveAnswerInput, user: CurrentUser, db: DbSession
) -> MessageResponse:
    await SimulationService(db).save_answer(
        user,
        public_id,
        question_public_id=payload.question_public_id,
        letter=payload.letter,
        time_seconds=payload.time_seconds,
    )
    return MessageResponse(message="Resposta salva.")


@simulation_router.post(
    "/attempts/{public_id}/pause", response_model=SimulationAttemptRead, summary="Pausar"
)
async def pause_attempt(public_id: str, user: CurrentUser, db: DbSession) -> SimulationAttemptRead:
    return SimulationAttemptRead.model_validate(await SimulationService(db).pause(user, public_id))


@simulation_router.post(
    "/attempts/{public_id}/resume", response_model=SimulationAttemptRead, summary="Retomar"
)
async def resume_attempt(public_id: str, user: CurrentUser, db: DbSession) -> SimulationAttemptRead:
    return SimulationAttemptRead.model_validate(await SimulationService(db).resume(user, public_id))


@simulation_router.post(
    "/attempts/{public_id}/finish",
    response_model=SimulationAttemptRead,
    summary="Encerrar e corrigir",
)
async def finish_attempt(
    public_id: str, user: CurrentUser, db: DbSession, ctx: RequestCtx
) -> SimulationAttemptRead:
    attempt = await SimulationService(db).finish(user, public_id, context=ctx)
    return SimulationAttemptRead.model_validate(attempt)


@simulation_router.get(
    "/history", response_model=list[SimulationAttemptRead], summary="Meus simulados"
)
async def simulation_history(user: CurrentUser, db: DbSession) -> list[SimulationAttemptRead]:
    attempts = await SimulationService(db).history(user)
    return [SimulationAttemptRead.model_validate(item) for item in attempts]


@simulation_router.get(
    "/current", response_model=SimulationRunRead | None, summary="Simulado em andamento"
)
async def current_simulation(user: CurrentUser, db: DbSession) -> SimulationRunRead | None:
    service = SimulationService(db)
    running = await service.attempts.get_running(user.id)
    if running is None:
        return None
    return await get_attempt(running.public_id, user, db)


router.include_router(admin_router)
router.include_router(practice_router)
router.include_router(simulation_router)


def _now() -> datetime:
    return datetime.now(UTC)
