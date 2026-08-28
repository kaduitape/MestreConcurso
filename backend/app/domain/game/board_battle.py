"""Você vs Banca — o placar entre o candidato e a banca que ele vai enfrentar.

O placar é a **taxa de acerto real** do candidato naquela banca, apresentada como
disputa. Não há adversário simulado, nem dificuldade artificial: os pontos da
banca são exatamente as questões que o candidato errou.

Isso é deliberado. Um "oponente" com força inventada tornaria o placar um enfeite
— e o candidato acabaria comemorando uma vitória contra ninguém. Aqui, ganhar da
banca significa acertar as questões dela.

Disciplina sem amostra **não recebe placar**: 12 respostas não dizem quem está
ganhando, e fingir que dizem é o mesmo que mentir com gráfico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Abaixo disto não se afirma placar algum.
MIN_BOARD_ANSWERS = 30
MIN_SUBJECT_ANSWERS = 30


@dataclass(frozen=True, slots=True)
class AnswerSample:
    """Uma resposta do candidato, reduzida ao que o placar precisa."""

    subject_id: int | None
    subject_name: str
    is_correct: bool
    answered_on: date


@dataclass(frozen=True, slots=True)
class SubjectScore:
    subject_id: int | None
    subject_name: str
    answers: int
    correct: int
    # 0..100 — a fatia do candidato no placar.
    you: int
    board: int
    is_sufficient: bool
    insufficient_reason: str | None = None


@dataclass(frozen=True, slots=True)
class WeekPoint:
    week_start: date
    answers: int
    accuracy: float


@dataclass(frozen=True, slots=True)
class BoardBattle:
    board_slug: str
    board_name: str
    answers: int
    correct: int
    you: int
    board: int
    is_sufficient: bool
    subjects: list[SubjectScore] = field(default_factory=list)
    evolution: list[WeekPoint] = field(default_factory=list)
    # Motivo pelo qual não há placar, quando for o caso.
    empty_reason: str | None = None

    @property
    def is_winning(self) -> bool:
        return self.is_sufficient and self.you > self.board


def _split(correct: int, total: int) -> tuple[int, int]:
    """Divide 100 pontos entre candidato e banca, sem sobra de arredondamento."""
    if total <= 0:
        return 0, 0
    you = round(correct / total * 100)
    return you, 100 - you


def _week_start(day: date) -> date:
    """Segunda-feira da semana daquela resposta."""
    return day - timedelta(days=day.weekday())


def build_battle(
    samples: list[AnswerSample], *, board_slug: str, board_name: str, weeks: int = 8
) -> BoardBattle:
    """Monta o placar geral, por disciplina e a evolução semanal."""
    total = len(samples)
    correct = sum(1 for item in samples if item.is_correct)

    if total < MIN_BOARD_ANSWERS:
        return BoardBattle(
            board_slug=board_slug,
            board_name=board_name,
            answers=total,
            correct=correct,
            you=0,
            board=0,
            is_sufficient=False,
            empty_reason=(
                f"Você respondeu {total} questão(ões) desta banca. "
                f"A partir de {MIN_BOARD_ANSWERS} o placar passa a significar alguma coisa."
            ),
        )

    you, board_points = _split(correct, total)

    grouped: dict[tuple[int | None, str], list[AnswerSample]] = {}
    for item in samples:
        grouped.setdefault((item.subject_id, item.subject_name), []).append(item)

    subjects: list[SubjectScore] = []
    for (subject_id, subject_name), items in grouped.items():
        count = len(items)
        hits = sum(1 for entry in items if entry.is_correct)
        sufficient = count >= MIN_SUBJECT_ANSWERS
        subject_you, subject_board = _split(hits, count) if sufficient else (0, 0)
        subjects.append(
            SubjectScore(
                subject_id=subject_id,
                subject_name=subject_name,
                answers=count,
                correct=hits,
                you=subject_you,
                board=subject_board,
                is_sufficient=sufficient,
                insufficient_reason=(
                    None
                    if sufficient
                    else (
                        f"{count} de {MIN_SUBJECT_ANSWERS} respostas para o placar desta "
                        "disciplina existir."
                    )
                ),
            )
        )

    # Placar decidido primeiro, insuficientes depois — e estes em ordem de volume.
    subjects.sort(key=lambda item: (not item.is_sufficient, -item.you, -item.answers))

    by_week: dict[date, list[AnswerSample]] = {}
    for item in samples:
        by_week.setdefault(_week_start(item.answered_on), []).append(item)

    evolution = [
        WeekPoint(
            week_start=week,
            answers=len(items),
            accuracy=round(sum(1 for entry in items if entry.is_correct) / len(items), 4),
        )
        for week, items in sorted(by_week.items())
    ][-weeks:]

    return BoardBattle(
        board_slug=board_slug,
        board_name=board_name,
        answers=total,
        correct=correct,
        you=you,
        board=board_points,
        is_sufficient=True,
        subjects=subjects,
        evolution=evolution,
    )
