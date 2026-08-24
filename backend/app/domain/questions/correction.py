"""Correção de simulado: muito além de "7/10".

Tudo é contagem sobre as respostas: acerto por disciplina, por dificuldade, tempo
gasto e comparação com o histórico. Recomendações são frases derivadas desses
números — nunca opinião gerada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Abaixo desta amostra não classificamos uma disciplina como ponto fraco: três
# questões erradas em três não sustentam um diagnóstico.
MIN_SUBJECT_SAMPLE = 3
WEAK_ACCURACY_THRESHOLD = 0.6


@dataclass(frozen=True, slots=True)
class QuestionInfo:
    question_id: int
    subject_id: int | None
    subject_name: str
    difficulty: str
    correct_letter: str | None


@dataclass(frozen=True, slots=True)
class AnswerInput:
    question_id: int
    selected_letter: str | None
    time_seconds: int = 0


@dataclass(frozen=True, slots=True)
class SubjectBreakdown:
    subject_id: int | None
    subject_name: str
    total: int
    correct: int
    wrong: int
    blank: int
    time_seconds: int

    @property
    def accuracy(self) -> float:
        answered = self.correct + self.wrong
        return round(self.correct / answered, 4) if answered else 0.0

    @property
    def average_time_seconds(self) -> int:
        return self.time_seconds // self.total if self.total else 0


@dataclass(frozen=True, slots=True)
class DifficultyBreakdown:
    difficulty: str
    total: int
    correct: int

    @property
    def accuracy(self) -> float:
        return round(self.correct / self.total, 4) if self.total else 0.0


@dataclass(frozen=True, slots=True)
class QuestionOutcome:
    question_id: int
    selected_letter: str | None
    correct_letter: str | None
    is_correct: bool
    is_blank: bool
    time_seconds: int


@dataclass(frozen=True, slots=True)
class AttemptAnalysis:
    total: int
    correct: int
    wrong: int
    blank: int
    score: float
    accuracy: float
    total_time_seconds: int
    average_time_seconds: int
    by_subject: list[SubjectBreakdown] = field(default_factory=list)
    by_difficulty: list[DifficultyBreakdown] = field(default_factory=list)
    weakest_subjects: list[str] = field(default_factory=list)
    strongest_subjects: list[str] = field(default_factory=list)
    outcomes: list[QuestionOutcome] = field(default_factory=list)
    previous_accuracy: float | None = None
    accuracy_delta: float | None = None
    recommendations: list[str] = field(default_factory=list)


def correct_attempt(
    answers: list[AnswerInput],
    questions: list[QuestionInfo],
    *,
    previous_accuracy: float | None = None,
) -> AttemptAnalysis:
    """Corrige a execução e devolve o diagnóstico completo."""
    answered = {answer.question_id: answer for answer in answers}

    outcomes: list[QuestionOutcome] = []
    subjects: dict[tuple[int | None, str], dict[str, int]] = {}
    difficulties: dict[str, dict[str, int]] = {}

    for question in questions:
        answer = answered.get(question.question_id)
        selected = answer.selected_letter if answer else None
        is_blank = selected is None or selected == ""
        is_correct = (
            not is_blank
            and question.correct_letter is not None
            and selected == question.correct_letter
        )
        time_seconds = answer.time_seconds if answer else 0

        outcomes.append(
            QuestionOutcome(
                question_id=question.question_id,
                selected_letter=selected,
                correct_letter=question.correct_letter,
                is_correct=is_correct,
                is_blank=is_blank,
                time_seconds=time_seconds,
            )
        )

        key = (question.subject_id, question.subject_name)
        bucket = subjects.setdefault(
            key, {"total": 0, "correct": 0, "wrong": 0, "blank": 0, "time": 0}
        )
        bucket["total"] += 1
        bucket["time"] += time_seconds
        if is_blank:
            bucket["blank"] += 1
        elif is_correct:
            bucket["correct"] += 1
        else:
            bucket["wrong"] += 1

        level = difficulties.setdefault(question.difficulty, {"total": 0, "correct": 0})
        level["total"] += 1
        if is_correct:
            level["correct"] += 1

    total = len(questions)
    correct = sum(1 for outcome in outcomes if outcome.is_correct)
    blank = sum(1 for outcome in outcomes if outcome.is_blank)
    wrong = total - correct - blank
    total_time = sum(outcome.time_seconds for outcome in outcomes)
    accuracy = round(correct / total, 4) if total else 0.0

    by_subject = sorted(
        (
            SubjectBreakdown(
                subject_id=key[0],
                subject_name=key[1],
                total=value["total"],
                correct=value["correct"],
                wrong=value["wrong"],
                blank=value["blank"],
                time_seconds=value["time"],
            )
            for key, value in subjects.items()
        ),
        key=lambda item: item.subject_name,
    )
    by_difficulty = [
        DifficultyBreakdown(difficulty=key, total=value["total"], correct=value["correct"])
        for key, value in sorted(difficulties.items())
    ]

    # Só entram no diagnóstico disciplinas com amostra suficiente.
    eligible = [item for item in by_subject if item.total >= MIN_SUBJECT_SAMPLE]
    weakest = sorted(eligible, key=lambda item: item.accuracy)
    weak_names = [item.subject_name for item in weakest if item.accuracy < WEAK_ACCURACY_THRESHOLD][
        :3
    ]
    strong_names = [item.subject_name for item in reversed(weakest) if item.accuracy >= 0.8][:3]

    return AttemptAnalysis(
        total=total,
        correct=correct,
        wrong=wrong,
        blank=blank,
        score=round(correct / total * 100, 2) if total else 0.0,
        accuracy=accuracy,
        total_time_seconds=total_time,
        average_time_seconds=total_time // total if total else 0,
        by_subject=by_subject,
        by_difficulty=by_difficulty,
        weakest_subjects=weak_names,
        strongest_subjects=strong_names,
        outcomes=outcomes,
        previous_accuracy=previous_accuracy,
        accuracy_delta=(
            round(accuracy - previous_accuracy, 4) if previous_accuracy is not None else None
        ),
        recommendations=build_recommendations(
            by_subject, blank=blank, total=total, average_time=total_time // total if total else 0
        ),
    )


def build_recommendations(
    by_subject: list[SubjectBreakdown], *, blank: int, total: int, average_time: int
) -> list[str]:
    """Frases derivadas dos números — cada uma cita o dado que a motivou."""
    messages: list[str] = []

    for item in by_subject:
        if item.total >= MIN_SUBJECT_SAMPLE and item.accuracy < WEAK_ACCURACY_THRESHOLD:
            messages.append(
                f"{item.subject_name}: {item.correct} de {item.total} questões "
                f"({item.accuracy * 100:.0f}% de acerto) — priorize revisão."
            )

    if total and blank / total > 0.1:
        messages.append(f"{blank} questão(ões) em branco de {total}: revise o controle de tempo.")

    if average_time > 180:
        messages.append(
            f"Tempo médio de {average_time // 60}min por questão — acima do ritmo de prova."
        )

    if not messages:
        messages.append("Desempenho consistente nesta execução; siga o plano.")
    return messages[:5]
