"""Repetição espaçada: quando cada cartão volta, e por quê.

O intervalo sai de uma conta determinística em Python. Nenhuma IA decide quando
um cartão volta — e cada revisão devolve o `breakdown` que explica o número, do
mesmo jeito que o Priority Score da Fase 6.

O algoritmo é da família SM-2, com três acréscimos deliberados:

* **a velocidade da resposta ajusta o intervalo** — quem responde rápido e certo
  demonstra domínio maior do que quem hesitou e acertou; o ajuste é limitado a
  ±15% para que velocidade não vire o sinal dominante;
* **o teto de intervalo** existe para que um cartão não suma por dois anos às
  vésperas da prova;
* **a queda por erro é proporcional**, não um retorno cego ao início: quem errou
  um cartão maduro não volta ao mesmo ponto de quem errou um cartão recém-visto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum


class Rating(StrEnum):
    """O que o candidato respondeu ao ver a resposta."""

    AGAIN = "AGAIN"  # não lembrei
    HARD = "HARD"  # lembrei com dificuldade
    GOOD = "GOOD"  # lembrei
    EASY = "EASY"  # lembrei de imediato


class CardState(StrEnum):
    NEW = "NEW"
    LEARNING = "LEARNING"
    REVIEW = "REVIEW"
    RELEARNING = "RELEARNING"


# Facilidade inicial e limites. Fora desta faixa o intervalo cresce ou encolhe
# rápido demais para ser útil.
DEFAULT_EASE = 2.5
MIN_EASE = 1.3
MAX_EASE = 3.0

# Ajuste da facilidade por resposta (SM-2 clássico).
EASE_DELTA: dict[str, float] = {
    Rating.AGAIN.value: -0.20,
    Rating.HARD.value: -0.15,
    Rating.GOOD.value: 0.0,
    Rating.EASY.value: 0.15,
}

# Passos de aprendizado, em dias, antes do cartão entrar em revisão.
LEARNING_STEPS = (0, 1)
# Depois de um erro, o cartão volta a passar por este passo.
RELEARNING_STEP = 0

# Multiplicadores aplicados ao intervalo em revisão.
HARD_FACTOR = 1.2
EASY_BONUS = 1.3
# Erro não zera: o intervalo cai a esta fração do anterior, com piso de 1 dia.
LAPSE_FACTOR = 0.35

MIN_INTERVAL = 1
MAX_INTERVAL = 180

# Velocidade: tempo de referência por cartão e o teto do ajuste.
TARGET_SECONDS = 20
MAX_SPEED_ADJUSTMENT = 0.15


@dataclass(frozen=True, slots=True)
class CardMemory:
    """O que se sabe da memória do candidato sobre um cartão."""

    state: str = CardState.NEW
    ease_factor: float = DEFAULT_EASE
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0
    step_index: int = 0


@dataclass(frozen=True, slots=True)
class ReviewOutcome:
    memory: CardMemory
    interval_days: int
    due_on: date
    # Como o intervalo foi obtido — é o "por quê?" exibido na interface.
    breakdown: dict[str, float | int | str] = field(default_factory=dict)

    @property
    def is_lapse(self) -> bool:
        return self.breakdown.get("motivo") == "erro"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def speed_adjustment(time_seconds: int, rating: str) -> float:
    """Fator de velocidade entre 0,85 e 1,15.

    Só se aplica a acerto: responder um erro rápido não é sinal de domínio, é
    sinal de que a pessoa nem tentou lembrar.
    """
    if rating == Rating.AGAIN or time_seconds <= 0:
        return 1.0
    ratio = TARGET_SECONDS / time_seconds
    # Rápido (ratio > 1) aumenta o intervalo; lento (ratio < 1) reduz.
    raw = 1 + (ratio - 1) * 0.25
    return round(_clamp(raw, 1 - MAX_SPEED_ADJUSTMENT, 1 + MAX_SPEED_ADJUSTMENT), 4)


def review(
    memory: CardMemory, rating: str, *, time_seconds: int = 0, today: date | None = None
) -> ReviewOutcome:
    """Calcula o próximo intervalo a partir da resposta dada."""
    if rating not in {item.value for item in Rating}:
        raise ValueError(f"Resposta inválida: {rating}")

    reference = today or date.today()
    ease = _clamp(memory.ease_factor + EASE_DELTA[rating], MIN_EASE, MAX_EASE)
    breakdown: dict[str, float | int | str] = {
        "resposta": rating,
        "facilidade_anterior": round(memory.ease_factor, 3),
        "facilidade_nova": round(ease, 3),
        "intervalo_anterior": memory.interval_days,
    }

    # ------------------------------------------------------------------ #
    # Erro: o cartão volta para reaprendizado, com queda proporcional.
    # ------------------------------------------------------------------ #
    if rating == Rating.AGAIN:
        interval = max(MIN_INTERVAL, round(memory.interval_days * LAPSE_FACTOR))
        if memory.state in {CardState.NEW, CardState.LEARNING}:
            interval = RELEARNING_STEP
        breakdown |= {
            "motivo": "erro",
            "fator_de_queda": LAPSE_FACTOR,
            "intervalo_final": interval,
        }
        return ReviewOutcome(
            memory=CardMemory(
                state=CardState.RELEARNING,
                ease_factor=ease,
                interval_days=interval,
                repetitions=0,
                lapses=memory.lapses + 1,
                step_index=0,
            ),
            interval_days=interval,
            due_on=reference + timedelta(days=interval),
            breakdown=breakdown,
        )

    # ------------------------------------------------------------------ #
    # Aprendizado e reaprendizado: passos fixos antes de virar revisão.
    # ------------------------------------------------------------------ #
    if memory.state in {CardState.NEW, CardState.LEARNING, CardState.RELEARNING}:
        next_step = memory.step_index + 1
        if rating == Rating.EASY or next_step >= len(LEARNING_STEPS):
            # Sai do aprendizado direto para revisão.
            interval = MIN_INTERVAL if rating != Rating.EASY else max(MIN_INTERVAL, 3)
            breakdown |= {
                "motivo": "saiu do aprendizado",
                "intervalo_final": interval,
            }
            return ReviewOutcome(
                memory=CardMemory(
                    state=CardState.REVIEW,
                    ease_factor=ease,
                    interval_days=interval,
                    repetitions=memory.repetitions + 1,
                    lapses=memory.lapses,
                    step_index=0,
                ),
                interval_days=interval,
                due_on=reference + timedelta(days=interval),
                breakdown=breakdown,
            )

        interval = LEARNING_STEPS[next_step]
        breakdown |= {
            "motivo": "passo de aprendizado",
            "passo": next_step,
            "intervalo_final": interval,
        }
        return ReviewOutcome(
            memory=CardMemory(
                state=CardState.LEARNING,
                ease_factor=ease,
                interval_days=interval,
                repetitions=memory.repetitions,
                lapses=memory.lapses,
                step_index=next_step,
            ),
            interval_days=interval,
            due_on=reference + timedelta(days=interval),
            breakdown=breakdown,
        )

    # ------------------------------------------------------------------ #
    # Revisão: o intervalo cresce pela facilidade, ajustado pela velocidade.
    # ------------------------------------------------------------------ #
    base = max(MIN_INTERVAL, memory.interval_days)
    if rating == Rating.HARD:
        raw = base * HARD_FACTOR
        factor_label = HARD_FACTOR
    elif rating == Rating.EASY:
        raw = base * ease * EASY_BONUS
        factor_label = round(ease * EASY_BONUS, 3)
    else:
        raw = base * ease
        factor_label = round(ease, 3)

    speed = speed_adjustment(time_seconds, rating)
    adjusted = raw * speed
    interval = int(_clamp(round(adjusted), MIN_INTERVAL, MAX_INTERVAL))

    breakdown |= {
        "motivo": "revisão",
        "fator_aplicado": factor_label,
        "intervalo_calculado": round(raw, 2),
        "ajuste_de_velocidade": speed,
        "tempo_de_resposta_s": time_seconds,
        "intervalo_final": interval,
    }
    if adjusted > MAX_INTERVAL:
        breakdown["teto_aplicado"] = MAX_INTERVAL

    return ReviewOutcome(
        memory=CardMemory(
            state=CardState.REVIEW,
            ease_factor=ease,
            interval_days=interval,
            repetitions=memory.repetitions + 1,
            lapses=memory.lapses,
            step_index=0,
        ),
        interval_days=interval,
        due_on=reference + timedelta(days=interval),
        breakdown=breakdown,
    )
