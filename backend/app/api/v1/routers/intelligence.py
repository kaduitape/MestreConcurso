"""Inteligência: incidência, DNA da banca, Priority Score e Caderno de Erros."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, RequestCtx, rate_limit, require_permissions
from app.core.errors import NotFoundError
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.domain.intelligence import CAUSE_ACTIONS, CAUSE_LABELS
from app.models.audit import AuditAction
from app.models.catalog import ExamBoard
from app.models.intelligence import ErrorAnalysis
from app.models.user import User
from app.repositories.intelligence import (
    BoardProfileMetricRepository,
    TopicIncidenceRepository,
)
from app.schemas.common import MessageResponse
from app.schemas.intelligence import (
    BoardDnaRead,
    BoardMetricRead,
    CauseSuggestionRead,
    CauseSummaryRead,
    ClassifyErrorInput,
    ContributionRead,
    ErrorAnalysisRead,
    ErrorNotebookRead,
    IncidenceMapRead,
    IncidenceRowRead,
    PendingAttemptRead,
    PriorityListRead,
    PriorityRead,
    RecomputeResultRead,
    SubjectErrorRead,
    TrapPatternRead,
    TrapSummaryRead,
)
from app.services.audit import AuditService
from app.services.error_notebook import ErrorNotebookService
from app.services.intelligence import IntelligenceService
from app.services.priority import PriorityService

router = APIRouter(tags=["inteligência"])
intel_router = APIRouter(prefix="/intelligence", tags=["inteligência"])
errors_router = APIRouter(prefix="/errors", tags=["caderno de erros"])
admin_router = APIRouter(prefix="/admin/intelligence", tags=["admin · inteligência"])

IntelligenceWriter = Annotated[User, Depends(require_permissions(perms.INTELLIGENCE_WRITE))]
PageDep = Annotated[PageParams, Depends(page_params)]


async def _board(db: DbSession, slug: str) -> ExamBoard:
    board = (await db.execute(select(ExamBoard).where(ExamBoard.slug == slug))).scalar_one_or_none()
    if board is None:
        raise NotFoundError("Banca não encontrada.")
    return board


def _analysis_read(row: ErrorAnalysis) -> ErrorAnalysisRead:
    question = row.attempt.question
    return ErrorAnalysisRead(
        public_id=row.public_id,
        cause=row.cause,
        cause_label=CAUSE_LABELS.get(row.cause, row.cause),
        question_public_id=question.public_id,
        question_statement=question.statement[:400],
        subject_name=question.subject.name if question.subject else None,
        selected_letter=row.attempt.selected_letter,
        trap_slug=row.trap_pattern.slug if row.trap_pattern else None,
        trap_name=row.trap_pattern.name if row.trap_pattern else None,
        note=row.note,
        source=row.source,
        model_slug=row.model_slug,
        rationale=row.rationale,
        is_confirmed=row.is_confirmed,
        is_resolved=row.resolved_at is not None,
        created_at=row.created_at,
    )


# --------------------------------------------------------------------------- #
# Mapa de incidência e DNA da banca
# --------------------------------------------------------------------------- #
@intel_router.get(
    "/incidence/{board_slug}",
    response_model=IncidenceMapRead,
    summary="Mapa de incidência da banca",
)
async def incidence_map(board_slug: str, _: CurrentUser, db: DbSession) -> IncidenceMapRead:
    board = await _board(db, board_slug)
    rows = list(await TopicIncidenceRepository(db).for_board(board.id))
    if not rows:
        return IncidenceMapRead(
            board_slug=board.slug,
            board_name=board.name,
            board_questions_count=0,
            empty_reason=(
                "Ainda não há mapa de incidência para esta banca. Ele é calculado sobre as "
                "questões cadastradas e precisa de amostra suficiente para existir."
            ),
        )

    first = rows[0]
    return IncidenceMapRead(
        board_slug=board.slug,
        board_name=board.name,
        period_start_year=first.period_start_year or None,
        period_end_year=first.period_end_year or None,
        board_questions_count=first.board_questions_count,
        computed_at=first.computed_at,
        rows=[
            IncidenceRowRead(
                subject_name=row.subject_name,
                topic_name=row.topic_name,
                questions_count=row.questions_count,
                exams_count=row.exams_count,
                incidence_pct=float(row.incidence_pct),
                trend=None if row.trend is None else float(row.trend),
                confidence=float(row.confidence),
                board_questions_count=row.board_questions_count,
            )
            for row in rows
        ],
    )


@intel_router.get("/board-dna/{board_slug}", response_model=BoardDnaRead, summary="DNA da banca")
async def board_dna(board_slug: str, _: CurrentUser, db: DbSession) -> BoardDnaRead:
    board = await _board(db, board_slug)
    metrics = list(await BoardProfileMetricRepository(db).for_board(board.id))
    if not metrics:
        return BoardDnaRead(
            board_slug=board.slug,
            board_name=board.name,
            empty_reason=(
                "O perfil desta banca ainda não foi calculado: são necessárias mais "
                "questões cadastradas dela no banco."
            ),
        )
    return BoardDnaRead(
        board_slug=board.slug,
        board_name=board.name,
        computed_at=metrics[0].computed_at,
        metrics=[
            BoardMetricRead(
                metric_slug=metric.metric_slug,
                label=metric.label,
                value=float(metric.value),
                unit=metric.unit,
                detail={key: float(value) for key, value in (metric.detail or {}).items()},
                sample_questions=metric.sample_questions,
                sample_exams=metric.sample_exams,
                period_start_year=metric.period_start_year,
                period_end_year=metric.period_end_year,
                confidence=float(metric.confidence),
            )
            for metric in metrics
        ],
    )


# --------------------------------------------------------------------------- #
# Priority Score
# --------------------------------------------------------------------------- #
@intel_router.get("/priority", response_model=PriorityListRead, summary="Minhas prioridades")
async def priority_list(user: CurrentUser, db: DbSession) -> PriorityListRead:
    rows = await PriorityService(db).stored(user)
    return PriorityListRead(
        computed_at=rows[0].computed_at if rows else None,
        items=[
            PriorityRead(
                scope_key=row.scope_key,
                label=row.label,
                color_token=row.color_token,
                score=row.score,
                contributions=[ContributionRead(**item) for item in row.contributions],
                missing_signals=list(row.missing_signals or []),
                coverage=float(row.coverage),
                computed_at=row.computed_at,
            )
            for row in rows
        ],
        notes=(
            []
            if rows
            else [
                "O Priority Score ainda não foi calculado. Ele depende do seu plano de "
                "estudo ativo e dos sinais que você já tiver gerado."
            ]
        ),
    )


@intel_router.post(
    "/priority/recompute",
    response_model=PriorityListRead,
    summary="Recalcular minhas prioridades",
    dependencies=[Depends(rate_limit("20/hour", scope="priority:recompute"))],
)
async def recompute_priority(user: CurrentUser, db: DbSession) -> PriorityListRead:
    report = await PriorityService(db).compute(user)
    return PriorityListRead(
        computed_at=report.computed_at,
        board_slug=report.board_slug,
        notes=report.notes,
        items=[
            PriorityRead(
                scope_key=score.scope_key,
                label=score.label,
                color_token=score.color_token,
                score=score.score,
                contributions=[
                    ContributionRead(
                        key=item.key,
                        label=item.label,
                        points=item.points,
                        max_points=item.max_points,
                        detail=item.detail,
                    )
                    for item in score.contributions
                ],
                missing_signals=list(score.missing_signals),
                coverage=score.coverage,
                computed_at=report.computed_at,
            )
            for score in report.scores
        ],
    )


# --------------------------------------------------------------------------- #
# Caderno de erros
# --------------------------------------------------------------------------- #
@errors_router.get("", response_model=Page[ErrorAnalysisRead], summary="Meus erros classificados")
async def list_errors(
    user: CurrentUser,
    db: DbSession,
    params: PageDep,
    cause: Annotated[str | None, Query(max_length=30)] = None,
    pending: Annotated[bool, Query()] = False,
) -> Page[ErrorAnalysisRead]:
    rows, total = await ErrorNotebookService(db).list_analyses(
        user, limit=params.page_size, offset=params.offset, cause=cause, only_pending=pending
    )
    return Page.create([_analysis_read(row) for row in rows], total, params)


@errors_router.get(
    "/pending", response_model=list[PendingAttemptRead], summary="Erros sem causa registrada"
)
async def pending_errors(user: CurrentUser, db: DbSession) -> list[PendingAttemptRead]:
    attempts = await ErrorNotebookService(db).pending_attempts(user)
    return [
        PendingAttemptRead(
            attempt_public_id=attempt.public_id,
            question_public_id=attempt.question.public_id,
            question_statement=attempt.question.statement[:400],
            subject_name=attempt.question.subject.name if attempt.question.subject else None,
            selected_letter=attempt.selected_letter,
            created_at=attempt.created_at,
        )
        for attempt in attempts
    ]


@errors_router.get("/notebook", response_model=ErrorNotebookRead, summary="Caderno de erros")
async def notebook(user: CurrentUser, db: DbSession) -> ErrorNotebookRead:
    result = await ErrorNotebookService(db).notebook(user)
    return ErrorNotebookRead(
        total=result.total,
        resolved=result.resolved,
        by_cause=[
            CauseSummaryRead(
                cause=item.cause,
                label=item.label,
                count=item.count,
                share=item.share,
                action=item.action,
            )
            for item in result.by_cause
        ],
        by_subject=[
            SubjectErrorRead(
                subject_name=item.subject_name,
                count=item.count,
                dominant_cause=item.dominant_cause,
                dominant_cause_label=item.dominant_cause_label,
            )
            for item in result.by_subject
        ],
        traps=[
            TrapSummaryRead(slug=item.slug, name=item.name, count=item.count, share=item.share)
            for item in result.traps
        ],
        insights=result.insights,
        notes=result.notes,
        causes_catalogue={
            key: {"label": label, "action": CAUSE_ACTIONS.get(key, "")}
            for key, label in CAUSE_LABELS.items()
        },
    )


@errors_router.get("/traps", response_model=list[TrapPatternRead], summary="Padrões de pegadinha")
async def trap_catalogue(_: CurrentUser, db: DbSession) -> list[TrapPatternRead]:
    patterns = await ErrorNotebookService(db).trap_catalogue()
    return [TrapPatternRead.model_validate(item) for item in patterns]


@errors_router.post(
    "/attempts/{attempt_public_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=ErrorAnalysisRead,
    summary="Registrar a causa de um erro",
)
async def classify_error(
    attempt_public_id: str, payload: ClassifyErrorInput, user: CurrentUser, db: DbSession
) -> ErrorAnalysisRead:
    analysis = await ErrorNotebookService(db).classify(
        user,
        attempt_public_id,
        cause=payload.cause,
        trap_slug=payload.trap_slug,
        note=payload.note,
    )
    return _analysis_read(analysis)


@errors_router.post(
    "/attempts/{attempt_public_id}/suggest-cause",
    response_model=CauseSuggestionRead,
    summary="Pedir à IA uma leitura do erro",
    dependencies=[Depends(rate_limit("60/hour", scope="errors:suggest"))],
)
async def suggest_cause(
    attempt_public_id: str, user: CurrentUser, db: DbSession
) -> CauseSuggestionRead:
    """A sugestão fica visível como sugestão e não entra em estatística alguma."""
    suggestion = await ErrorNotebookService(db).suggest_cause(user, attempt_public_id)
    return CauseSuggestionRead(
        cause=suggestion.cause,
        cause_label=CAUSE_LABELS.get(suggestion.cause or "", None),
        trap_slug=suggestion.trap_slug,
        confidence=suggestion.confidence,
        rationale=suggestion.rationale,
        study_tip=suggestion.study_tip,
        model=suggestion.model,
        prompt_version=suggestion.prompt_version,
        confirmed=suggestion.confirmed,
    )


@errors_router.post(
    "/{public_id}/confirm", response_model=ErrorAnalysisRead, summary="Confirmar a causa sugerida"
)
async def confirm_cause(public_id: str, user: CurrentUser, db: DbSession) -> ErrorAnalysisRead:
    return _analysis_read(await ErrorNotebookService(db).confirm(user, public_id))


@errors_router.post(
    "/{public_id}/resolve", response_model=ErrorAnalysisRead, summary="Marcar erro como superado"
)
async def resolve_error(public_id: str, user: CurrentUser, db: DbSession) -> ErrorAnalysisRead:
    return _analysis_read(await ErrorNotebookService(db).resolve(user, public_id))


@errors_router.delete("/{public_id}", response_model=MessageResponse, summary="Remover do caderno")
async def delete_error(public_id: str, user: CurrentUser, db: DbSession) -> MessageResponse:
    await ErrorNotebookService(db).delete(user, public_id)
    return MessageResponse(message="Classificação removida.")


# --------------------------------------------------------------------------- #
# Recálculo (administração)
# --------------------------------------------------------------------------- #
@admin_router.post(
    "/recompute",
    response_model=list[RecomputeResultRead],
    summary="Recalcular incidência e DNA das bancas",
)
async def recompute(
    actor: IntelligenceWriter,
    db: DbSession,
    ctx: RequestCtx,
    board: Annotated[str | None, Query(max_length=80)] = None,
) -> list[RecomputeResultRead]:
    service = IntelligenceService(db)
    results = [await service.recompute_board(board)] if board else await service.recompute_all()
    await AuditService(db).record(
        AuditAction.INTELLIGENCE_RECOMPUTED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="exam_board",
        resource_id=board or "todas",
        meta={"boards": len(results)},
    )
    await db.commit()
    return [
        RecomputeResultRead(
            board_slug=item.board_slug,
            questions_sampled=item.questions_sampled,
            incidence_rows=item.incidence_rows,
            profile_metrics=item.profile_metrics,
            incidence_blocked=item.incidence_blocked,
            profile_blocked=item.profile_blocked,
        )
        for item in results
    ]


router.include_router(intel_router)
router.include_router(errors_router)
router.include_router(admin_router)
