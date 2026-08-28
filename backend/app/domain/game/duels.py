"""Desafio entre amigos: dois candidatos, **as mesmas questões**, dois placares.

A regra que sustenta o modo é essa: as questões são as mesmas para os dois lados.
Um duelo com listas diferentes não compara ninguém — compara sortes.

Também não existe adversário de mentira. Se o convite não é aceito, o duelo
expira; se um lado não termina, a vitória do outro é declarada **por ausência**,
com esse nome, em vez de virar uma vitória disfarçada de mérito.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

# Curto de propósito: duelo é encontro, não maratona.
DUEL_QUESTIONS = 10

# Convite sem resposta não fica aberto para sempre.
DUEL_EXPIRY_HOURS = 48


class DuelStatus(StrEnum):
    OPEN = "OPEN"  # convite criado, aguardando alguém aceitar
    RUNNING = "RUNNING"  # aceito, pelo menos um lado ainda respondendo
    FINISHED = "FINISHED"  # os dois lados fecharam (ou um venceu por ausência)
    EXPIRED = "EXPIRED"  # ninguém aceitou dentro do prazo
    CANCELED = "CANCELED"


class DuelOutcome(StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"
    TIE = "TIE"
    WALKOVER = "WALKOVER"  # o outro lado não respondeu
    EXPIRED = "EXPIRED"  # o prazo acabou sem placar possível
    UNDECIDED = "UNDECIDED"  # ainda não dá para dizer


@dataclass(frozen=True, slots=True)
class DuelSide:
    user_key: str
    display_name: str
    answered: int = 0
    correct: int = 0
    time_seconds: int = 0
    finished: bool = False

    @property
    def accuracy(self) -> float | None:
        return round(self.correct / self.answered, 4) if self.answered else None


@dataclass(frozen=True, slots=True)
class DuelResult:
    outcome: str
    winner_key: str | None = None
    margin: int = 0
    #: A frase que a tela mostra. Nunca disfarça ausência de vitória.
    headline: str = ""
    #: A conta aberta: como o resultado foi decidido.
    lines: list[str] = field(default_factory=list)


def resolve(
    challenger: DuelSide, opponent: DuelSide | None, *, expired: bool = False
) -> DuelResult:
    """Decide o duelo a partir do que os dois lados de fato responderam."""
    if opponent is None:
        if expired:
            return DuelResult(
                outcome=DuelOutcome.EXPIRED,
                headline="Ninguém aceitou o desafio dentro do prazo.",
                lines=["Convite expirado — nenhum adversário entrou."],
            )
        return DuelResult(
            outcome=DuelOutcome.UNDECIDED,
            headline="Aguardando alguém aceitar o desafio.",
            lines=["Enquanto ninguém aceita, não há placar."],
        )

    both_finished = challenger.finished and opponent.finished
    if not both_finished and not expired:
        return DuelResult(
            outcome=DuelOutcome.UNDECIDED,
            headline="Duelo em andamento.",
            lines=[
                f"{challenger.display_name}: {challenger.correct} de {challenger.answered}.",
                f"{opponent.display_name}: {opponent.correct} de {opponent.answered}.",
                "O resultado só é declarado quando os dois lados terminam.",
            ],
        )

    if not both_finished:
        # Prazo esgotado com um lado parado: vitória por ausência, dita assim.
        present, absent = (challenger, opponent) if challenger.finished else (opponent, challenger)
        if not present.finished:
            return DuelResult(
                outcome=DuelOutcome.EXPIRED,
                headline="O prazo acabou sem que os dois lados respondessem.",
                lines=["Nenhum dos dois concluiu a rodada — não há resultado."],
            )
        return DuelResult(
            outcome=DuelOutcome.WALKOVER,
            winner_key=present.user_key,
            headline=f"{present.display_name} venceu por ausência.",
            lines=[
                f"{absent.display_name} não concluiu a rodada dentro do prazo.",
                "Vitória por ausência não mede desempenho comparado.",
            ],
        )

    lines = [
        f"{challenger.display_name}: {challenger.correct} acertos em {challenger.time_seconds}s.",
        f"{opponent.display_name}: {opponent.correct} acertos em {opponent.time_seconds}s.",
    ]

    if challenger.correct != opponent.correct:
        winner, loser = (
            (challenger, opponent)
            if challenger.correct > opponent.correct
            else (opponent, challenger)
        )
        return DuelResult(
            outcome=DuelOutcome.WIN,
            winner_key=winner.user_key,
            margin=abs(challenger.correct - opponent.correct),
            headline=f"{winner.display_name} venceu por {winner.correct} a {loser.correct}.",
            lines=lines,
        )

    if challenger.time_seconds != opponent.time_seconds:
        winner = challenger if challenger.time_seconds < opponent.time_seconds else opponent
        lines.append("Empate em acertos: o desempate foi pelo tempo total.")
        return DuelResult(
            outcome=DuelOutcome.WIN,
            winner_key=winner.user_key,
            margin=0,
            headline=f"{winner.display_name} venceu no desempate por tempo.",
            lines=lines,
        )

    lines.append("Mesmos acertos e mesmo tempo.")
    return DuelResult(
        outcome=DuelOutcome.TIE,
        headline=f"Empate em {challenger.correct} acertos.",
        lines=lines,
    )
