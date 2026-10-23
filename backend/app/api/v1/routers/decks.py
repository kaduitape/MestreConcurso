"""Baralhos oficiais pelo lado de quem estuda: ver, entrar e sair.

A assinatura é o ponto inteiro desta rota. Um cartão oficial só entra na fila de
revisão de alguém porque essa pessoa **escolheu** o baralho — não porque a
equipe publicou conteúdo. É o que mantém a fila do candidato sendo sobre o
concurso dele.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.v1.routers.admin_decks import deck_read
from app.schemas.deck import DeckCatalogueRead, OfficialDeckRead
from app.services.decks import OfficialDeckService

router = APIRouter(prefix="/decks", tags=["baralhos oficiais"])


@router.get("", response_model=DeckCatalogueRead, summary="Baralhos do meu edital")
async def catalogue(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DeckCatalogueRead:
    result = await OfficialDeckService(db).catalogue(user, limit=limit, offset=offset)
    return DeckCatalogueRead(
        items=[
            deck_read(item, is_subscribed=item.deck.id in result.subscribed)
            for item in result.items
        ],
        total=result.total,
        scope=result.scope,
        competition_name=result.competition_name,
    )


@router.post(
    "/{public_id}/subscribe", response_model=OfficialDeckRead, summary="Entrar num baralho"
)
async def subscribe(public_id: str, user: CurrentUser, db: DbSession) -> OfficialDeckRead:
    """Os cartões entram na fila respeitando o teto de cartões novos por dia."""
    service = OfficialDeckService(db)
    deck = await service.subscribe(user, public_id)
    return deck_read(await service.view(deck), is_subscribed=True)


@router.delete(
    "/{public_id}/subscribe", response_model=OfficialDeckRead, summary="Sair de um baralho"
)
async def unsubscribe(public_id: str, user: CurrentUser, db: DbSession) -> OfficialDeckRead:
    """Sai da fila; o histórico de revisão de cada cartão continua gravado."""
    service = OfficialDeckService(db)
    deck = await service.unsubscribe(user, public_id)
    return deck_read(await service.view(deck), is_subscribed=False)
