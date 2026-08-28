"""A fila de revisão — e a regra de que ela **nunca explode** depois de uma ausência.

Quem passa uma semana fora volta e encontra 300 cartões vencidos. Empilhar todos
no mesmo dia é a forma mais rápida de fazer alguém abandonar a revisão: a fila
vira uma dívida impagável e a pessoa desiste do hábito inteiro.

Então a fila tem teto diário. O que não cabe hoje é **redistribuído** pelos
próximos dias, do mais atrasado para o menos, e a plataforma diz exatamente o
que fez — mesma regra do replanejamento da Fase 4: dívida declarada, nunca
escondida.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Teto padrão de cartões por dia. Acima disso a sessão deixa de ser revisão e
# vira maratona — e maratona ninguém repete no dia seguinte.
DEFAULT_DAILY_LIMIT = 60
MAX_DAILY_LIMIT = 300
# Quantos cartões novos entram por dia, dentro do teto acima.
DEFAULT_NEW_PER_DAY = 15

# Em quantos dias, no máximo, o atraso é diluído.
MAX_SPREAD_DAYS = 7


@dataclass(frozen=True, slots=True)
class QueueCard:
    """Um cartão candidato à fila de hoje."""

    card_id: int
    due_on: date
    is_new: bool = False
    # Priority Score da disciplina, quando existir: desempata o que entra hoje.
    priority: int = 0

    def overdue_days(self, today: date) -> int:
        return max(0, (today - self.due_on).days)


@dataclass(frozen=True, slots=True)
class Reschedule:
    card_id: int
    from_day: date
    to_day: date


@dataclass(frozen=True, slots=True)
class QueuePlan:
    today: list[QueueCard] = field(default_factory=list)
    rescheduled: list[Reschedule] = field(default_factory=list)
    new_count: int = 0
    review_count: int = 0
    overdue_count: int = 0
    absence_days: int = 0
    # Frase pronta para a interface — o candidato sabe o que aconteceu com a fila.
    summary: str = ""


def _sort_key(card: QueueCard, today: date) -> tuple[int, int, int]:
    """Mais atrasado primeiro; empate resolve por prioridade e por id."""
    return (-card.overdue_days(today), -card.priority, card.card_id)


def build_queue(
    cards: list[QueueCard],
    *,
    today: date | None = None,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
    new_per_day: int = DEFAULT_NEW_PER_DAY,
    last_reviewed_on: date | None = None,
) -> QueuePlan:
    """Monta a fila do dia e redistribui o que passar do teto."""
    reference = today or date.today()
    limit = max(1, min(daily_limit, MAX_DAILY_LIMIT))
    absence = max(0, (reference - last_reviewed_on).days) if last_reviewed_on else 0

    due = [card for card in cards if card.due_on <= reference]
    overdue = [card for card in due if card.due_on < reference]

    reviews = sorted(
        (card for card in due if not card.is_new), key=lambda item: _sort_key(item, reference)
    )
    fresh = sorted((card for card in due if card.is_new), key=lambda item: item.card_id)

    # Revisão vencida tem precedência sobre cartão novo: memória que já existe e
    # está prestes a se perder vale mais do que memória que ainda nem começou.
    selected_reviews = reviews[:limit]
    remaining_slots = max(0, limit - len(selected_reviews))
    selected_new = fresh[: min(new_per_day, remaining_slots)]

    overflow = reviews[len(selected_reviews) :]
    rescheduled: list[Reschedule] = []
    if overflow:
        # Dilui o excedente nos próximos dias, respeitando o mesmo teto por dia.
        spread_days = min(MAX_SPREAD_DAYS, max(1, -(-len(overflow) // limit)))
        for index, card in enumerate(overflow):
            offset = (index // limit) + 1
            target = reference + timedelta(days=min(offset, spread_days))
            rescheduled.append(
                Reschedule(card_id=card.card_id, from_day=card.due_on, to_day=target)
            )

    return QueuePlan(
        today=selected_reviews + selected_new,
        rescheduled=rescheduled,
        new_count=len(selected_new),
        review_count=len(selected_reviews),
        overdue_count=len(overdue),
        absence_days=absence,
        summary=_summary(
            absence=absence,
            overdue=len(overdue),
            today_count=len(selected_reviews) + len(selected_new),
            rescheduled=len(rescheduled),
            limit=limit,
        ),
    )


def _summary(*, absence: int, overdue: int, today_count: int, rescheduled: int, limit: int) -> str:
    if today_count == 0 and overdue == 0:
        return "Nenhuma revisão vencida. Sua memória está em dia."

    parts: list[str] = []
    if absence >= 2:
        parts.append(f"Você ficou {absence} dias sem revisar.")
    if overdue:
        parts.append(f"{overdue} cartão(ões) estavam vencidos.")
    parts.append(f"Separei {today_count} para hoje (teto de {limit}).")
    if rescheduled:
        parts.append(
            f"Os outros {rescheduled} foram distribuídos pelos próximos dias — "
            "a fila não acumula tudo num dia só."
        )
    return " ".join(parts)


def forecast(cards: list[QueueCard], *, today: date | None = None, days: int = 7) -> list[dict]:
    """Quantos cartões vencem em cada um dos próximos dias.

    Serve para o candidato ver a carga que vem pela frente antes de ela chegar.
    """
    reference = today or date.today()
    counts: dict[date, int] = {}
    for card in cards:
        day = max(card.due_on, reference)
        if (day - reference).days < days:
            counts[day] = counts.get(day, 0) + 1
    return [
        {
            "day": (reference + timedelta(days=offset)).isoformat(),
            "count": counts.get(reference + timedelta(days=offset), 0),
        }
        for offset in range(days)
    ]
