"""Quanto tempo cada disciplina recebe.

A divisão sai de dados do edital: peso, número de questões e extensão do conteúdo.
Enquanto não houver histórico de desempenho (Fase 6), a distribuição é *baseline* —
e a interface diz isso, em vez de apresentar como se fosse personalização.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

# Pesos relativos dos sinais que definem a fatia de cada disciplina.
WEIGHT_FACTOR = 0.45
QUESTIONS_FACTOR = 0.35
EXTENT_FACTOR = 0.20

MIN_SHARE = 0.02  # nenhuma disciplina do edital fica sem tempo algum


@dataclass(frozen=True, slots=True)
class SubjectInput:
    """Uma disciplina do edital, com o que se sabe dela até aqui."""

    key: str
    name: str
    weight: Decimal | float | None = None
    questions_count: int | None = None
    topics_count: int = 0
    color_token: str = "subject-especifica"
    # Disciplina canônica, quando existe: é o elo com o banco de questões e com
    # o mapa de incidência (Fase 6).
    subject_id: int | None = None


@dataclass(frozen=True, slots=True)
class SubjectShare:
    key: str
    name: str
    share: float
    minutes: int
    color_token: str
    subject_id: int | None = None
    # Contribuição de cada sinal — é o que sustenta o "por quê?" na interface.
    breakdown: dict[str, float] = field(default_factory=dict)


def _normalize(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        return [1 / len(values)] * len(values) if values else []
    return [value / total for value in values]


def allocate_subject_shares(subjects: list[SubjectInput], total_minutes: int) -> list[SubjectShare]:
    """Distribui os minutos disponíveis entre as disciplinas.

    Cada sinal é normalizado antes de entrar na conta, para que uma disciplina com
    200 assuntos não engula o plano só por ser extensa.
    """
    if not subjects:
        return []

    weights = _normalize([float(item.weight or 1) for item in subjects])
    questions = _normalize([float(item.questions_count or 0) or 1.0 for item in subjects])
    extents = _normalize([float(item.topics_count or 0) or 1.0 for item in subjects])

    raw: list[float] = []
    breakdowns: list[dict[str, float]] = []
    for index in range(len(subjects)):
        weight_part = weights[index] * WEIGHT_FACTOR
        questions_part = questions[index] * QUESTIONS_FACTOR
        extent_part = extents[index] * EXTENT_FACTOR
        raw.append(weight_part + questions_part + extent_part)
        breakdowns.append(
            {
                "peso_no_edital": round(weight_part, 6),
                "questoes_na_prova": round(questions_part, 6),
                "extensao_do_conteudo": round(extent_part, 6),
            }
        )

    shares = _normalize(raw)
    shares = [max(share, MIN_SHARE) for share in shares]
    shares = _normalize(shares)

    result: list[SubjectShare] = []
    for index, subject in enumerate(subjects):
        result.append(
            SubjectShare(
                key=subject.key,
                name=subject.name,
                share=round(shares[index], 6),
                minutes=round(total_minutes * shares[index]),
                color_token=subject.color_token,
                subject_id=subject.subject_id,
                breakdown=breakdowns[index],
            )
        )
    return result
