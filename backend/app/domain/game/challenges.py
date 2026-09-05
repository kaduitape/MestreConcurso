"""Modos de desafio: Boss Battle, Sobrevivência, Combo e Contra o Relógio.

Todos usam **questões reais do banco**. Nenhum modo gera pergunta, ajusta
gabarito ou inventa dificuldade — o que muda entre eles é a regra de parada e a
forma de pontuar, não o conteúdo.

Duas escolhas merecem justificativa:

*Resposta rápida demais não alimenta combo nem XP.* O combo premia sequência de
acerto; se três segundos bastassem, ele premiaria quem chuta rápido. A resposta
continua registrada — ela aconteceu —, apenas não vira pontuação.

*O multiplicador tem teto.* Sem teto, uma sequência longa transformaria o placar
num número sem significado, e o candidato acabaria jogando pelo multiplicador em
vez de estudar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.game.battle import ENEMY_HP_ACCURACY_TARGET

# Mesmo piso do antiabuso da Fase 1: abaixo disso não deu tempo de ler.
MIN_SECONDS_PER_ANSWER = 3

# Combo: cada acerto encadeado soma 10%, até dobrar. Erro zera.
COMBO_STEP = 0.1
MAX_COMBO_MULTIPLIER = 2.0

# Boss Battle: abaixo deste acerto a disciplina continua sendo o ponto fraco.
BOSS_TARGET_ACCURACY = 0.70


class ChallengeMode(StrEnum):
    BOSS = "BOSS"
    SURVIVAL = "SURVIVAL"
    COMBO = "COMBO"
    TIME_ATTACK = "TIME_ATTACK"
    #: Rodada de um duelo (Fase 4). Não aparece na lista de modos avulsos: ela
    #: só existe dentro de um desafio entre dois candidatos.
    DUEL = "DUEL"
    #: Batalha RPG. É uma rodada como as outras — o que muda é a apresentação.
    BATTLE = "BATTLE"


class RunStatus(StrEnum):
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ABANDONED = "ABANDONED"


@dataclass(frozen=True, slots=True)
class ModeSpec:
    mode: str
    name: str
    description: str
    #: Quantas questões são separadas na largada. A corrida pode acabar antes.
    questions: int
    #: Erros que encerram a corrida (``None`` = não encerra por erro).
    lives: int | None
    #: Tempo total (``None`` = sem relógio).
    time_limit_seconds: int | None
    base_xp: int
    #: O critério de vitória, escrito para aparecer na tela.
    rule: str


MODES: tuple[ModeSpec, ...] = (
    ModeSpec(
        mode=ChallengeMode.BOSS,
        name="Boss Battle",
        description=(
            "Uma rodada contra a sua disciplina mais frágil, escolhida pelo Priority Score "
            "— não por sorteio."
        ),
        questions=15,
        lives=None,
        time_limit_seconds=None,
        base_xp=120,
        rule=f"Vence quem acerta {int(BOSS_TARGET_ACCURACY * 100)}% ou mais das 15 questões.",
    ),
    ModeSpec(
        mode=ChallengeMode.SURVIVAL,
        name="Sobrevivência",
        description="Segue enquanto você acerta. Três erros encerram a rodada.",
        questions=40,
        lives=3,
        time_limit_seconds=None,
        base_xp=80,
        rule="A pontuação é quantas questões você respondeu certo antes do terceiro erro.",
    ),
    ModeSpec(
        mode=ChallengeMode.COMBO,
        name="Combo",
        description="Acertos encadeados aumentam o multiplicador. Um erro zera.",
        questions=25,
        lives=None,
        time_limit_seconds=None,
        base_xp=80,
        rule=(
            f"Cada acerto seguido soma {int(COMBO_STEP * 100)}% ao multiplicador, "
            f"até {MAX_COMBO_MULTIPLIER:.0f}×."
        ),
    ),
    ModeSpec(
        mode=ChallengeMode.BATTLE,
        name="Batalha RPG",
        description=(
            "As mesmas questões, em forma de combate: acertar fere o inimigo, "
            "errar custa vida do seu guerreiro."
        ),
        questions=8,
        lives=None,
        time_limit_seconds=None,
        base_xp=100,
        rule=(
            "Vence quem derruba o inimigo antes de ficar sem vida. "
            "Três de cada quatro acertos bastam."
        ),
    ),
    ModeSpec(
        mode=ChallengeMode.TIME_ATTACK,
        name="Contra o Relógio",
        description="Vinte questões em dez minutos.",
        questions=20,
        lives=None,
        time_limit_seconds=600,
        base_xp=100,
        rule="A rodada encerra ao acabar o tempo, valendo o que foi respondido até ali.",
    ),
)

#: O lado de um duelo. Fora da tupla ``MODES`` porque não se começa sozinho.
DUEL_SPEC = ModeSpec(
    mode=ChallengeMode.DUEL,
    name="Duelo",
    description="Sua rodada de um desafio entre dois candidatos.",
    questions=10,
    lives=None,
    time_limit_seconds=None,
    base_xp=60,
    rule="Os dois lados respondem as mesmas questões. Vence quem acerta mais.",
)

MODES_BY_KEY: dict[str, ModeSpec] = {item.mode: item for item in (*MODES, DUEL_SPEC)}


@dataclass(frozen=True, slots=True)
class RunAnswer:
    """Uma resposta já corrigida, reduzida ao que o modo precisa saber."""

    is_correct: bool
    time_seconds: int

    @property
    def counts_for_score(self) -> bool:
        """Resposta instantânea não pontua — mas continua tendo acontecido."""
        return self.time_seconds >= MIN_SECONDS_PER_ANSWER


@dataclass(frozen=True, slots=True)
class RunState:
    mode: str
    answered: int
    correct: int
    wrong: int
    lives_left: int | None
    combo: int
    best_combo: int
    multiplier: float
    elapsed_seconds: int
    seconds_left: int | None
    questions_left: int
    is_over: bool
    #: Por que a rodada acabou. Nulo enquanto ela corre.
    over_reason: str | None = None

    @property
    def accuracy(self) -> float | None:
        """``None`` sem resposta alguma: zero de zero não é zero por cento."""
        return round(self.correct / self.answered, 4) if self.answered else None


def combo_multiplier(streak: int) -> float:
    """1,0 sem sequência; cresce 10% por acerto encadeado, com teto."""
    if streak <= 1:
        return 1.0
    return round(min(MAX_COMBO_MULTIPLIER, 1.0 + (streak - 1) * COMBO_STEP), 2)


def evaluate_run(spec: ModeSpec, answers: list[RunAnswer], *, elapsed_seconds: int) -> RunState:
    """Reconstrói o estado da rodada a partir das respostas já dadas.

    O estado é sempre **derivado**, nunca acumulado em contador: assim uma
    resposta perdida ou repetida não deixa o placar mentindo.
    """
    correct = 0
    wrong = 0
    combo = 0
    best_combo = 0

    for answer in answers:
        if answer.is_correct:
            correct += 1
            if answer.counts_for_score:
                combo += 1
                best_combo = max(best_combo, combo)
        else:
            wrong += 1
            combo = 0

    answered = len(answers)
    lives_left = None if spec.lives is None else max(0, spec.lives - wrong)
    seconds_left = (
        None
        if spec.time_limit_seconds is None
        else max(0, spec.time_limit_seconds - max(0, elapsed_seconds))
    )
    questions_left = max(0, spec.questions - answered)

    over_reason: str | None = None
    if lives_left == 0:
        over_reason = f"{spec.lives} erros — a rodada de sobrevivência acaba aqui."
    elif seconds_left == 0:
        over_reason = "O tempo acabou."
    elif questions_left == 0:
        over_reason = "Todas as questões da rodada foram respondidas."

    return RunState(
        mode=spec.mode,
        answered=answered,
        correct=correct,
        wrong=wrong,
        lives_left=lives_left,
        combo=combo,
        best_combo=best_combo,
        multiplier=combo_multiplier(combo),
        elapsed_seconds=max(0, elapsed_seconds),
        seconds_left=seconds_left,
        questions_left=questions_left,
        is_over=over_reason is not None,
        over_reason=over_reason,
    )


@dataclass(frozen=True, slots=True)
class ScoreLine:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class RunScore:
    score: int
    xp: int
    #: Verdadeiro só quando o modo tem critério de vitória e ele foi cumprido.
    achieved: bool
    headline: str
    #: A conta aberta: as linhas explicam de onde saiu o XP.
    breakdown: list[ScoreLine] = field(default_factory=list)


def score_run(spec: ModeSpec, state: RunState) -> RunScore:
    """Fecha a rodada: placar, XP e a conta que os produziu.

    O XP nunca é sorteado. Ele sai do XP base do modo, proporcional ao que foi
    de fato respondido, e — no Combo — do maior encadeamento alcançado.
    """
    scoring = state.correct
    lines: list[ScoreLine] = [
        ScoreLine("Acertos", f"{state.correct} de {state.answered} respondidas"),
    ]

    if spec.mode == ChallengeMode.SURVIVAL:
        score = scoring
        achieved = state.wrong < (spec.lives or 0)
        headline = f"{score} questões antes do fim"
        share = score / spec.questions
    elif spec.mode == ChallengeMode.COMBO:
        score = state.best_combo
        achieved = state.best_combo >= 5
        headline = f"Maior sequência: {state.best_combo}"
        share = scoring / spec.questions
        lines.append(
            ScoreLine("Multiplicador máximo", f"{combo_multiplier(state.best_combo):.1f}×")
        )
    elif spec.mode == ChallengeMode.BATTLE:
        score = scoring
        # Vencer é derrubar o inimigo, e o HP dele sai da mesma régua.
        achieved = state.correct >= round(spec.questions * ENEMY_HP_ACCURACY_TARGET)
        headline = f"{score} acertos em {state.answered} questões"
        share = scoring / spec.questions
    elif spec.mode == ChallengeMode.DUEL:
        score = scoring
        achieved = state.answered >= spec.questions
        headline = f"{score} acertos em {state.answered} questões"
        share = scoring / spec.questions
    elif spec.mode == ChallengeMode.TIME_ATTACK:
        score = scoring
        achieved = state.answered >= spec.questions
        headline = f"{score} acertos em {state.elapsed_seconds // 60} min"
        share = scoring / spec.questions
    else:  # BOSS
        score = scoring
        accuracy = state.accuracy or 0.0
        achieved = state.answered >= spec.questions and accuracy >= BOSS_TARGET_ACCURACY
        headline = (
            f"{int(accuracy * 100)}% de acerto na disciplina"
            if state.answered
            else "Nenhuma questão respondida"
        )
        share = scoring / spec.questions
        lines.append(ScoreLine("Alvo do desafio", f"{int(BOSS_TARGET_ACCURACY * 100)}% de acerto"))

    multiplier = combo_multiplier(state.best_combo) if spec.mode == ChallengeMode.COMBO else 1.0
    xp = int(spec.base_xp * min(1.0, share) * multiplier)

    lines.append(ScoreLine("XP base do modo", str(spec.base_xp)))
    lines.append(ScoreLine("Proporção respondida", f"{min(1.0, share) * 100:.0f}%"))
    if multiplier > 1.0:
        lines.append(ScoreLine("Multiplicador do combo", f"{multiplier:.1f}×"))
    lines.append(ScoreLine("XP da rodada", str(xp)))

    return RunScore(
        score=score,
        xp=xp,
        achieved=achieved,
        headline=headline,
        breakdown=lines,
    )
