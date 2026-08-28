"""Correção de simulado: contagem, agrupamento e diagnóstico."""

from __future__ import annotations

from app.domain.questions import (
    AnswerInput,
    QuestionInfo,
    adaptive_difficulty,
    correct_attempt,
    distribute_by_weight,
)
from app.domain.questions.correction import build_recommendations

QUESTIONS = [
    QuestionInfo(1, 10, "Direito Penal", "MEDIUM", "A"),
    QuestionInfo(2, 10, "Direito Penal", "HARD", "B"),
    QuestionInfo(3, 10, "Direito Penal", "EASY", "C"),
    QuestionInfo(4, 20, "Português", "MEDIUM", "D"),
    QuestionInfo(5, 20, "Português", "MEDIUM", "A"),
    QuestionInfo(6, 20, "Português", "EASY", "B"),
]


def test_counts_correct_wrong_and_blank() -> None:
    analysis = correct_attempt(
        [
            AnswerInput(1, "A", 60),
            AnswerInput(2, "C", 120),
            AnswerInput(3, None, 10),
            AnswerInput(4, "D", 45),
            AnswerInput(5, "A", 30),
            AnswerInput(6, "B", 20),
        ],
        QUESTIONS,
    )

    assert analysis.total == 6
    assert analysis.correct == 4
    assert analysis.wrong == 1
    assert analysis.blank == 1
    assert analysis.accuracy == round(4 / 6, 4)
    assert analysis.score == round(4 / 6 * 100, 2)


def test_unanswered_question_counts_as_blank() -> None:
    # Questão que nem chegou a ser exibida entra como branco, não como erro.
    analysis = correct_attempt([AnswerInput(1, "A", 30)], QUESTIONS)
    assert analysis.blank == 5
    assert analysis.wrong == 0


def test_breakdown_by_subject() -> None:
    analysis = correct_attempt(
        [
            AnswerInput(1, "A", 60),
            AnswerInput(2, "X", 60),
            AnswerInput(3, "X", 60),
            AnswerInput(4, "D", 30),
            AnswerInput(5, "A", 30),
            AnswerInput(6, "B", 30),
        ],
        QUESTIONS,
    )
    by_name = {item.subject_name: item for item in analysis.by_subject}

    assert by_name["Direito Penal"].correct == 1
    assert by_name["Direito Penal"].wrong == 2
    assert by_name["Direito Penal"].accuracy == round(1 / 3, 4)
    assert by_name["Português"].accuracy == 1.0
    assert by_name["Direito Penal"].average_time_seconds == 60


def test_breakdown_by_difficulty() -> None:
    analysis = correct_attempt(
        [AnswerInput(question.question_id, question.correct_letter, 30) for question in QUESTIONS],
        QUESTIONS,
    )
    levels = {item.difficulty: item for item in analysis.by_difficulty}
    assert levels["EASY"].total == 2
    assert levels["HARD"].accuracy == 1.0


def test_weak_subject_needs_minimum_sample() -> None:
    questions = [
        QuestionInfo(1, 10, "Informática", "MEDIUM", "A"),
        QuestionInfo(2, 10, "Informática", "MEDIUM", "B"),
    ]
    analysis = correct_attempt([AnswerInput(1, "X", 30), AnswerInput(2, "X", 30)], questions)
    # 0% de acerto em duas questões não sustenta rotular a disciplina como fraca.
    assert analysis.weakest_subjects == []


def test_weak_subject_is_reported_with_enough_sample() -> None:
    analysis = correct_attempt(
        [
            AnswerInput(1, "X", 30),
            AnswerInput(2, "X", 30),
            AnswerInput(3, "X", 30),
            AnswerInput(4, "D", 30),
            AnswerInput(5, "A", 30),
            AnswerInput(6, "B", 30),
        ],
        QUESTIONS,
    )
    assert analysis.weakest_subjects == ["Direito Penal"]
    assert analysis.strongest_subjects == ["Português"]


def test_comparison_only_when_history_exists() -> None:
    without = correct_attempt([AnswerInput(1, "A", 10)], QUESTIONS)
    assert without.previous_accuracy is None
    assert without.accuracy_delta is None

    with_history = correct_attempt(
        [AnswerInput(question.question_id, question.correct_letter, 10) for question in QUESTIONS],
        QUESTIONS,
        previous_accuracy=0.5,
    )
    assert with_history.accuracy_delta == 0.5


def test_timing_is_aggregated() -> None:
    analysis = correct_attempt(
        [AnswerInput(question.question_id, "A", 60) for question in QUESTIONS], QUESTIONS
    )
    assert analysis.total_time_seconds == 360
    assert analysis.average_time_seconds == 60


def test_recommendations_cite_the_numbers() -> None:
    analysis = correct_attempt(
        [
            AnswerInput(1, "X", 200),
            AnswerInput(2, "X", 200),
            AnswerInput(3, "X", 200),
            AnswerInput(4, "D", 200),
            AnswerInput(5, "A", 200),
            AnswerInput(6, "B", 200),
        ],
        QUESTIONS,
    )
    joined = " ".join(analysis.recommendations)
    assert "Direito Penal: 0 de 3" in joined
    assert "acima do ritmo de prova" in joined


def test_blank_recommendation_appears_above_ten_percent() -> None:
    messages = build_recommendations([], blank=3, total=10, average_time=60)
    assert any("em branco" in message for message in messages)


def test_good_performance_gets_a_neutral_message() -> None:
    messages = build_recommendations([], blank=0, total=10, average_time=60)
    assert messages == ["Desempenho consistente nesta execução; siga o plano."]


def test_empty_attempt_does_not_break() -> None:
    analysis = correct_attempt([], [])
    assert analysis.total == 0
    assert analysis.score == 0.0
    assert analysis.recommendations


# --------------------------------------------------------------------------- #
# Composição do simulado
# --------------------------------------------------------------------------- #
def test_distribution_uses_declared_question_counts() -> None:
    quotas = distribute_by_weight(
        [(1, "Penal", 3, 20), (2, "Português", 2, 20), (3, "Informática", 1, 10)], 50
    )
    assert sum(quota.questions for quota in quotas) == 50
    by_name = {quota.subject_name: quota.questions for quota in quotas}
    # 20/20/10 declarados no edital → proporção 40%/40%/20%.
    assert by_name["Penal"] == 20
    assert by_name["Informática"] == 10


def test_distribution_falls_back_to_weight() -> None:
    quotas = distribute_by_weight([(1, "Penal", 3, None), (2, "Português", 1, None)], 40)
    by_name = {quota.subject_name: quota.questions for quota in quotas}
    assert by_name["Penal"] == 30
    assert by_name["Português"] == 10


def test_distribution_gives_at_least_one_question_per_subject() -> None:
    quotas = distribute_by_weight([(1, "Penal", 10, 100), (2, "Ética", 1, 1)], 5)
    assert all(quota.questions >= 1 for quota in quotas)


def test_distribution_handles_edge_cases() -> None:
    assert distribute_by_weight([], 10) == []
    assert distribute_by_weight([(1, "Penal", 1, 10)], 0) == []


def test_adaptive_difficulty_moves_after_two_in_a_row() -> None:
    assert adaptive_difficulty("MEDIUM", correct_streak=2, wrong_streak=0) == "HARD"
    assert adaptive_difficulty("MEDIUM", correct_streak=0, wrong_streak=2) == "EASY"
    # Um acerto isolado não muda o nível.
    assert adaptive_difficulty("MEDIUM", correct_streak=1, wrong_streak=0) == "MEDIUM"


def test_adaptive_difficulty_respects_bounds() -> None:
    assert adaptive_difficulty("HARD", correct_streak=5, wrong_streak=0) == "HARD"
    assert adaptive_difficulty("EASY", correct_streak=0, wrong_streak=5) == "EASY"
