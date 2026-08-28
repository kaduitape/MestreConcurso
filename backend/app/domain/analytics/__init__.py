"""Analytics — Mestre Score, projeção, caminho e painéis.

Toda a estatística da plataforma nasce aqui, em Python determinístico: a IA
nunca é responsável sozinha por cálculo estatístico.
"""

from app.domain.analytics.dashboards import (
    Chart,
    Dashboard,
    DayEffort,
    SeriesPoint,
    SubjectCoverage,
    WeeklyAttempts,
    accuracy_evolution,
    consistency,
    coverage_by_subject,
    retention,
)
from app.domain.analytics.master_score import (
    SCALE,
    MasterScore,
    MasterScoreInput,
    ScoreComponent,
    band_for,
)
from app.domain.analytics.master_score import compute as compute_master_score
from app.domain.analytics.path import DISCLAIMER as PATH_DISCLAIMER
from app.domain.analytics.path import (
    ActionKind,
    Path,
    PathStep,
)
from app.domain.analytics.path import build as build_path
from app.domain.analytics.projection import DISCLAIMER as PROJECTION_DISCLAIMER
from app.domain.analytics.projection import (
    MIN_EXAM_COVERAGE,
    MIN_SUBJECT_ATTEMPTS,
    ExamProjection,
    SubjectExam,
    SubjectPerformance,
    SubjectProjection,
    project,
)
from app.domain.analytics.statistics import (
    SAMPLE_HIGH,
    SAMPLE_LOW,
    Component,
    Composite,
    Confidence,
    Interval,
    combine,
    confidence_for,
    largest_remainder,
    weakest_confidence,
    wilson,
)

__all__ = [
    "MIN_EXAM_COVERAGE",
    "MIN_SUBJECT_ATTEMPTS",
    "PATH_DISCLAIMER",
    "PROJECTION_DISCLAIMER",
    "SAMPLE_HIGH",
    "SAMPLE_LOW",
    "SCALE",
    "ActionKind",
    "Chart",
    "Component",
    "Composite",
    "Confidence",
    "Dashboard",
    "DayEffort",
    "ExamProjection",
    "Interval",
    "MasterScore",
    "MasterScoreInput",
    "Path",
    "PathStep",
    "ScoreComponent",
    "SeriesPoint",
    "SubjectCoverage",
    "SubjectExam",
    "SubjectPerformance",
    "SubjectProjection",
    "WeeklyAttempts",
    "accuracy_evolution",
    "band_for",
    "build_path",
    "combine",
    "compute_master_score",
    "confidence_for",
    "consistency",
    "coverage_by_subject",
    "largest_remainder",
    "project",
    "retention",
    "weakest_confidence",
    "wilson",
]
