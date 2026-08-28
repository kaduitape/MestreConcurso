"""Modo Sprint: um estudo pronto para o tempo que o candidato tem agora."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.planner.scheduler import MIN_TASK_MINUTES, TaskKind

ALLOWED_DURATIONS = (15, 30, 45, 60)

# Proporção de cada bloco por duração. Sprints curtos priorizam revisão e questões:
# não faz sentido abrir conteúdo novo em 15 minutos.
SPRINT_MIX: dict[int, tuple[tuple[str, float], ...]] = {
    15: ((TaskKind.REVIEW, 0.6), (TaskKind.FLASHCARDS, 0.4)),
    30: ((TaskKind.REVIEW, 0.35), (TaskKind.QUESTIONS, 0.4), (TaskKind.FLASHCARDS, 0.25)),
    45: (
        (TaskKind.REVIEW, 0.25),
        (TaskKind.QUESTIONS, 0.4),
        (TaskKind.THEORY, 0.2),
        (TaskKind.FLASHCARDS, 0.15),
    ),
    60: (
        (TaskKind.THEORY, 0.3),
        (TaskKind.QUESTIONS, 0.4),
        (TaskKind.REVIEW, 0.2),
        (TaskKind.FLASHCARDS, 0.1),
    ),
}

LABELS: dict[str, str] = {
    TaskKind.THEORY: "Teoria",
    TaskKind.QUESTIONS: "Questões",
    TaskKind.REVIEW: "Revisão",
    TaskKind.FLASHCARDS: "Flashcards",
}


@dataclass(frozen=True, slots=True)
class SprintBlock:
    kind: str
    label: str
    minutes: int
    subject_key: str | None = None
    subject_name: str | None = None


@dataclass(frozen=True, slots=True)
class SprintPlan:
    total_minutes: int
    blocks: list[SprintBlock] = field(default_factory=list)

    @property
    def planned_minutes(self) -> int:
        return sum(block.minutes for block in self.blocks)


def build_sprint(
    minutes: int,
    *,
    focus_subject_key: str | None = None,
    focus_subject_name: str | None = None,
) -> SprintPlan:
    """Monta o sprint para a duração escolhida.

    Duração fora das opções conhecidas é aproximada para a mais próxima — sem
    inventar composição para um tempo que não foi pensado.
    """
    if minutes < MIN_TASK_MINUTES:
        raise ValueError(f"O sprint mínimo é de {MIN_TASK_MINUTES} minutos.")

    duration = min(ALLOWED_DURATIONS, key=lambda option: abs(option - minutes))
    entries = SPRINT_MIX[duration]

    # Cada bloco recebe sua fração arredondada para baixo em múltiplos de 5.
    allocated = [max(5, int(minutes * fraction) // 5 * 5) for _, fraction in entries]
    while sum(allocated) > minutes and max(allocated) > 5:
        allocated[allocated.index(max(allocated))] -= 5

    # A sobra vai para o bloco de maior peso, não para o último da lista: senão
    # um sprint de 45 minutos terminaria com mais flashcards do que questões.
    leftover = minutes - sum(allocated)
    if leftover > 0:
        heaviest = max(range(len(entries)), key=lambda index: entries[index][1])
        allocated[heaviest] += leftover

    blocks = [
        SprintBlock(
            kind=kind,
            label=LABELS[kind],
            minutes=allocated[index],
            subject_key=focus_subject_key,
            subject_name=focus_subject_name,
        )
        for index, (kind, _) in enumerate(entries)
        if allocated[index] >= 5
    ]
    return SprintPlan(total_minutes=minutes, blocks=blocks)
