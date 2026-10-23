"""Baralho oficial de flashcards — curadoria no painel.

A publicação é uma rota separada de propósito, como a confirmação do plano de
geração: tornar um baralho visível para quem estuda não pode ser efeito
colateral de salvar um cartão.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.deck import OfficialDeck
from app.models.flashcard import Flashcard
from app.models.user import User
from app.schemas.deck import (
    DeckCardCreate,
    DeckCardReview,
    DeckCardsRead,
    DeckGenerateInput,
    DeckGenerationRead,
    OfficialDeckCreate,
    OfficialDeckRead,
)
from app.schemas.flashcard import FlashcardRead
from app.services.decks import DeckView, OfficialDeckService

router = APIRouter(prefix="/admin/flashcard-decks", tags=["admin · baralhos oficiais"])

PageDep = Annotated[PageParams, Depends(page_params)]
DeckReader = Annotated[User, Depends(require_permissions(perms.DECKS_READ))]
DeckWriter = Annotated[User, Depends(require_permissions(perms.DECKS_WRITE))]


def deck_read(view: DeckView, *, is_subscribed: bool = False) -> OfficialDeckRead:
    deck = view.deck
    return OfficialDeckRead(
        public_id=deck.public_id,
        title=deck.title,
        description=deck.description,
        status=deck.status,
        source_kind=deck.source_kind,
        source_ref=deck.source_ref,
        topic_public_id=deck.topic.public_id if deck.topic else None,
        topic_name=deck.topic.name if deck.topic else None,
        subject_name=deck.subject.name if deck.subject else None,
        active_cards=view.active_cards,
        inactive_cards=view.inactive_cards,
        ai_cards=view.ai_cards,
        subscribers=view.subscribers,
        is_subscribed=is_subscribed,
        published_at=deck.published_at,
        created_at=deck.created_at,
    )


def card_read(card: Flashcard, *, deck: OfficialDeck | None = None) -> FlashcardRead:
    baralho = deck or card.deck
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
        is_owned=False,
        is_official=card.is_official,
        deck_title=baralho.title if baralho else None,
        is_active=card.is_active,
        created_at=card.created_at,
    )


@router.get("", response_model=Page[OfficialDeckRead], summary="Listar baralhos oficiais")
async def list_decks(
    _: DeckReader,
    db: DbSession,
    params: PageDep,
    deck_status: Annotated[str | None, Query(pattern="^(DRAFT|PUBLISHED|ARCHIVED)$")] = None,
) -> Page[OfficialDeckRead]:
    views, total = await OfficialDeckService(db).list_decks(
        limit=params.page_size, offset=params.offset, status=deck_status
    )
    return Page.create([deck_read(item) for item in views], total, params)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=OfficialDeckRead,
    summary="Criar baralho oficial de um tópico",
)
async def create_deck(
    payload: OfficialDeckCreate, actor: DeckWriter, db: DbSession, context: RequestCtx
) -> OfficialDeckRead:
    service = OfficialDeckService(db)
    deck = await service.create(
        actor,
        context,
        topic_public_id=payload.topic_public_id,
        title=payload.title,
        description=payload.description,
    )
    return deck_read(await service.view(deck))


@router.get("/{public_id}", response_model=DeckCardsRead, summary="Detalhar baralho e cartões")
async def get_deck(public_id: str, _: DeckReader, db: DbSession) -> DeckCardsRead:
    service = OfficialDeckService(db)
    deck = await service.get(public_id)
    cards = await service.deck_cards(deck)
    return DeckCardsRead(
        deck=deck_read(await service.view(deck)),
        cards=[card_read(item, deck=deck) for item in cards],
    )


@router.post(
    "/{public_id}/cards",
    status_code=status.HTTP_201_CREATED,
    response_model=FlashcardRead,
    summary="Escrever um cartão no baralho",
)
async def add_card(
    public_id: str,
    payload: DeckCardCreate,
    actor: DeckWriter,
    db: DbSession,
    context: RequestCtx,
) -> FlashcardRead:
    service = OfficialDeckService(db)
    deck = await service.get(public_id)
    card = await service.add_card(
        actor,
        context,
        deck,
        front=payload.front,
        back=payload.back,
        hint=payload.hint,
        tags=payload.tags,
    )
    return card_read(card, deck=deck)


@router.post(
    "/{public_id}/generate",
    response_model=DeckGenerationRead,
    summary="Gerar cartões por IA no rascunho",
)
async def generate_cards(
    public_id: str,
    payload: DeckGenerateInput,
    actor: DeckWriter,
    db: DbSession,
    context: RequestCtx,
) -> DeckGenerationRead:
    """Cada cartão gerado precisa de citação literal no material; o resto é descartado."""
    service = OfficialDeckService(db)
    deck = await service.get(public_id)
    result = await service.generate(
        actor,
        context,
        deck,
        material=payload.material,
        quantity=payload.quantity,
        source_document=payload.source_document,
        source_page=payload.source_page,
    )
    return DeckGenerationRead(
        created=[card_read(item, deck=deck) for item in result.created],
        discarded=result.discarded,
        duplicated=result.duplicated,
        skipped_reason=result.skipped_reason,
        model=result.model,
        prompt_version=result.prompt_version,
    )


@router.patch(
    "/{public_id}/cards/{card_public_id}",
    response_model=FlashcardRead,
    summary="Tirar ou devolver um cartão à circulação",
)
async def review_card(
    public_id: str,
    card_public_id: str,
    payload: DeckCardReview,
    actor: DeckWriter,
    db: DbSession,
    context: RequestCtx,
) -> FlashcardRead:
    service = OfficialDeckService(db)
    deck = await service.get(public_id)
    card = await service.set_card_active(
        actor, context, deck, card_public_id, is_active=payload.is_active
    )
    return card_read(card, deck=deck)


@router.post("/{public_id}/publish", response_model=OfficialDeckRead, summary="Publicar baralho")
async def publish_deck(
    public_id: str, actor: DeckWriter, db: DbSession, context: RequestCtx
) -> OfficialDeckRead:
    """Passa pelo portão de auditoria antes de mudar o estado."""
    service = OfficialDeckService(db)
    deck = await service.publish(actor, context, await service.get(public_id))
    return deck_read(await service.view(deck))


@router.post("/{public_id}/archive", response_model=OfficialDeckRead, summary="Arquivar baralho")
async def archive_deck(
    public_id: str, actor: DeckWriter, db: DbSession, context: RequestCtx
) -> OfficialDeckRead:
    service = OfficialDeckService(db)
    deck = await service.archive(actor, context, await service.get(public_id))
    return deck_read(await service.view(deck))


@router.post(
    "/{public_id}/reopen", response_model=OfficialDeckRead, summary="Reabrir baralho arquivado"
)
async def reopen_deck(
    public_id: str, actor: DeckWriter, db: DbSession, context: RequestCtx
) -> OfficialDeckRead:
    service = OfficialDeckService(db)
    deck = await service.reopen(actor, context, await service.get(public_id))
    return deck_read(await service.view(deck))
