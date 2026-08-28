"""Regras do banco de questões e da correção — Python puro, sem IA.

A correção de um simulado é aritmética: contar, agrupar, comparar. Nada aqui
depende de modelo de linguagem, e nenhum número é estimado.
"""

from app.domain.questions.correction import (
    AnswerInput,
    AttemptAnalysis,
    QuestionInfo,
    SubjectBreakdown,
    correct_attempt,
)
from app.domain.questions.selection import (
    SubjectQuota,
    adaptive_difficulty,
    distribute_by_weight,
)

__all__ = [
    "AnswerInput",
    "AttemptAnalysis",
    "QuestionInfo",
    "SubjectBreakdown",
    "SubjectQuota",
    "adaptive_difficulty",
    "correct_attempt",
    "distribute_by_weight",
]
