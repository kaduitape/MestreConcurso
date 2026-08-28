"""Mestre Game Engine: XP, antiabuso, níveis, rank, sequência e missões."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from app.domain.game import (
    ACHIEVEMENTS_BY_SLUG,
    RULES_BY_KEY,
    DayRecord,
    GameEvent,
    GameEventKind,
    MissionSignals,
    RankInput,
    build_streak,
    compute_rank,
    evaluate,
    generate_daily,
    level_for_xp,
    qualifies,
    score_event,
    tier_for,
    valid_questions,
    xp_for_level,
)
from app.domain.game.ranks import MIN_ATTEMPTS, MIN_REVIEWS
from app.domain.game.streak import MIN_FOCUS_MINUTES, SHIELDS_PER_MONTH
from app.domain.game.xp import (
    LOW_ACCURACY_MULTIPLIER,
    MIN_SECONDS_PER_QUESTION,
    MIN_SIMULATION_QUESTIONS,
)
from app.domain.game.xp import (
    MIN_FOCUS_MINUTES as XP_MIN_FOCUS,
)

HOJE = date(2026, 8, 25)


def _rule(kind: str):
    return RULES_BY_KEY[kind]


# --------------------------------------------------------------------------- #
# XP
# --------------------------------------------------------------------------- #
def test_study_xp_is_proportional_to_focus_time() -> None:
    award = score_event(
        GameEvent(GameEventKind.STUDY_SESSION, {"focus_minutes": 30}),
        _rule(GameEventKind.STUDY_SESSION),
    )
    assert award.amount == 100

    half = score_event(
        GameEvent(GameEventKind.STUDY_SESSION, {"focus_minutes": 15}),
        _rule(GameEventKind.STUDY_SESSION),
    )
    assert half.amount == 50


def test_very_short_session_earns_nothing() -> None:
    award = score_event(
        GameEvent(GameEventKind.STUDY_SESSION, {"focus_minutes": XP_MIN_FOCUS - 1}),
        _rule(GameEventKind.STUDY_SESSION),
    )

    assert award.amount == 0
    assert str(XP_MIN_FOCUS) in award.reason


def test_daily_cap_zeroes_the_excess_and_explains_it() -> None:
    rule = _rule(GameEventKind.STUDY_SESSION)
    award = score_event(
        GameEvent(GameEventKind.STUDY_SESSION, {"focus_minutes": 60}),
        rule,
        earned_today=rule.daily_cap - 50,
    )

    assert award.amount == 50
    assert award.capped is True
    assert award.cap_reason is not None
    # O corte é explicado, e o texto deixa claro que o estudo continua valendo.
    assert "teto diário" in award.cap_reason
    assert "continua contando" in award.cap_reason


def test_cap_already_reached_gives_zero() -> None:
    rule = _rule(GameEventKind.QUESTIONS_ANSWERED)
    award = score_event(
        GameEvent(GameEventKind.QUESTIONS_ANSWERED, {"questions": 10}),
        rule,
        earned_today=rule.daily_cap,
    )

    assert award.amount == 0
    assert award.capped is True


def test_disabled_rule_stops_scoring_without_breaking() -> None:
    rule = replace(_rule(GameEventKind.STUDY_SESSION), is_enabled=False)
    disabled = rule
    award = score_event(GameEvent(GameEventKind.STUDY_SESSION, {"focus_minutes": 60}), disabled)

    assert award.amount == 0
    assert "desativada" in award.reason


def test_difficulty_modulates_question_xp() -> None:
    facil = score_event(
        GameEvent(GameEventKind.QUESTIONS_ANSWERED, {"questions": 10, "difficulty": "EASY"}),
        _rule(GameEventKind.QUESTIONS_ANSWERED),
    )
    dificil = score_event(
        GameEvent(GameEventKind.QUESTIONS_ANSWERED, {"questions": 10, "difficulty": "HARD"}),
        _rule(GameEventKind.QUESTIONS_ANSWERED),
    )

    assert facil.amount < dificil.amount
    assert facil.multiplier == 0.7
    assert dificil.multiplier == 1.3


def test_low_accuracy_batch_earns_less_and_says_why() -> None:
    award = score_event(
        GameEvent(
            GameEventKind.QUESTIONS_ANSWERED,
            {"questions": 20, "difficulty": "MEDIUM", "accuracy": 0.2},
        ),
        _rule(GameEventKind.QUESTIONS_ANSWERED),
    )

    assert award.multiplier == LOW_ACCURACY_MULTIPLIER
    assert "volume sem acerto não é aprendizado" in award.reason


def test_tiny_simulation_does_not_score() -> None:
    award = score_event(
        GameEvent(GameEventKind.SIMULATION_FINISHED, {"questions": MIN_SIMULATION_QUESTIONS - 1}),
        _rule(GameEventKind.SIMULATION_FINISHED),
    )

    assert award.amount == 0
    assert str(MIN_SIMULATION_QUESTIONS) in award.reason


def test_fast_answers_and_repeats_are_dropped_from_the_count() -> None:
    count, accuracy, difficulty = valid_questions(
        [
            {"question_id": 1, "time_seconds": 30, "is_correct": 1, "difficulty": "MEDIUM"},
            # Rápida demais: não deu tempo de ler o enunciado.
            {"question_id": 2, "time_seconds": MIN_SECONDS_PER_QUESTION - 1, "is_correct": 1},
            # Repetida no mesmo dia.
            {"question_id": 1, "time_seconds": 40, "is_correct": 1, "difficulty": "MEDIUM"},
            {"question_id": 3, "time_seconds": 25, "is_correct": 0, "difficulty": "MEDIUM"},
        ]
    )

    assert count == 2
    assert accuracy == 0.5
    assert difficulty == "MEDIUM"


def test_no_valid_question_reports_no_accuracy() -> None:
    count, accuracy, _ = valid_questions([{"question_id": 1, "time_seconds": 1}])

    assert count == 0
    assert accuracy is None


# --------------------------------------------------------------------------- #
# Níveis
# --------------------------------------------------------------------------- #
def test_level_starts_at_one_and_grows_with_xp() -> None:
    assert level_for_xp(0).level == 1
    assert level_for_xp(0).xp_into_level == 0
    assert level_for_xp(xp_for_level(1)).level == 2


def test_level_progress_reports_what_is_missing() -> None:
    progress = level_for_xp(xp_for_level(1) + 100)

    assert progress.level == 2
    assert progress.xp_into_level == 100
    assert progress.xp_for_next == xp_for_level(2)
    assert 0 < progress.ratio < 1


def test_level_curve_is_strictly_increasing() -> None:
    steps = [xp_for_level(level) for level in range(1, 20)]
    assert steps == sorted(steps)
    assert steps[0] < steps[-1]


def test_max_level_is_capped() -> None:
    progress = level_for_xp(999_999_999)

    assert progress.level == 100
    assert progress.is_max is True
    assert progress.xp_for_next is None


# --------------------------------------------------------------------------- #
# Rank
# --------------------------------------------------------------------------- #
def test_rank_components_sum_exactly_to_the_score() -> None:
    result = compute_rank(
        RankInput(
            accuracy=0.71,
            attempts=200,
            retention=0.82,
            reviews=100,
            coverage=0.46,
            has_plan=True,
            simulation_accuracy=0.68,
            simulations=3,
            active_days=14,
        )
    )

    assert result.components_sum == result.score
    assert result.missing_signals == []
    assert result.coverage == 1.0
    assert result.slug == "OURO"


def test_missing_signal_is_worth_zero_and_declared() -> None:
    result = compute_rank(RankInput(accuracy=0.9, attempts=MIN_ATTEMPTS - 1))

    assert result.components_sum == result.score
    assert "acerto" in result.missing_signals
    assert result.slug == "FERRO"
    acerto = next(item for item in result.components if item.key == "acerto")
    assert acerto.points == 0.0
    assert acerto.available is False
    assert str(MIN_ATTEMPTS) in acerto.detail


def test_a_brand_new_candidate_is_iron_because_there_is_nothing_to_measure() -> None:
    result = compute_rank(RankInput())

    assert result.slug == "FERRO"
    assert result.score == 0.0
    assert len(result.missing_signals) == 5
    assert result.coverage == 0.0


def test_xp_never_enters_the_rank() -> None:
    # A entrada do rank sequer aceita XP: a fórmula não tem onde encaixá-lo.
    assert not hasattr(RankInput(), "xp_total")


def test_rank_can_fall_when_performance_falls() -> None:
    strong = compute_rank(
        RankInput(
            accuracy=0.9,
            attempts=200,
            retention=0.9,
            reviews=100,
            coverage=0.9,
            has_plan=True,
            simulation_accuracy=0.9,
            simulations=5,
            active_days=28,
        )
    )
    weak = compute_rank(
        RankInput(
            accuracy=0.4,
            attempts=200,
            retention=0.5,
            reviews=100,
            coverage=0.3,
            has_plan=True,
            simulation_accuracy=0.4,
            simulations=5,
            active_days=8,
        )
    )

    assert strong.score > weak.score
    assert tier_for(strong.score).min_score > tier_for(weak.score).min_score


def test_retention_needs_its_own_sample() -> None:
    result = compute_rank(RankInput(retention=1.0, reviews=MIN_REVIEWS - 1))

    assert "retencao" in result.missing_signals
    retencao = next(item for item in result.components if item.key == "retencao")
    assert retencao.points == 0.0


def test_progress_to_next_tier_is_reported() -> None:
    result = compute_rank(
        RankInput(
            accuracy=0.71,
            attempts=200,
            retention=0.82,
            reviews=100,
            coverage=0.46,
            has_plan=True,
            simulation_accuracy=0.68,
            simulations=3,
            active_days=14,
        )
    )

    assert result.next_tier is not None
    assert result.next_tier.slug == "PLATINA"
    assert 0 <= result.progress_to_next <= 1


# --------------------------------------------------------------------------- #
# Sequência
# --------------------------------------------------------------------------- #
def test_only_useful_study_qualifies_a_day() -> None:
    assert qualifies(MIN_FOCUS_MINUTES, 0, False) is True
    assert qualifies(0, 3, False) is True
    assert qualifies(0, 0, True) is True
    # Abrir o aplicativo não é estudar.
    assert qualifies(5, 1, False) is False


def _days(count: int, *, until: date = HOJE) -> list[DayRecord]:
    return [DayRecord(day=until - timedelta(days=offset), minutes=30) for offset in range(count)]


def test_consecutive_days_build_the_streak() -> None:
    state = build_streak(_days(5), today=HOJE)

    assert state.current == 5
    assert state.longest == 5
    assert "5 dias seguidos" in state.message


def test_today_still_open_does_not_break_the_streak() -> None:
    # Ontem valeu, hoje ainda não foi cumprido: a contagem não pune o dia aberto.
    state = build_streak(_days(3, until=HOJE - timedelta(days=1)), today=HOJE)

    assert state.current == 3


def test_a_shield_covers_one_missed_day() -> None:
    records = [
        DayRecord(day=HOJE, minutes=30),
        # HOJE-1 não existe: dia perdido.
        DayRecord(day=HOJE - timedelta(days=2), minutes=30),
        DayRecord(day=HOJE - timedelta(days=3), minutes=30),
    ]
    state = build_streak(records, today=HOJE, shields_left=SHIELDS_PER_MONTH)

    assert state.current == 3
    assert state.shields_left == SHIELDS_PER_MONTH - 1
    assert state.shielded_days == [HOJE - timedelta(days=1)]
    assert "proteção cobriu" in state.message


def test_without_shields_the_streak_breaks_without_drama() -> None:
    records = [
        DayRecord(day=HOJE, minutes=30),
        DayRecord(day=HOJE - timedelta(days=2), minutes=30),
    ]
    state = build_streak(records, today=HOJE, shields_left=0)

    assert state.current == 1
    assert state.shielded_days == []


def test_broken_streak_keeps_the_record_and_avoids_threatening_language() -> None:
    records = [DayRecord(day=HOJE - timedelta(days=10 + offset), minutes=30) for offset in range(6)]
    state = build_streak(records, today=HOJE, shields_left=0)

    assert state.current == 0
    assert state.longest == 6
    assert "recorde" in state.message
    for word in ("perdeu", "perdendo", "cuidado", "atenção"):
        assert word not in state.message.lower()


def test_history_covers_the_last_two_weeks() -> None:
    state = build_streak(_days(3), today=HOJE)

    assert len(state.history) == 14
    assert state.history[-1]["day"] == HOJE.isoformat()
    assert state.history[-1]["qualified"] is True


# --------------------------------------------------------------------------- #
# Missões
# --------------------------------------------------------------------------- #
def test_missions_follow_the_urgency_order() -> None:
    missions = generate_daily(
        MissionSignals(
            due_cards=24,
            unclassified_errors=11,
            top_subject="Constitucional",
            top_subject_score=78,
            pending_tasks=2,
            has_plan=True,
        )
    )

    assert [item.kind for item in missions] == [
        "REVIEW_CARDS",
        "CLASSIFY_ERRORS",
        "STUDY_SUBJECT",
        "COMPLETE_TASKS",
    ]


def test_every_mission_carries_the_number_that_generated_it() -> None:
    missions = generate_daily(
        MissionSignals(due_cards=24, top_subject="Penal", top_subject_score=61, has_plan=True)
    )

    assert all(item.rationale for item in missions)
    assert "24 cartão(ões) venceram" in missions[0].rationale
    assert "Priority Score 61" in missions[1].rationale


def test_without_signals_the_fallback_is_volume_of_questions() -> None:
    missions = generate_daily(MissionSignals(has_plan=True))

    assert len(missions) == 1
    assert missions[0].kind == "ANSWER_QUESTIONS"
    assert missions[0].rationale


def test_without_an_active_plan_no_mission_is_invented() -> None:
    assert generate_daily(MissionSignals(due_cards=10, has_plan=False)) == []


def test_daily_missions_are_capped() -> None:
    missions = generate_daily(
        MissionSignals(
            due_cards=50,
            unclassified_errors=20,
            top_subject="Penal",
            top_subject_score=90,
            pending_tasks=5,
            has_plan=True,
        )
    )

    assert len(missions) <= 4


# --------------------------------------------------------------------------- #
# Conquistas
# --------------------------------------------------------------------------- #
def test_achievement_unlocks_on_the_real_metric() -> None:
    result = evaluate({"current_streak": 7}, already_unlocked=set())

    slugs = [item.slug for item in result.unlocked]
    assert "disciplina-de-ferro" in slugs


def test_guarded_achievement_needs_both_conditions() -> None:
    volume_only = evaluate({"questions_answered": 150, "accuracy": 0.5}, already_unlocked=set())
    assert "atirador-de-elite" not in [item.slug for item in volume_only.unlocked]

    both = evaluate({"questions_answered": 150, "accuracy": 0.85}, already_unlocked=set())
    assert "atirador-de-elite" in [item.slug for item in both.unlocked]


def test_blocked_guard_explains_itself_instead_of_showing_false_progress() -> None:
    result = evaluate({"questions_answered": 150, "accuracy": 0.5}, already_unlocked=set())
    elite = next(item for item in result.progress if item.spec.slug == "atirador-de-elite")

    assert elite.unlocked is False
    assert elite.ratio is None
    assert elite.blocked_reason is not None


def test_already_unlocked_is_not_granted_twice() -> None:
    result = evaluate({"current_streak": 30}, already_unlocked={"disciplina-de-ferro"})

    assert "disciplina-de-ferro" not in [item.slug for item in result.unlocked]
    assert "constancia-de-aco" in [item.slug for item in result.unlocked]


def test_secret_achievements_exist_and_are_marked() -> None:
    secrets = [item for item in ACHIEVEMENTS_BY_SLUG.values() if item.is_secret]

    assert secrets
    assert all(item.xp_reward > 0 for item in secrets)


def test_progress_is_reported_for_visible_achievements() -> None:
    result = evaluate({"questions_answered": 40}, already_unlocked=set())
    cem = next(item for item in result.progress if item.spec.slug == "cem-questoes")

    assert cem.current == 40
    assert cem.ratio == 0.4
    assert cem.unlocked is False
