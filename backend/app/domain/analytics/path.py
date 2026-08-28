"""Caminho da Aprovação — a lista do que fazer, ordenada pelo que rende mais.

O nome vem do pedido, mas o conteúdo é deliberadamente modesto: são **ações**
ordenadas por quantas questões da prova elas colocam em jogo. Nada aqui afirma
que seguir a lista aprova alguém.

Cada passo carrega o número que o gerou. Uma recomendação sem o número que a
justifica é palpite — e palpite com cara de sistema é pior do que palpite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.analytics.projection import MIN_SUBJECT_ATTEMPTS, SubjectProjection

# Acima disto a disciplina está consolidada: a ação vira manutenção.
STRONG_ACCURACY = 0.80

DISCLAIMER = (
    "As ações são ordenadas por quantas questões da prova elas colocam em jogo. "
    "Seguir a lista melhora o que é medido aqui; não é garantia de resultado."
)


class ActionKind(StrEnum):
    MEASURE = "MEASURE"  # falta amostra: primeiro medir
    IMPROVE = "IMPROVE"  # há espaço claro de ganho
    MAINTAIN = "MAINTAIN"  # já consolidado: manter


ACTION_LABEL: dict[str, str] = {
    ActionKind.MEASURE: "Medir",
    ActionKind.IMPROVE: "Melhorar",
    ActionKind.MAINTAIN: "Manter",
}


@dataclass(frozen=True, slots=True)
class PathStep:
    subject_id: int | None
    subject_name: str
    kind: str
    label: str
    #: O que fazer, em uma frase de ação.
    action: str
    #: O número real que gerou a recomendação.
    evidence: str
    #: Questões da prova que a ação coloca em jogo (0 quando é só medir).
    questions_at_stake: float
    is_eliminatory: bool
    #: Alerta do edital, quando existe.
    risk_note: str | None = None


@dataclass(frozen=True, slots=True)
class Path:
    steps: list[PathStep] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    empty_reason: str | None = None


def build(projections: list[SubjectProjection]) -> Path:
    """Monta a lista de ações a partir da projeção por disciplina."""
    if not projections:
        return Path(
            empty_reason=(
                "O caminho é traçado sobre a distribuição de questões da sua prova. "
                "Sem ela, não há o que ordenar."
            )
        )

    steps: list[PathStep] = []
    for item in projections:
        if not item.included:
            faltam = max(0, MIN_SUBJECT_ATTEMPTS - item.sample)
            steps.append(
                PathStep(
                    subject_id=item.subject_id,
                    subject_name=item.name,
                    kind=ActionKind.MEASURE,
                    label=ACTION_LABEL[ActionKind.MEASURE],
                    action=(
                        f"Responder {faltam} questões de {item.name} para a disciplina "
                        "entrar na estimativa."
                    ),
                    evidence=(
                        f"{item.sample} respostas registradas · {item.questions} questões "
                        "desta disciplina na prova"
                    ),
                    # Não há ganho estimável: ainda não se sabe onde o candidato está.
                    questions_at_stake=0.0,
                    is_eliminatory=item.is_eliminatory,
                )
            )
            continue

        accuracy = item.accuracy or 0.0
        at_stake = round((1 - accuracy) * item.questions * item.weight, 2)

        if accuracy >= STRONG_ACCURACY:
            steps.append(
                PathStep(
                    subject_id=item.subject_id,
                    subject_name=item.name,
                    kind=ActionKind.MAINTAIN,
                    label=ACTION_LABEL[ActionKind.MAINTAIN],
                    action=(
                        f"Manter {item.name} com revisão espaçada; o esforço rende mais em "
                        "outra disciplina agora."
                    ),
                    evidence=f"{accuracy * 100:.0f}% em {item.sample} respostas",
                    questions_at_stake=at_stake,
                    is_eliminatory=item.is_eliminatory,
                    risk_note=item.risk_note,
                )
            )
            continue

        steps.append(
            PathStep(
                subject_id=item.subject_id,
                subject_name=item.name,
                kind=ActionKind.IMPROVE,
                label=ACTION_LABEL[ActionKind.IMPROVE],
                action=(
                    f"Estudar e resolver questões de {item.name}: é onde há mais questões "
                    "da prova em jogo."
                ),
                evidence=(
                    f"{accuracy * 100:.0f}% em {item.sample} respostas · "
                    f"{item.questions} questões na prova"
                    + (f" · peso {item.weight:g}" if item.weight != 1.0 else "")
                ),
                questions_at_stake=at_stake,
                is_eliminatory=item.is_eliminatory,
                risk_note=item.risk_note,
            )
        )

    # Ordem: risco de eliminação primeiro, depois o que coloca mais questões em
    # jogo, depois o que ainda precisa ser medido.
    priority: dict[str, int] = {
        ActionKind.IMPROVE: 0,
        ActionKind.MEASURE: 1,
        ActionKind.MAINTAIN: 2,
    }
    steps.sort(
        key=lambda item: (
            item.risk_note is None,
            priority[item.kind],
            -item.questions_at_stake,
            item.subject_name,
        )
    )
    return Path(steps=steps)
