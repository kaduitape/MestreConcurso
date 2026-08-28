"""A sessão de revisão: montar a fila, responder e reagendar.

Toda a matemática vive no domínio (`app/domain/srs`). Aqui só se lê o estado,
chama o cálculo e grava — inclusive o `breakdown`, para que a interface consiga
dizer *por que* o cartão volta em N dias em vez de apresentar o número seco.

A regra que dá nome à fase: **a fila nunca explode**. O teto diário é respeitado
mesmo depois de uma ausência longa, e o excedente é redistribuído com o motivo
declarado, nunca empilhado em silêncio.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.game import GameEvent, GameEventKind
from app.domain.srs import (
    DEFAULT_DAILY_LIMIT,
    DEFAULT_NEW_PER_DAY,
    CardMemory,
    CardState,
    QueueCard,
    QueuePlan,
    build_queue,
    forecast,
    review,
)
from app.models.flashcard import CardMemoryState, Flashcard, FlashcardReview
from app.models.intelligence import UserPriority
from app.models.user import User
from app.repositories.flashcard import (
    CardStateRepository,
    FlashcardRepository,
    FlashcardReviewRepository,
)
from app.services.game_engine import GameEngine

logger = get_logger(__name__)

# Revisão relâmpago: sessão curta, pensada para caber num intervalo de espera.
FLASH_DEFAULT_SIZE = 10
FLASH_MAX_SIZE = 30


@dataclass(frozen=True, slots=True)
class QueueItem:
    state: CardMemoryState
    card: Flashcard
    is_new: bool


@dataclass(frozen=True, slots=True)
class ReviewQueue:
    items: list[QueueItem] = field(default_factory=list)
    plan: QueuePlan | None = None
    total_cards: int = 0
    reviewed_today: int = 0
    upcoming: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReviewResult:
    state: CardMemoryState
    card: Flashcard
    interval_days: int
    due_on: date
    breakdown: dict[str, Any]
    remaining_today: int


class ReviewService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cards = FlashcardRepository(session)
        self.states = CardStateRepository(session)
        self.reviews = FlashcardReviewRepository(session)

    # ------------------------------------------------------------------ #
    # Estado de memória
    # ------------------------------------------------------------------ #
    async def ensure_states(self, user: User, *, today: date | None = None) -> int:
        """Cria o estado inicial dos cartões visíveis que ainda não têm um.

        Cartão novo nasce vencido hoje: é assim que ele entra na fila pela
        primeira vez, respeitando o teto de cartões novos por dia.
        """
        reference = today or datetime.now(UTC).date()
        visible, _ = await self.cards.search(user.id, limit=1000, offset=0)
        existing = await self.states.by_card_ids(user.id, [card.id for card in visible])

        created = 0
        for card in visible:
            if card.id in existing:
                continue
            self.session.add(
                CardMemoryState(
                    user_id=user.id,
                    flashcard_id=card.id,
                    state=CardState.NEW,
                    ease_factor=Decimal("2.500"),
                    interval_days=0,
                    repetitions=0,
                    lapses=0,
                    step_index=0,
                    due_on=reference,
                    postponed_count=0,
                )
            )
            created += 1
        if created:
            await self.session.commit()
        return created

    async def _priorities(self, user: User) -> dict[int, int]:
        rows = (
            await self.session.execute(
                select(UserPriority.subject_id, UserPriority.score).where(
                    UserPriority.user_id == user.id, UserPriority.subject_id.is_not(None)
                )
            )
        ).all()
        return {int(row[0]): int(row[1]) for row in rows}

    # ------------------------------------------------------------------ #
    # Fila
    # ------------------------------------------------------------------ #
    async def queue(
        self,
        user: User,
        *,
        today: date | None = None,
        daily_limit: int = DEFAULT_DAILY_LIMIT,
        new_per_day: int = DEFAULT_NEW_PER_DAY,
        apply_reschedule: bool = True,
    ) -> ReviewQueue:
        reference = today or datetime.now(UTC).date()
        await self.ensure_states(user, today=reference)

        states = list(await self.states.all_states(user.id))
        priorities = await self._priorities(user)

        plan = build_queue(
            [
                QueueCard(
                    card_id=state.flashcard_id,
                    due_on=state.due_on,
                    is_new=state.state == CardState.NEW,
                    priority=priorities.get(state.flashcard.subject_id or -1, 0),
                )
                for state in states
            ],
            today=reference,
            daily_limit=daily_limit,
            new_per_day=new_per_day,
            last_reviewed_on=await self.states.last_review_day(user.id),
        )

        by_card = {state.flashcard_id: state for state in states}

        if apply_reschedule and plan.rescheduled:
            # A diluição é gravada: o cartão realmente muda de dia, e o candidato
            # não reencontra a mesma avalanche amanhã.
            for item in plan.rescheduled:
                state = by_card.get(item.card_id)
                if state is not None:
                    state.due_on = item.to_day
                    state.postponed_count += 1
            await self.session.commit()

        items = [
            QueueItem(
                state=by_card[card.card_id],
                card=by_card[card.card_id].flashcard,
                is_new=card.is_new,
            )
            for card in plan.today
            if card.card_id in by_card
        ]

        return ReviewQueue(
            items=items,
            plan=plan,
            total_cards=len(states),
            reviewed_today=await self.reviews.reviewed_today(user.id, day=reference),
            upcoming=forecast(
                [QueueCard(card_id=state.flashcard_id, due_on=state.due_on) for state in states],
                today=reference,
            ),
        )

    async def flash(
        self, user: User, *, size: int = FLASH_DEFAULT_SIZE, today: date | None = None
    ) -> ReviewQueue:
        """Revisão relâmpago: os cartões mais atrasados, num punhado.

        Não é uma fila diferente — é a mesma fila truncada, para que a sessão
        curta não desalinhe o agendamento.
        """
        limit = max(1, min(size, FLASH_MAX_SIZE))
        full = await self.queue(user, today=today, daily_limit=limit, new_per_day=0)
        return ReviewQueue(
            items=full.items[:limit],
            plan=full.plan,
            total_cards=full.total_cards,
            reviewed_today=full.reviewed_today,
            upcoming=full.upcoming,
        )

    # ------------------------------------------------------------------ #
    # Resposta
    # ------------------------------------------------------------------ #
    async def answer(
        self,
        user: User,
        flashcard_public_id: str,
        *,
        rating: str,
        time_seconds: int = 0,
        today: date | None = None,
    ) -> ReviewResult:
        reference = today or datetime.now(UTC).date()
        card = await self.cards.get_by_public_id(flashcard_public_id, user.id)
        if card is None:
            raise NotFoundError("Cartão não encontrado.")

        state = await self.states.get_for(user.id, card.id)
        if state is None:
            raise ConflictError(
                "Este cartão ainda não entrou na sua fila de revisão.",
                code="card_not_in_queue",
            )

        outcome = review(
            CardMemory(
                state=state.state,
                ease_factor=float(state.ease_factor),
                interval_days=state.interval_days,
                repetitions=state.repetitions,
                lapses=state.lapses,
                step_index=state.step_index,
            ),
            rating,
            time_seconds=max(0, min(time_seconds, 3600)),
            today=reference,
        )

        previous_interval = state.interval_days
        state.state = outcome.memory.state
        state.ease_factor = Decimal(str(round(outcome.memory.ease_factor, 3)))
        state.interval_days = outcome.memory.interval_days
        state.repetitions = outcome.memory.repetitions
        state.lapses = outcome.memory.lapses
        state.step_index = outcome.memory.step_index
        state.due_on = outcome.due_on
        state.last_reviewed_at = datetime.now(UTC)
        state.last_rating = rating
        state.last_breakdown = dict(outcome.breakdown)
        # O cartão foi revisado: o adiamento anterior deixou de importar.
        state.postponed_count = 0

        self.session.add(
            FlashcardReview(
                user_id=user.id,
                flashcard_id=card.id,
                rating=rating,
                time_seconds=max(0, min(time_seconds, 3600)),
                previous_interval_days=previous_interval,
                next_interval_days=outcome.interval_days,
                ease_factor=state.ease_factor,
                due_on=outcome.due_on,
                breakdown=dict(outcome.breakdown),
            )
        )
        await self.session.commit()

        remaining = len(
            [
                item
                for item in await self.states.due_states(user.id, until=reference)
                if item.flashcard_id != card.id
            ]
        )
        await GameEngine(self.session).award(
            user,
            GameEvent(
                GameEventKind.FLASHCARDS_REVIEWED,
                {"cards": 1.0},
                reference=f"{card.public_id}:{reference.isoformat()}",
            ),
            today=reference,
        )

        logger.info(
            "review.answered",
            user=user.public_id,
            rating=rating,
            interval=outcome.interval_days,
        )
        return ReviewResult(
            state=state,
            card=card,
            interval_days=outcome.interval_days,
            due_on=outcome.due_on,
            breakdown=dict(outcome.breakdown),
            remaining_today=remaining,
        )

    # ------------------------------------------------------------------ #
    # Estatística
    # ------------------------------------------------------------------ #
    async def stats(self, user: User, *, today: date | None = None) -> dict[str, Any]:
        """Números reais da memória do candidato — nenhum deles estimado."""
        reference = today or datetime.now(UTC).date()
        states = list(await self.states.all_states(user.id))
        ratings = await self.reviews.counts_by_rating(user.id)
        total_reviews = sum(ratings.values())

        by_state: dict[str, int] = {}
        for state in states:
            by_state[state.state] = by_state.get(state.state, 0) + 1

        mature = [state for state in states if state.interval_days >= 21]
        recalled = total_reviews - ratings.get("AGAIN", 0)

        return {
            "total_cards": len(states),
            "by_state": by_state,
            "due_today": len([item for item in states if item.due_on <= reference]),
            "mature_cards": len(mature),
            "total_reviews": total_reviews,
            "reviewed_today": await self.reviews.reviewed_today(user.id, day=reference),
            # Sem revisão registrada não há taxa: nula, não zero.
            "recall_rate": (round(recalled / total_reviews, 4) if total_reviews else None),
            "ratings": ratings,
            "upcoming": forecast(
                [QueueCard(card_id=item.flashcard_id, due_on=item.due_on) for item in states],
                today=reference,
                days=14,
            ),
        }

    async def postpone_all(self, user: User, *, days: int = 1) -> int:
        """Adia a fila inteira, quando o candidato não vai conseguir revisar hoje.

        Existe para que a alternativa a "não revisar" não seja acumular em
        silêncio: o adiamento é uma escolha declarada.
        """
        reference = datetime.now(UTC).date()
        states = await self.states.due_states(user.id, until=reference)
        for state in states:
            state.due_on = reference + timedelta(days=max(1, days))
            state.postponed_count += 1
        await self.session.commit()
        return len(states)
