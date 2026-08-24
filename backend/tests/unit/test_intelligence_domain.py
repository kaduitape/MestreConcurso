"""Camada de inteligência: incidência, Priority Score, DNA da banca e erros."""

from __future__ import annotations

from app.domain.intelligence import (
    ErrorRecord,
    PriorityInput,
    ProfileSample,
    QuestionSample,
    adjust_shares_by_priority,
    build_board_profile,
    build_notebook,
    compute_incidence,
    compute_priority,
    rank_priorities,
)
from app.domain.intelligence.incidence import MIN_BOARD_QUESTIONS, MIN_SCOPE_QUESTIONS
from app.domain.intelligence.priority import MAX_SCORE, MIN_ATTEMPTS


def _questions(
    count: int, *, subject: str = "Direito Penal", year: int = 2024
) -> list[QuestionSample]:
    return [
        QuestionSample(
            subject_id=hash(subject) % 1000,
            subject_name=subject,
            year=year,
            exam_id=year,
        )
        for _ in range(count)
    ]


# --------------------------------------------------------------------------- #
# Mapa de incidência
# --------------------------------------------------------------------------- #
def test_incidence_refuses_to_publish_without_sample() -> None:
    report = compute_incidence(_questions(MIN_BOARD_QUESTIONS - 1))

    assert report.rows == []
    assert report.blocked_reason is not None
    assert str(MIN_BOARD_QUESTIONS) in report.blocked_reason


def test_incidence_shares_sum_to_the_whole_sample() -> None:
    questions = _questions(30, subject="Direito Penal") + _questions(10, subject="Português")
    report = compute_incidence(questions)

    assert report.board_questions_count == 40
    assert report.blocked_reason is None
    assert sum(row.questions_count for row in report.rows) == 40
    assert abs(sum(row.incidence_pct for row in report.rows) - 1.0) < 1e-6
    # Ordenação: o que mais cai vem primeiro.
    assert report.rows[0].subject_name == "Direito Penal"


def test_scope_below_the_minimum_is_marked_insufficient() -> None:
    questions = _questions(38, subject="Direito Penal") + _questions(
        MIN_SCOPE_QUESTIONS - 1, subject="Arquivologia"
    )
    report = compute_incidence(questions)

    rare = next(row for row in report.rows if row.subject_name == "Arquivologia")
    assert rare.is_sufficient is False
    assert rare.insufficient_reason is not None
    # Sem amostra, não se afirma tendência.
    assert rare.trend is None


def test_trend_needs_two_years_to_exist() -> None:
    single_year = compute_incidence(_questions(40, year=2024))
    assert single_year.rows[0].trend is None

    growing = compute_incidence(
        _questions(10, subject="Direito Penal", year=2020)
        + _questions(20, subject="Direito Penal", year=2024)
        + _questions(20, subject="Português", year=2020)
        + _questions(5, subject="Português", year=2024)
    )
    penal = next(row for row in growing.rows if row.subject_name == "Direito Penal")
    portugues = next(row for row in growing.rows if row.subject_name == "Português")
    assert penal.trend is not None and penal.trend > 0
    assert portugues.trend is not None and portugues.trend < 0


# --------------------------------------------------------------------------- #
# Priority Score
# --------------------------------------------------------------------------- #
def test_contributions_always_sum_to_the_displayed_score() -> None:
    score = compute_priority(
        PriorityInput(
            scope_key="subject:1",
            label="Direito Penal",
            incidence_pct=0.18,
            notice_share=0.22,
            accuracy=0.43,
            attempts=40,
            days_since_studied=9,
            completion=0.3,
        )
    )

    assert score.contributions_sum == score.score
    assert 0 < score.score <= MAX_SCORE
    assert score.missing_signals == []
    assert score.coverage == 1.0
    # Cada parcela explica de onde saiu.
    assert all(item.detail for item in score.contributions)


def test_missing_signal_is_declared_and_worth_zero() -> None:
    score = compute_priority(
        PriorityInput(scope_key="subject:2", label="Informática", notice_share=0.1)
    )

    assert score.contributions_sum == score.score
    assert set(score.missing_signals) == {
        "incidencia_na_banca",
        "seu_desempenho",
        "tempo_sem_estudar",
        "conteudo_pendente",
    }
    zeroed = {item.key: item.points for item in score.contributions}
    assert zeroed["incidencia_na_banca"] == 0
    assert zeroed["seu_desempenho"] == 0
    assert score.coverage < 1.0


def test_small_attempt_sample_does_not_feed_the_performance_signal() -> None:
    score = compute_priority(
        PriorityInput(
            scope_key="subject:3",
            label="Português",
            accuracy=0.0,
            attempts=MIN_ATTEMPTS - 1,
        )
    )

    performance = next(item for item in score.contributions if item.key == "seu_desempenho")
    assert performance.points == 0
    assert "seu_desempenho" in score.missing_signals
    assert str(MIN_ATTEMPTS) in performance.detail


def test_worse_performance_raises_the_score() -> None:
    base = {
        "incidence_pct": 0.2,
        "notice_share": 0.2,
        "days_since_studied": 5,
        "completion": 0.5,
    }
    weak = compute_priority(
        PriorityInput(scope_key="a", label="A", accuracy=0.30, attempts=50, **base)
    )
    strong = compute_priority(
        PriorityInput(scope_key="b", label="B", accuracy=0.90, attempts=50, **base)
    )

    assert weak.score > strong.score


def test_ranking_puts_the_most_urgent_first() -> None:
    scores = rank_priorities(
        [
            PriorityInput(
                scope_key="s1",
                label="Tranquila",
                incidence_pct=0.05,
                notice_share=0.05,
                accuracy=0.95,
                attempts=30,
                days_since_studied=1,
                completion=0.9,
            ),
            PriorityInput(
                scope_key="s2",
                label="Urgente",
                incidence_pct=0.25,
                notice_share=0.25,
                accuracy=0.20,
                attempts=30,
                days_since_studied=30,
                completion=0.0,
            ),
        ]
    )

    assert [item.label for item in scores] == ["Urgente", "Tranquila"]
    assert all(item.contributions_sum == item.score for item in scores)


def test_priority_adjustment_is_bounded_and_keeps_the_total() -> None:
    shares = {"penal": 0.5, "portugues": 0.3, "informatica": 0.2}
    adjusted = adjust_shares_by_priority(shares, {"penal": 90, "portugues": 50, "informatica": 10})

    assert abs(sum(adjusted.values()) - 1.0) < 1e-9
    assert adjusted["penal"] > shares["penal"]
    assert adjusted["informatica"] < shares["informatica"]
    # O ajuste inclina, não vira a mesa: a ordem do edital é preservada.
    assert adjusted["penal"] > adjusted["portugues"] > adjusted["informatica"]


def test_subject_without_score_keeps_its_baseline_share() -> None:
    shares = {"penal": 0.6, "novata": 0.4}
    adjusted = adjust_shares_by_priority(shares, {})

    assert adjusted == shares


# --------------------------------------------------------------------------- #
# DNA da banca
# --------------------------------------------------------------------------- #
def _profile_samples(count: int, **overrides: object) -> list[ProfileSample]:
    defaults: dict[str, object] = {
        "subject_id": 1,
        "subject_name": "Direito Penal",
        "difficulty": "MEDIUM",
        "kind": "MULTIPLE_CHOICE",
        "alternatives_count": 5,
        "year": 2024,
        "exam_id": 7,
    }
    defaults.update(overrides)
    return [ProfileSample(**defaults) for _ in range(count)]  # type: ignore[arg-type]


def test_board_profile_needs_a_minimum_sample() -> None:
    profile = build_board_profile(_profile_samples(10))

    assert profile.metrics == []
    assert profile.blocked_reason is not None


def test_board_profile_reports_distribution_with_its_sample() -> None:
    profile = build_board_profile(
        _profile_samples(30, difficulty="HARD") + _profile_samples(10, difficulty="EASY")
    )

    assert profile.blocked_reason is None
    assert profile.sample_questions == 40
    mix = next(item for item in profile.metrics if item.slug == "difficulty_mix")
    assert mix.detail == {"EASY": 0.25, "HARD": 0.75}
    assert mix.sample_questions == 40


# --------------------------------------------------------------------------- #
# Caderno de erros
# --------------------------------------------------------------------------- #
def test_empty_notebook_explains_what_is_missing() -> None:
    notebook = build_notebook([])

    assert notebook.total == 0
    assert notebook.by_cause == []
    assert notebook.notes


def test_notebook_groups_causes_and_suggests_the_action_of_the_top_cause() -> None:
    records = [
        ErrorRecord(cause="RUSH", subject_id=1, subject_name="Português") for _ in range(6)
    ] + [ErrorRecord(cause="FORGETTING", subject_id=2, subject_name="Direito Penal")]
    notebook = build_notebook(records)

    assert notebook.total == 7
    assert notebook.by_cause[0].cause == "RUSH"
    assert notebook.by_cause[0].count == 6
    assert abs(sum(item.share for item in notebook.by_cause) - 1.0) < 1e-6
    assert notebook.insights
    assert "6 dos seus 7 erros" in notebook.insights[0]
    assert notebook.by_cause[0].action in notebook.insights[0]


def test_few_errors_do_not_produce_a_predominant_cause() -> None:
    notebook = build_notebook(
        [ErrorRecord(cause="TRAP", subject_id=1, subject_name="Português") for _ in range(2)]
    )

    assert notebook.insights == []
    assert any("predominante" in note for note in notebook.notes)


def test_tie_between_causes_has_no_dominant_in_the_subject() -> None:
    records = [
        ErrorRecord(cause="RUSH", subject_id=1, subject_name="Português"),
        ErrorRecord(cause="TRAP", subject_id=1, subject_name="Português"),
        ErrorRecord(cause="RUSH", subject_id=1, subject_name="Português"),
        ErrorRecord(cause="TRAP", subject_id=1, subject_name="Português"),
    ]
    notebook = build_notebook(records)

    subject = notebook.by_subject[0]
    assert subject.count == 4
    assert subject.dominant_cause is None


def test_trap_radar_only_points_a_pattern_with_repetition() -> None:
    once = build_notebook(
        [
            ErrorRecord(
                cause="TRAP",
                subject_id=1,
                subject_name="Português",
                trap_slug="generalizacao",
                trap_name="Generalização indevida",
            )
        ]
    )
    assert once.traps == []
    assert any("radar" in note.lower() for note in once.notes)

    repeated = build_notebook(
        [
            ErrorRecord(
                cause="TRAP",
                subject_id=1,
                subject_name="Português",
                trap_slug="generalizacao",
                trap_name="Generalização indevida",
            )
            for _ in range(4)
        ]
    )
    assert repeated.traps[0].slug == "generalizacao"
    assert repeated.traps[0].count == 4
