"""Repetição espaçada: intervalos, velocidade e a fila que não explode."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.srs import (
    DEFAULT_EASE,
    MAX_INTERVAL,
    CardMemory,
    CardState,
    QueueCard,
    Rating,
    build_queue,
    forecast,
    review,
    speed_adjustment,
)
from app.domain.srs.queue import DEFAULT_DAILY_LIMIT, MAX_SPREAD_DAYS
from app.domain.srs.scheduler import LAPSE_FACTOR, MAX_EASE, MIN_EASE, TARGET_SECONDS

HOJE = date(2026, 8, 24)


def _mature(interval: int = 20, ease: float = DEFAULT_EASE) -> CardMemory:
    return CardMemory(
        state=CardState.REVIEW, ease_factor=ease, interval_days=interval, repetitions=5
    )


# --------------------------------------------------------------------------- #
# Intervalos
# --------------------------------------------------------------------------- #
def test_new_card_walks_through_the_learning_steps() -> None:
    first = review(CardMemory(), Rating.GOOD, today=HOJE)

    assert first.memory.state == CardState.LEARNING
    assert first.interval_days == 1
    assert first.due_on == HOJE + timedelta(days=1)

    second = review(first.memory, Rating.GOOD, today=HOJE)
    assert second.memory.state == CardState.REVIEW
    assert second.memory.repetitions == 1


def test_easy_on_a_new_card_skips_straight_to_review() -> None:
    outcome = review(CardMemory(), Rating.EASY, today=HOJE)

    assert outcome.memory.state == CardState.REVIEW
    assert outcome.interval_days == 3


def test_interval_grows_by_the_ease_factor() -> None:
    outcome = review(_mature(interval=10), Rating.GOOD, time_seconds=TARGET_SECONDS, today=HOJE)

    # 10 dias × facilidade 2,5, sem ajuste de velocidade.
    assert outcome.interval_days == 25
    assert outcome.breakdown["fator_aplicado"] == DEFAULT_EASE
    assert outcome.breakdown["ajuste_de_velocidade"] == 1.0


def test_ratings_are_ordered_by_the_interval_they_produce() -> None:
    base = _mature(interval=10)
    intervals = {
        rating: review(base, rating, time_seconds=TARGET_SECONDS, today=HOJE).interval_days
        for rating in (Rating.AGAIN, Rating.HARD, Rating.GOOD, Rating.EASY)
    }

    assert intervals[Rating.AGAIN] < intervals[Rating.HARD]
    assert intervals[Rating.HARD] < intervals[Rating.GOOD]
    assert intervals[Rating.GOOD] < intervals[Rating.EASY]


def test_ease_factor_stays_inside_its_limits() -> None:
    hard = CardMemory(state=CardState.REVIEW, ease_factor=MIN_EASE, interval_days=5)
    assert review(hard, Rating.AGAIN, today=HOJE).memory.ease_factor == MIN_EASE

    easy = CardMemory(state=CardState.REVIEW, ease_factor=MAX_EASE, interval_days=5)
    assert review(easy, Rating.EASY, today=HOJE).memory.ease_factor == MAX_EASE


def test_interval_never_passes_the_ceiling() -> None:
    outcome = review(_mature(interval=MAX_INTERVAL), Rating.EASY, today=HOJE)

    assert outcome.interval_days == MAX_INTERVAL
    assert outcome.breakdown["teto_aplicado"] == MAX_INTERVAL


def test_every_review_explains_the_interval_it_produced() -> None:
    outcome = review(_mature(interval=10), Rating.GOOD, time_seconds=12, today=HOJE)

    assert outcome.breakdown["resposta"] == Rating.GOOD
    assert outcome.breakdown["intervalo_anterior"] == 10
    assert outcome.breakdown["intervalo_final"] == outcome.interval_days
    assert "facilidade_nova" in outcome.breakdown


def test_invalid_rating_is_rejected() -> None:
    with pytest.raises(ValueError, match="Resposta inválida"):
        review(CardMemory(), "TALVEZ", today=HOJE)


# --------------------------------------------------------------------------- #
# Erro
# --------------------------------------------------------------------------- #
def test_error_drops_the_interval_proportionally_instead_of_resetting() -> None:
    outcome = review(_mature(interval=40), Rating.AGAIN, today=HOJE)

    assert outcome.memory.state == CardState.RELEARNING
    assert outcome.memory.lapses == 1
    assert outcome.interval_days == round(40 * LAPSE_FACTOR)
    assert outcome.is_lapse is True


def test_a_mature_card_missed_keeps_more_ground_than_a_fresh_one() -> None:
    maduro = review(_mature(interval=60), Rating.AGAIN, today=HOJE)
    recente = review(_mature(interval=3), Rating.AGAIN, today=HOJE)

    assert maduro.interval_days > recente.interval_days


def test_error_on_a_card_still_being_learned_goes_back_to_the_same_day() -> None:
    outcome = review(
        CardMemory(state=CardState.LEARNING, interval_days=1), Rating.AGAIN, today=HOJE
    )

    assert outcome.interval_days == 0
    assert outcome.due_on == HOJE


# --------------------------------------------------------------------------- #
# Velocidade
# --------------------------------------------------------------------------- #
def test_answering_fast_and_right_stretches_the_interval() -> None:
    rapido = review(_mature(interval=10), Rating.GOOD, time_seconds=5, today=HOJE)
    lento = review(_mature(interval=10), Rating.GOOD, time_seconds=60, today=HOJE)

    assert rapido.interval_days > lento.interval_days


def test_speed_adjustment_is_bounded_in_both_directions() -> None:
    assert speed_adjustment(1, Rating.GOOD) == 1.15
    assert speed_adjustment(3600, Rating.GOOD) == 0.85


def test_speed_does_not_reward_a_fast_error() -> None:
    # Responder "não lembrei" em 1 segundo não é domínio: é não ter tentado.
    assert speed_adjustment(1, Rating.AGAIN) == 1.0


def test_unmeasured_time_leaves_the_interval_untouched() -> None:
    assert speed_adjustment(0, Rating.GOOD) == 1.0


# --------------------------------------------------------------------------- #
# Fila
# --------------------------------------------------------------------------- #
def _cards(count: int, *, days_late: int = 1, start: int = 1) -> list[QueueCard]:
    return [
        QueueCard(card_id=start + index, due_on=HOJE - timedelta(days=days_late))
        for index in range(count)
    ]


def test_empty_queue_says_the_memory_is_up_to_date() -> None:
    plan = build_queue([], today=HOJE)

    assert plan.today == []
    assert "em dia" in plan.summary


def test_queue_respects_the_daily_ceiling() -> None:
    plan = build_queue(_cards(200), today=HOJE, daily_limit=50)

    assert len(plan.today) == 50
    assert plan.review_count == 50


def test_backlog_is_spread_instead_of_dumped_on_one_day() -> None:
    plan = build_queue(_cards(200), today=HOJE, daily_limit=50)

    assert plan.overdue_count == 200
    assert len(plan.rescheduled) == 150
    # Nenhum reagendamento cai hoje, e nenhum vai além do limite de diluição.
    assert all(item.to_day > HOJE for item in plan.rescheduled)
    assert all((item.to_day - HOJE).days <= MAX_SPREAD_DAYS for item in plan.rescheduled)
    assert "distribuídos pelos próximos dias" in plan.summary


def test_after_an_absence_the_queue_reports_it_in_words() -> None:
    plan = build_queue(
        _cards(120, days_late=10),
        today=HOJE,
        daily_limit=40,
        last_reviewed_on=HOJE - timedelta(days=10),
    )

    assert plan.absence_days == 10
    assert "10 dias sem revisar" in plan.summary
    assert "120 cartão(ões) estavam vencidos" in plan.summary
    assert len(plan.today) == 40


def test_the_most_overdue_cards_come_first() -> None:
    cards = [
        QueueCard(card_id=1, due_on=HOJE - timedelta(days=1)),
        QueueCard(card_id=2, due_on=HOJE - timedelta(days=9)),
        QueueCard(card_id=3, due_on=HOJE - timedelta(days=4)),
    ]
    plan = build_queue(cards, today=HOJE, daily_limit=2)

    assert [card.card_id for card in plan.today] == [2, 3]


def test_priority_score_breaks_the_tie_between_equally_late_cards() -> None:
    cards = [
        QueueCard(card_id=1, due_on=HOJE, priority=10),
        QueueCard(card_id=2, due_on=HOJE, priority=90),
    ]
    plan = build_queue(cards, today=HOJE, daily_limit=1)

    assert [card.card_id for card in plan.today] == [2]


def test_overdue_reviews_come_before_new_cards() -> None:
    cards = [
        *_cards(30),
        *[QueueCard(card_id=100 + index, due_on=HOJE, is_new=True) for index in range(20)],
    ]
    plan = build_queue(cards, today=HOJE, daily_limit=30, new_per_day=15)

    assert plan.review_count == 30
    # O teto já foi ocupado por revisão vencida: nenhum cartão novo entra hoje.
    assert plan.new_count == 0


def test_new_cards_fill_only_what_is_left_under_the_ceiling() -> None:
    cards = [
        *_cards(10),
        *[QueueCard(card_id=100 + index, due_on=HOJE, is_new=True) for index in range(40)],
    ]
    plan = build_queue(cards, today=HOJE, daily_limit=30, new_per_day=15)

    assert plan.review_count == 10
    assert plan.new_count == 15
    assert len(plan.today) == 25


def test_cards_due_in_the_future_are_not_pulled_into_today() -> None:
    plan = build_queue([QueueCard(card_id=1, due_on=HOJE + timedelta(days=3))], today=HOJE)

    assert plan.today == []
    assert plan.overdue_count == 0


def test_forecast_shows_the_load_of_the_coming_days() -> None:
    cards = [
        QueueCard(card_id=1, due_on=HOJE),
        QueueCard(card_id=2, due_on=HOJE + timedelta(days=2)),
        QueueCard(card_id=3, due_on=HOJE + timedelta(days=2)),
    ]
    days = forecast(cards, today=HOJE, days=4)

    assert [item["count"] for item in days] == [1, 0, 2, 0]
    assert days[0]["day"] == HOJE.isoformat()


def test_default_ceiling_is_a_session_a_person_finishes() -> None:
    plan = build_queue(_cards(500), today=HOJE)

    assert len(plan.today) == DEFAULT_DAILY_LIMIT
