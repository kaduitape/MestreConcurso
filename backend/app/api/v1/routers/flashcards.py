"""Flashcards e revisão espaçada."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, rate_limit
from app.core.errors import ValidationError
from app.core.pagination import Page, PageParams, page_params
from app.domain.billing.plans import FeatureKey
from app.domain.srs import DEFAULT_DAILY_LIMIT, DEFAULT_NEW_PER_DAY
from app.models.flashcard import CardMemoryState, Flashcard
from app.schemas.common import MessageResponse
from app.schemas.flashcard import (
    AnswerInput,
    CardStateRead,
    FlashcardCreate,
    FlashcardRead,
    FlashcardUpdate,
    FromSourceInput,
    GenerateInput,
    GenerationRead,
    QueueItemRead,
    QueuePlanRead,
    ReviewQueueRead,
    ReviewResultRead,
    ReviewStatsRead,
)
from app.services.entitlements import EntitlementService
from app.services.flashcards import FlashcardService
from app.services.review import ReviewService

router = APIRouter(tags=["flashcards"])
cards_router = APIRouter(prefix="/flashcards", tags=["flashcards"])
review_router = APIRouter(prefix="/review", tags=["revisão"])

PageDep = Annotated[PageParams, Depends(page_params)]


def _card_read(card: Flashcard, *, user_id: int) -> FlashcardRead:
    return FlashcardRead(
        public_id=card.public_id,
        front=card.front,
        back=card.back,
        hint=card.hint,
        tags=card.tags or [],
        subject_name=card.subject.name if card.subject else None,
        origin=card.origin,
        source_ref=card.source_ref,
        source_quote=card.source_quote,
        source_page=card.source_page,
        source_document=card.source_document,
        model_slug=card.model_slug,
        is_owned=card.user_id == user_id,
        created_at=card.created_at,
    )


def _state_read(state: CardMemoryState) -> CardStateRead:
    return CardStateRead(
        state=state.state,
        interval_days=state.interval_days,
        due_on=state.due_on,
        repetitions=state.repetitions,
        lapses=state.lapses,
        ease_factor=float(state.ease_factor),
        last_rating=state.last_rating,
        postponed_count=state.postponed_count,
    )


# --------------------------------------------------------------------------- #
# Baralho
# --------------------------------------------------------------------------- #
@cards_router.get("", response_model=Page[FlashcardRead], summary="Meus cartões")
async def list_cards(
    user: CurrentUser,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    subject: Annotated[str | None, Query(max_length=26)] = None,
    origin: Annotated[
        str | None, Query(pattern="^(USER|AI|QUESTION|ERROR|NOTICE|EDITORIAL)$")
    ] = None,
) -> Page[FlashcardRead]:
    cards, total = await FlashcardService(db).search(
        user,
        limit=params.page_size,
        offset=params.offset,
        search=search,
        subject_public_id=subject,
        origin=origin,
    )
    return Page.create([_card_read(item, user_id=user.id) for item in cards], total, params)


@cards_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=FlashcardRead,
    summary="Criar cartão",
)
async def create_card(payload: FlashcardCreate, user: CurrentUser, db: DbSession) -> FlashcardRead:
    card = await FlashcardService(db).create(
        user,
        front=payload.front,
        back=payload.back,
        hint=payload.hint,
        tags=payload.tags,
        subject_public_id=payload.subject_public_id,
    )
    return _card_read(card, user_id=user.id)


@cards_router.get("/{public_id}", response_model=FlashcardRead, summary="Detalhar cartão")
async def get_card(public_id: str, user: CurrentUser, db: DbSession) -> FlashcardRead:
    card = await FlashcardService(db).get(user, public_id)
    return _card_read(card, user_id=user.id)


@cards_router.patch("/{public_id}", response_model=FlashcardRead, summary="Editar cartão")
async def update_card(
    public_id: str, payload: FlashcardUpdate, user: CurrentUser, db: DbSession
) -> FlashcardRead:
    card = await FlashcardService(db).update(
        user, public_id, payload.model_dump(exclude_unset=True)
    )
    return _card_read(card, user_id=user.id)


@cards_router.delete("/{public_id}", response_model=MessageResponse, summary="Remover cartão")
async def delete_card(public_id: str, user: CurrentUser, db: DbSession) -> MessageResponse:
    await FlashcardService(db).delete(user, public_id)
    return MessageResponse(message="Cartão removido.")


@cards_router.post(
    "/from-source",
    status_code=status.HTTP_201_CREATED,
    response_model=FlashcardRead,
    summary="Criar cartão a partir de uma questão ou de um erro",
)
async def create_from_source(
    payload: FromSourceInput, user: CurrentUser, db: DbSession
) -> FlashcardRead:
    service = FlashcardService(db)
    if payload.error_public_id:
        card = await service.from_error(user, payload.error_public_id)
    elif payload.question_public_id:
        card = await service.from_question(user, payload.question_public_id)
    else:
        raise ValidationError("Informe a questão ou o erro de origem.", code="source_required")
    return _card_read(card, user_id=user.id)


@cards_router.post(
    "/generate",
    response_model=GenerationRead,
    summary="Gerar cartões a partir de um material",
    dependencies=[Depends(rate_limit("30/hour", scope="flashcards:generate"))],
)
async def generate_cards(
    payload: GenerateInput, user: CurrentUser, db: DbSession
) -> GenerationRead:
    """Cada cartão gerado precisa de citação literal no material; o resto é descartado."""
    await EntitlementService(db).consume(user, FeatureKey.AI_FLASHCARDS)
    result = await FlashcardService(db).generate(
        user,
        material=payload.material,
        quantity=payload.quantity,
        subject_public_id=payload.subject_public_id,
        source_document=payload.source_document,
        source_page=payload.source_page,
    )
    return GenerationRead(
        created=[_card_read(item, user_id=user.id) for item in result.created],
        discarded=result.discarded,
        skipped_reason=result.skipped_reason,
        model=result.model,
        prompt_version=result.prompt_version,
    )


# --------------------------------------------------------------------------- #
# Revisão
# --------------------------------------------------------------------------- #
@review_router.get("/queue", response_model=ReviewQueueRead, summary="Fila de hoje")
async def review_queue(
    user: CurrentUser,
    db: DbSession,
    daily_limit: Annotated[int, Query(ge=1, le=300)] = DEFAULT_DAILY_LIMIT,
    new_per_day: Annotated[int, Query(ge=0, le=100)] = DEFAULT_NEW_PER_DAY,
) -> ReviewQueueRead:
    queue = await ReviewService(db).queue(user, daily_limit=daily_limit, new_per_day=new_per_day)
    return _queue_read(queue, user_id=user.id)


@review_router.get("/flash", response_model=ReviewQueueRead, summary="Revisão relâmpago")
async def flash_review(
    user: CurrentUser, db: DbSession, size: Annotated[int, Query(ge=1, le=30)] = 10
) -> ReviewQueueRead:
    queue = await ReviewService(db).flash(user, size=size)
    return _queue_read(queue, user_id=user.id)


@review_router.post(
    "/{public_id}/answer",
    response_model=ReviewResultRead,
    summary="Responder um cartão",
    dependencies=[Depends(rate_limit("600/minute", scope="review:answer"))],
)
async def answer_card(
    public_id: str, payload: AnswerInput, user: CurrentUser, db: DbSession
) -> ReviewResultRead:
    result = await ReviewService(db).answer(
        user, public_id, rating=payload.rating, time_seconds=payload.time_seconds
    )
    return ReviewResultRead(
        interval_days=result.interval_days,
        due_on=result.due_on,
        state=result.state.state,
        breakdown=result.breakdown,
        remaining_today=result.remaining_today,
    )


@review_router.post("/postpone", response_model=MessageResponse, summary="Adiar a fila de hoje")
async def postpone(
    user: CurrentUser, db: DbSession, days: Annotated[int, Query(ge=1, le=7)] = 1
) -> MessageResponse:
    moved = await ReviewService(db).postpone_all(user, days=days)
    return MessageResponse(
        message=f"{moved} cartão(ões) adiado(s) em {days} dia(s).",
        detail={"moved": moved},
    )


@review_router.get("/stats", response_model=ReviewStatsRead, summary="Minha memória em números")
async def review_stats(user: CurrentUser, db: DbSession) -> ReviewStatsRead:
    return ReviewStatsRead(**await ReviewService(db).stats(user))


def _queue_read(queue: object, *, user_id: int) -> ReviewQueueRead:
    from app.services.review import ReviewQueue

    assert isinstance(queue, ReviewQueue)
    plan = queue.plan
    assert plan is not None
    return ReviewQueueRead(
        items=[
            QueueItemRead(
                card=_card_read(item.card, user_id=user_id),
                state=_state_read(item.state),
                is_new=item.is_new,
            )
            for item in queue.items
        ],
        plan=QueuePlanRead(
            review_count=plan.review_count,
            new_count=plan.new_count,
            overdue_count=plan.overdue_count,
            absence_days=plan.absence_days,
            rescheduled_count=len(plan.rescheduled),
            summary=plan.summary,
        ),
        total_cards=queue.total_cards,
        reviewed_today=queue.reviewed_today,
        upcoming=queue.upcoming,
    )


router.include_router(cards_router)
router.include_router(review_router)
