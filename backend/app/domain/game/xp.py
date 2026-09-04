"""Quanto vale cada ação — e o que o motor se recusa a pontuar.

XP mede **esforço útil**. Um número que sobe sem que o candidato tenha ficado
melhor é uma mentira com animação, e mentira animada é pior do que número nenhum:
o candidato confia nela e relaxa.

Por isso cada regra abaixo tem um motivo, e toda redução vira texto legível — o
candidato vê por que ganhou menos, em vez de achar que é bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GameEventKind(StrEnum):
    """Fatos consumados que o motor sabe pontuar."""

    STUDY_SESSION = "STUDY_SESSION"
    FLASHCARDS_REVIEWED = "FLASHCARDS_REVIEWED"
    QUESTIONS_ANSWERED = "QUESTIONS_ANSWERED"
    SIMULATION_FINISHED = "SIMULATION_FINISHED"
    ERROR_CLASSIFIED = "ERROR_CLASSIFIED"
    DAILY_MISSIONS_DONE = "DAILY_MISSIONS_DONE"
    WEEKLY_MISSION_DONE = "WEEKLY_MISSION_DONE"
    ACHIEVEMENT_UNLOCKED = "ACHIEVEMENT_UNLOCKED"
    CHALLENGE_FINISHED = "CHALLENGE_FINISHED"
    TRAINING_FINISHED = "TRAINING_FINISHED"


@dataclass(frozen=True, slots=True)
class XPRule:
    """Regra de fábrica. A tabela ``game_rules`` vence sobre isto."""

    key: str
    label: str
    xp_value: int
    daily_cap: int
    is_enabled: bool = True


DEFAULT_RULES: tuple[XPRule, ...] = (
    XPRule(GameEventKind.STUDY_SESSION, "Estudo com foco (por 30 min)", 100, 400),
    XPRule(GameEventKind.FLASHCARDS_REVIEWED, "Revisão de flashcards (por cartão)", 4, 200),
    XPRule(GameEventKind.QUESTIONS_ANSWERED, "Questões resolvidas (por questão)", 6, 300),
    XPRule(GameEventKind.SIMULATION_FINISHED, "Simulado concluído", 300, 600),
    XPRule(GameEventKind.ERROR_CLASSIFIED, "Erro classificado (por erro)", 20, 100),
    XPRule(GameEventKind.DAILY_MISSIONS_DONE, "Todas as missões do dia", 250, 250),
    XPRule(GameEventKind.WEEKLY_MISSION_DONE, "Missão da semana", 500, 500),
    XPRule(GameEventKind.ACHIEVEMENT_UNLOCKED, "Conquista desbloqueada", 0, 1000),
    XPRule(GameEventKind.CHALLENGE_FINISHED, "Rodada de desafio concluída", 0, 500),
    XPRule(GameEventKind.TRAINING_FINISHED, "Missão de treinamento concluída", 150, 300),
)

RULES_BY_KEY: dict[str, XPRule] = {rule.key: rule for rule in DEFAULT_RULES}

# --------------------------------------------------------------------------- #
# Antiabuso
# --------------------------------------------------------------------------- #
# Abrir e fechar a tela não é estudo.
MIN_FOCUS_MINUTES = 5
# Não dá tempo de ler o enunciado: a questão não entra na contagem.
MIN_SECONDS_PER_QUESTION = 3
# Simulado com menos que isto é treino solto, não simulado.
MIN_SIMULATION_QUESTIONS = 10

# A dificuldade modula: cem questões fáceis não valem mais que estudar de verdade.
DIFFICULTY_MULTIPLIER: dict[str, float] = {"EASY": 0.7, "MEDIUM": 1.0, "HARD": 1.3}

# Lote com acerto muito baixo vale menos: o objetivo é aprender, não preencher contador.
LOW_ACCURACY_THRESHOLD = 0.40
LOW_ACCURACY_MULTIPLIER = 0.6


@dataclass(frozen=True, slots=True)
class GameEvent:
    """Um fato já consumado, com a métrica real que o descreve."""

    kind: str
    metrics: dict[str, float | str] = field(default_factory=dict)
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class XPAward:
    kind: str
    amount: int
    base_amount: int
    multiplier: float
    # Frase legível: é o que a interface mostra ao lado do ganho.
    reason: str
    capped: bool = False
    cap_reason: str | None = None
    metrics: dict[str, float | str] = field(default_factory=dict)

    @property
    def is_zero(self) -> bool:
        return self.amount == 0


def _plural(count: float, singular: str, plural: str) -> str:
    return singular if round(count) == 1 else plural


def score_event(event: GameEvent, rule: XPRule, *, earned_today: int = 0) -> XPAward:
    """Calcula o XP de um evento, aplicando modulação e teto diário."""
    metrics = event.metrics

    if not rule.is_enabled:
        return XPAward(
            kind=event.kind,
            amount=0,
            base_amount=0,
            multiplier=0.0,
            reason="Esta pontuação está desativada.",
            metrics=metrics,
        )

    base, multiplier, reason, refusal = _base_for(event, rule)
    if refusal is not None:
        return XPAward(
            kind=event.kind,
            amount=0,
            base_amount=0,
            multiplier=0.0,
            reason=refusal,
            metrics=metrics,
        )

    amount = round(base * multiplier)
    remaining = max(0, rule.daily_cap - earned_today)
    if amount > remaining:
        capped_amount = remaining
        return XPAward(
            kind=event.kind,
            amount=capped_amount,
            base_amount=base,
            multiplier=multiplier,
            reason=reason,
            capped=True,
            cap_reason=(
                f"Você atingiu o teto diário de {rule.daily_cap} XP para "
                f"“{rule.label.lower()}”. O estudo continua contando para o seu "
                "desempenho — só o XP desta atividade parou por hoje."
            ),
            metrics=metrics,
        )

    return XPAward(
        kind=event.kind,
        amount=amount,
        base_amount=base,
        multiplier=multiplier,
        reason=reason,
        metrics=metrics,
    )


def _base_for(event: GameEvent, rule: XPRule) -> tuple[int, float, str, str | None]:
    """Devolve (base, multiplicador, motivo, recusa)."""
    metrics = event.metrics

    if event.kind == GameEventKind.STUDY_SESSION:
        minutes = float(metrics.get("focus_minutes", 0))
        if minutes < MIN_FOCUS_MINUTES:
            return (
                0,
                0.0,
                "",
                (f"Sessões abaixo de {MIN_FOCUS_MINUTES} minutos de foco não pontuam."),
            )
        base = round(rule.xp_value * minutes / 30)
        return base, 1.0, f"{round(minutes)} minutos de estudo com foco.", None

    if event.kind == GameEventKind.FLASHCARDS_REVIEWED:
        cards = int(metrics.get("cards", 0))
        if cards <= 0:
            return 0, 0.0, "", "Nenhum cartão revisado."
        base = rule.xp_value * cards
        return base, 1.0, f"{cards} {_plural(cards, 'cartão revisado', 'cartões revisados')}.", None

    if event.kind == GameEventKind.QUESTIONS_ANSWERED:
        questions = int(metrics.get("questions", 0))
        if questions <= 0:
            return 0, 0.0, "", "Nenhuma questão válida na contagem."
        base = rule.xp_value * questions
        multiplier = DIFFICULTY_MULTIPLIER.get(str(metrics.get("difficulty", "MEDIUM")), 1.0)
        raw_accuracy = metrics.get("accuracy")
        accuracy = float(raw_accuracy) if isinstance(raw_accuracy, int | float) else None
        detail = f"{questions} {_plural(questions, 'questão resolvida', 'questões resolvidas')}."
        if accuracy is not None and accuracy < LOW_ACCURACY_THRESHOLD:
            multiplier *= LOW_ACCURACY_MULTIPLIER
            detail += (
                f" Acerto de {accuracy * 100:.0f}% nesta rodada: o ganho foi reduzido, "
                "porque volume sem acerto não é aprendizado."
            )
        return base, round(multiplier, 3), detail, None

    if event.kind == GameEventKind.SIMULATION_FINISHED:
        questions = int(metrics.get("questions", 0))
        if questions < MIN_SIMULATION_QUESTIONS:
            return (
                0,
                0.0,
                "",
                (f"Simulados com menos de {MIN_SIMULATION_QUESTIONS} questões não pontuam."),
            )
        return rule.xp_value, 1.0, f"Simulado de {questions} questões concluído.", None

    if event.kind == GameEventKind.ERROR_CLASSIFIED:
        errors = int(metrics.get("errors", 1))
        if errors <= 0:
            return 0, 0.0, "", "Nenhum erro classificado."
        base = rule.xp_value * errors
        detail = f"{errors} {_plural(errors, 'erro classificado', 'erros classificados')}."
        return base, 1.0, detail, None

    if event.kind == GameEventKind.ACHIEVEMENT_UNLOCKED:
        amount = int(metrics.get("xp", 0))
        return amount, 1.0, str(metrics.get("label", "Conquista desbloqueada.")), None

    if event.kind == GameEventKind.CHALLENGE_FINISHED:
        # O valor vem da rodada, que já é uma conta aberta (modo, proporção
        # respondida e combo). A regra guarda apenas o teto diário — é ele que
        # impede transformar desafio em torneira de XP.
        answered = int(metrics.get("answered", 0))
        if answered <= 0:
            return 0, 0.0, "", "Rodada encerrada sem resposta alguma."
        amount = int(metrics.get("xp", 0))
        return amount, 1.0, str(metrics.get("label", "Rodada de desafio concluída.")), None

    if event.kind == GameEventKind.TRAINING_FINISHED:
        minutes = float(metrics.get("focus_minutes", 0))
        if minutes < MIN_FOCUS_MINUTES:
            return (
                0,
                0.0,
                "",
                f"Missões exigem ao menos {MIN_FOCUS_MINUTES} minutos de foco para pontuar.",
            )
        return (
            rule.xp_value,
            1.0,
            f"Missão de treinamento concluída com {round(minutes)} minutos de foco.",
            None,
        )

    # Missões: o valor é o da própria regra.
    return rule.xp_value, 1.0, rule.label + ".", None


def valid_questions(
    attempts: list[dict[str, float | bool]],
) -> tuple[int, float | None, str]:
    """Filtra as respostas que contam para XP.

    Devolve (quantidade válida, taxa de acerto, dificuldade predominante).
    Resposta rápida demais e questão repetida no dia ficam de fora — não é
    punição, é reconhecer que não houve leitura do enunciado.
    """
    seen: set[float] = set()
    valid: list[dict[str, float | bool]] = []
    for attempt in attempts:
        if float(attempt.get("time_seconds", 0)) < MIN_SECONDS_PER_QUESTION:
            continue
        question_id = float(attempt.get("question_id", 0))
        if question_id in seen:
            continue
        seen.add(question_id)
        valid.append(attempt)

    if not valid:
        return 0, None, "MEDIUM"

    correct = sum(1 for item in valid if item.get("is_correct"))
    accuracy = correct / len(valid)

    difficulties = [str(item.get("difficulty", "MEDIUM")) for item in valid]
    predominant = max(set(difficulties), key=difficulties.count)
    return len(valid), round(accuracy, 4), predominant
