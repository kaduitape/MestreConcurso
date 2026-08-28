"""Conquistas — avaliadas sobre número real, nunca sobre presença.

Conquista que se ganha por abrir o aplicativo não reconhece nada. Todas as
definições abaixo apontam para uma métrica que a plataforma já calcula em outra
fase: horas de foco, acerto, cartões, sequência, erros classificados.

Conquista secreta existe para premiar o que não se persegue de propósito — a
virada numa disciplina, a recuperação de um assunto crítico. Por isso ela não
aparece antes de acontecer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AchievementCategory(StrEnum):
    STUDY = "STUDY"
    QUESTIONS = "QUESTIONS"
    MEMORY = "MEMORY"
    CONSISTENCY = "CONSISTENCY"
    SIMULATIONS = "SIMULATIONS"
    RECOVERY = "RECOVERY"


@dataclass(frozen=True, slots=True)
class AchievementSpec:
    slug: str
    name: str
    description: str
    category: str
    icon: str
    tier: str
    metric: str
    threshold: float
    xp_reward: int
    is_secret: bool = False
    # Métrica secundária: quando existe, precisa ser atendida junto.
    guard_metric: str | None = None
    guard_threshold: float = 0.0


ACHIEVEMENTS: tuple[AchievementSpec, ...] = (
    AchievementSpec(
        "primeiro-estudo",
        "Primeiro passo",
        "Sua primeira sessão de estudo com foco.",
        AchievementCategory.STUDY,
        "🌱",
        "BRONZE",
        "study_sessions",
        1,
        50,
    ),
    AchievementSpec(
        "disciplina-de-ferro",
        "Disciplina de Ferro",
        "7 dias seguidos de estudo útil.",
        AchievementCategory.CONSISTENCY,
        "🔥",
        "PRATA",
        "current_streak",
        7,
        300,
    ),
    AchievementSpec(
        "constancia-de-aco",
        "Constância de Aço",
        "30 dias seguidos de estudo útil.",
        AchievementCategory.CONSISTENCY,
        "🛡️",
        "OURO",
        "current_streak",
        30,
        1000,
    ),
    AchievementSpec(
        "cem-questoes",
        "Cem Questões",
        "100 questões resolvidas.",
        AchievementCategory.QUESTIONS,
        "🎯",
        "BRONZE",
        "questions_answered",
        100,
        200,
    ),
    AchievementSpec(
        "atirador-de-elite",
        "Atirador de Elite",
        "100 questões resolvidas com 80% de acerto ou mais.",
        AchievementCategory.QUESTIONS,
        "🏹",
        "OURO",
        "questions_answered",
        100,
        600,
        guard_metric="accuracy",
        guard_threshold=0.80,
    ),
    AchievementSpec(
        "mil-questoes",
        "Mil Questões",
        "1.000 questões resolvidas.",
        AchievementCategory.QUESTIONS,
        "⚔️",
        "DIAMANTE",
        "questions_answered",
        1000,
        1500,
    ),
    AchievementSpec(
        "memoria-de-aco",
        "Memória de Aço",
        "100 revisões de flashcards com 90% de recordação.",
        AchievementCategory.MEMORY,
        "🧠",
        "OURO",
        "flashcard_reviews",
        100,
        600,
        guard_metric="recall_rate",
        guard_threshold=0.90,
    ),
    AchievementSpec(
        "cem-horas",
        "Cem Horas",
        "100 horas líquidas de estudo com foco.",
        AchievementCategory.STUDY,
        "⏳",
        "DIAMANTE",
        "focus_hours",
        100,
        1200,
    ),
    AchievementSpec(
        "analista-de-erros",
        "Analista de Erros",
        "50 erros classificados com causa registrada.",
        AchievementCategory.RECOVERY,
        "🔍",
        "PRATA",
        "errors_classified",
        50,
        400,
    ),
    AchievementSpec(
        "maratonista",
        "Maratonista",
        "10 simulados concluídos.",
        AchievementCategory.SIMULATIONS,
        "🏁",
        "OURO",
        "simulations_finished",
        10,
        700,
    ),
    # --- secretas -------------------------------------------------------- #
    AchievementSpec(
        "virada-de-jogo",
        "Virada de Jogo",
        "Uma disciplina saiu de menos de 50% para mais de 70% de acerto.",
        AchievementCategory.RECOVERY,
        "📈",
        "DIAMANTE",
        "subject_turnaround",
        1,
        1000,
        is_secret=True,
    ),
    AchievementSpec(
        "sem-repetir-erro",
        "Sem Repetir Erro",
        "50 questões seguidas sem repetir um erro já classificado.",
        AchievementCategory.RECOVERY,
        "🎓",
        "OURO",
        "clean_streak_questions",
        50,
        800,
        is_secret=True,
    ),
)

ACHIEVEMENTS_BY_SLUG: dict[str, AchievementSpec] = {item.slug: item for item in ACHIEVEMENTS}


@dataclass(frozen=True, slots=True)
class AchievementProgress:
    spec: AchievementSpec
    current: float
    unlocked: bool
    # Nulo quando a conquista tem guarda não atendida: o progresso do contador
    # sozinho enganaria — a pessoa acharia que está perto sem estar.
    ratio: float | None = None
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AchievementEvaluation:
    unlocked: list[AchievementSpec] = field(default_factory=list)
    progress: list[AchievementProgress] = field(default_factory=list)


def evaluate(metrics: dict[str, float], *, already_unlocked: set[str]) -> AchievementEvaluation:
    """Confere quais conquistas o candidato alcançou, com base nos números reais."""
    unlocked: list[AchievementSpec] = []
    progress: list[AchievementProgress] = []

    for spec in ACHIEVEMENTS:
        current = float(metrics.get(spec.metric, 0))
        reached = current >= spec.threshold

        guard_ok = True
        blocked = None
        if spec.guard_metric is not None:
            guard_value = metrics.get(spec.guard_metric)
            guard_ok = guard_value is not None and guard_value >= spec.guard_threshold
            if not guard_ok:
                blocked = (
                    f"Exige {spec.guard_threshold * 100:.0f}% em "
                    f"{spec.guard_metric.replace('_', ' ')}."
                )

        is_unlocked = spec.slug in already_unlocked
        if reached and guard_ok and not is_unlocked:
            unlocked.append(spec)

        progress.append(
            AchievementProgress(
                spec=spec,
                current=current,
                unlocked=is_unlocked or (reached and guard_ok),
                ratio=(
                    round(min(1.0, current / spec.threshold), 4)
                    if spec.threshold and guard_ok
                    else None
                ),
                blocked_reason=blocked,
            )
        )

    return AchievementEvaluation(unlocked=unlocked, progress=progress)
