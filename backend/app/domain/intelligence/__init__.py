"""Camada de inteligência — cálculo puro, sem I/O e sem IA."""

from app.domain.intelligence.errors import (
    CAUSE_ACTIONS,
    CAUSE_LABELS,
    ErrorNotebook,
    ErrorRecord,
    build_notebook,
)
from app.domain.intelligence.incidence import (
    IncidenceReport,
    IncidenceRow,
    QuestionSample,
    compute_incidence,
)
from app.domain.intelligence.priority import (
    Contribution,
    PriorityInput,
    PriorityScore,
    adjust_shares_by_priority,
    compute_priority,
    rank_priorities,
)
from app.domain.intelligence.profile import BoardMetric, ProfileSample, build_board_profile

__all__ = [
    "CAUSE_ACTIONS",
    "CAUSE_LABELS",
    "BoardMetric",
    "Contribution",
    "ErrorNotebook",
    "ErrorRecord",
    "IncidenceReport",
    "IncidenceRow",
    "PriorityInput",
    "PriorityScore",
    "ProfileSample",
    "QuestionSample",
    "adjust_shares_by_priority",
    "build_board_profile",
    "build_notebook",
    "compute_incidence",
    "compute_priority",
    "rank_priorities",
]
