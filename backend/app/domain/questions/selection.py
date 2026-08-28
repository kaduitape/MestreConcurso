"""Composição de simulados: quantas questões de cada disciplina, e com que dificuldade."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

# Sequência de acertos/erros que move a dificuldade no simulado adaptativo.
ADAPTIVE_STEP = 2
DIFFICULTY_ORDER = ("EASY", "MEDIUM", "HARD")


@dataclass(frozen=True, slots=True)
class SubjectQuota:
    subject_id: int | None
    subject_name: str
    weight: float
    questions: int


def distribute_by_weight(
    subjects: list[tuple[int | None, str, Decimal | float | None, int | None]],
    total_questions: int,
) -> list[SubjectQuota]:
    """Divide o total de questões entre as disciplinas.

    Quando o edital informa quantas questões cada disciplina tem, esse número manda.
    Só na ausência dele o peso é usado como aproximação — e o resultado é declarado
    como distribuição estimada na interface.
    """
    if total_questions <= 0 or not subjects:
        return []

    declared = [item[3] or 0 for item in subjects]
    if sum(declared) > 0:
        base = [value / sum(declared) for value in declared]
    else:
        weights = [float(item[2] or 1) for item in subjects]
        total_weight = sum(weights)
        base = [weight / total_weight for weight in weights]

    quotas = [max(1, round(total_questions * fraction)) for fraction in base]

    # Ajuste fino para fechar exatamente o total pedido.
    difference = total_questions - sum(quotas)
    order = sorted(range(len(quotas)), key=lambda index: base[index], reverse=True)
    position = 0
    while difference != 0 and order:
        index = order[position % len(order)]
        if difference > 0:
            quotas[index] += 1
            difference -= 1
        elif quotas[index] > 1:
            quotas[index] -= 1
            difference += 1
        position += 1
        if position > len(order) * total_questions:
            break

    return [
        SubjectQuota(
            subject_id=subjects[index][0],
            subject_name=subjects[index][1],
            weight=round(base[index], 6),
            questions=quotas[index],
        )
        for index in range(len(subjects))
    ]


def adaptive_difficulty(current: str, *, correct_streak: int, wrong_streak: int) -> str:
    """Próxima dificuldade no simulado adaptativo.

    Regra simples e explicável: dois acertos seguidos sobem um nível, dois erros
    seguidos descem. Sem heurística oculta e sem modelo envolvido.
    """
    if current not in DIFFICULTY_ORDER:
        current = "MEDIUM"
    index = DIFFICULTY_ORDER.index(current)

    if correct_streak >= ADAPTIVE_STEP:
        index = min(index + 1, len(DIFFICULTY_ORDER) - 1)
    elif wrong_streak >= ADAPTIVE_STEP:
        index = max(index - 1, 0)
    return DIFFICULTY_ORDER[index]
