"""Exportação de dados pessoais (LGPD) — tudo o que a conta gerou.

A exportação nasceu na Fase 1 e ficou parada ali enquanto o produto crescia:
plano de estudo, respostas, flashcards, conversas, gamificação e assinatura
foram entrando sem realimentar este arquivo. O resultado era uma exportação que
dizia "tudo o que a plataforma guarda sobre você" e entregava a menor parte.

O catálogo abaixo é **declarativo de propósito**: dá para ler a lista e conferir
o que entra. Uma coleção nova numa fase futura é uma linha aqui — e a ausência
fica visível na revisão, em vez de passar batida.

Coleções grandes são limitadas por um teto, e o corte é **declarado** com o total
real: entregar 5.000 de 40.000 sem avisar seria pior do que não entregar.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models import analytics as analytics_models
from app.models import billing as billing_models
from app.models import flashcard as flashcard_models
from app.models import game as game_models
from app.models import intelligence as intelligence_models
from app.models import question as question_models
from app.models import study as study_models
from app.models import tutor as tutor_models
from app.models.user import User

#: Teto por coleção. Alto o bastante para caber um ano de estudo intenso.
MAX_ROWS = 5000


@dataclass(frozen=True, slots=True)
class Collection:
    """Uma coleção exportável e as colunas que saem dela."""

    key: str
    label: str
    model: type[Base]
    fields: tuple[str, ...]


CATALOG: tuple[tuple[str, tuple[Collection, ...]], ...] = (
    (
        "estudo",
        (
            Collection(
                "planos",
                "Planos de estudo",
                study_models.StudyPlan,
                (
                    "public_id",
                    "name",
                    "status",
                    "exam_date",
                    "starts_on",
                    "weekly_minutes_target",
                    "created_at",
                ),
            ),
            Collection(
                "tarefas",
                "Tarefas do plano",
                study_models.StudyTask,
                (
                    "public_id",
                    "subject_label",
                    "kind",
                    "status",
                    "scheduled_on",
                    "planned_minutes",
                    "done_minutes",
                ),
            ),
            Collection(
                "sessoes",
                "Sessões de estudo",
                study_models.StudySession,
                (
                    "public_id",
                    "subject_label",
                    "kind",
                    "status",
                    "started_at",
                    "ended_at",
                    "focus_seconds",
                    "pause_seconds",
                ),
            ),
            Collection(
                "progresso_por_disciplina",
                "Progresso por disciplina",
                study_models.UserSubjectProgress,
                (
                    "subject_label",
                    "planned_minutes",
                    "studied_minutes",
                    "tasks_done",
                    "completion",
                    "last_studied_at",
                ),
            ),
        ),
    ),
    (
        "questoes",
        (
            Collection(
                "respostas",
                "Respostas a questões",
                question_models.QuestionAttempt,
                (
                    "public_id",
                    "question_id",
                    "selected_letter",
                    "is_correct",
                    "is_blank",
                    "time_seconds",
                    "confidence",
                    "created_at",
                ),
            ),
            Collection(
                "simulados",
                "Simulados montados",
                question_models.Simulation,
                ("public_id", "name", "kind", "questions_count", "duration_minutes", "created_at"),
            ),
            Collection(
                "simulados_realizados",
                "Simulados realizados",
                question_models.SimulationAttempt,
                (
                    "public_id",
                    "status",
                    "started_at",
                    "finished_at",
                    "score",
                    "correct_count",
                    "wrong_count",
                    "blank_count",
                ),
            ),
        ),
    ),
    (
        "memorizacao",
        (
            Collection(
                "flashcards",
                "Flashcards",
                flashcard_models.Flashcard,
                ("public_id", "front", "back", "origin", "status", "created_at"),
            ),
            Collection(
                "revisoes",
                "Revisões de flashcards",
                flashcard_models.FlashcardReview,
                (
                    "rating",
                    "time_seconds",
                    "previous_interval_days",
                    "next_interval_days",
                    "due_on",
                    "created_at",
                ),
            ),
            Collection(
                "estado_de_memoria",
                "Estado de memória dos cartões",
                flashcard_models.CardMemoryState,
                (
                    "flashcard_id",
                    "state",
                    "due_on",
                    "interval_days",
                    "ease_factor",
                    "reviews",
                    "lapses",
                ),
            ),
        ),
    ),
    (
        "mestre_ia",
        (
            Collection(
                "conversas",
                "Conversas com o Mestre IA",
                tutor_models.Conversation,
                ("public_id", "title", "mode", "created_at"),
            ),
            Collection(
                "mensagens",
                "Mensagens das conversas",
                tutor_models.Message,
                ("public_id", "role", "content", "created_at"),
            ),
            Collection(
                "vocabulario",
                "Termos do vocabulário",
                tutor_models.VocabularyTerm,
                ("public_id", "term", "definition", "status", "created_at"),
            ),
        ),
    ),
    (
        "inteligencia",
        (
            Collection(
                "analises_de_erro",
                "Erros classificados",
                intelligence_models.ErrorAnalysis,
                ("public_id", "cause", "confidence", "note", "confirmed_at", "created_at"),
            ),
            Collection(
                "prioridades",
                "Priority Score por disciplina",
                intelligence_models.UserPriority,
                ("scope_key", "label", "score", "coverage", "computed_at"),
            ),
        ),
    ),
    (
        "gamificacao",
        (
            Collection(
                "perfil",
                "Perfil de gamificação",
                game_models.GamificationProfile,
                (
                    "level",
                    "xp_total",
                    "rank_slug",
                    "rank_score",
                    "current_streak",
                    "longest_streak",
                    "missions_completed",
                    "achievements_count",
                ),
            ),
            Collection(
                "extrato_de_xp",
                "Extrato de XP",
                game_models.XPTransaction,
                ("public_id", "event_kind", "amount", "reason", "capped", "day", "created_at"),
            ),
            Collection(
                "missoes",
                "Missões",
                game_models.Mission,
                (
                    "public_id",
                    "scope",
                    "kind",
                    "title",
                    "target_value",
                    "current_value",
                    "status",
                    "valid_from",
                ),
            ),
            Collection(
                "conquistas",
                "Conquistas desbloqueadas",
                game_models.UserAchievement,
                ("achievement_id", "unlocked_at"),
            ),
            Collection(
                "dias_de_sequencia",
                "Dias de sequência",
                game_models.StreakDay,
                ("day", "minutes", "tasks_done", "qualified", "shield_used"),
            ),
            Collection(
                "historico_de_rank",
                "Histórico de rank",
                game_models.RankSnapshot,
                ("day", "rank_slug", "rank_score", "xp_total", "level"),
            ),
            Collection(
                "temporadas",
                "Participação em temporadas",
                game_models.SeasonParticipation,
                (
                    "season_id",
                    "seasonal_xp",
                    "qualified_days",
                    "position",
                    "participants",
                    "context_label",
                    "closed_at",
                ),
            ),
            Collection(
                "rodadas_de_desafio",
                "Rodadas de desafio",
                game_models.GameRun,
                (
                    "public_id",
                    "mode",
                    "status",
                    "score",
                    "best_combo",
                    "xp_awarded",
                    "achieved",
                    "started_at",
                    "ended_at",
                ),
            ),
            Collection(
                "modo_guerra",
                "Períodos de Modo Guerra",
                game_models.WarCampaign,
                (
                    "public_id",
                    "status",
                    "starts_on",
                    "days",
                    "daily_minutes",
                    "daily_questions",
                    "days_met",
                    "succeeded",
                    "ended_at",
                ),
            ),
            Collection(
                "cards_publicados",
                "Cards compartilháveis",
                game_models.ShareCardRecord,
                ("public_id", "display_name", "headline", "revoked_at", "created_at"),
            ),
        ),
    ),
    (
        "analytics",
        (
            Collection(
                "historico_do_mestre_score",
                "Histórico do Mestre Score",
                analytics_models.MasterScoreSnapshot,
                ("day", "value", "low", "high", "band", "confidence"),
            ),
        ),
    ),
    (
        "comercial",
        (
            Collection(
                "assinaturas",
                "Assinaturas",
                billing_models.Subscription,
                (
                    "public_id",
                    "plan_id",
                    "status",
                    "started_on",
                    "current_period_start",
                    "current_period_end",
                    "trial_ends_on",
                    "canceled_at",
                    "cancel_reason",
                ),
            ),
            Collection(
                "pagamentos",
                "Cobranças",
                billing_models.Payment,
                (
                    "public_id",
                    "reference",
                    "status",
                    "amount_cents",
                    "discount_cents",
                    "paid_at",
                    "created_at",
                ),
            ),
            Collection(
                "faturamento",
                "Faturamento",
                billing_models.InvoiceLine,
                (
                    "description",
                    "amount_cents",
                    "discount_cents",
                    "credit_cents",
                    "total_cents",
                    "period_start",
                    "period_end",
                    "created_at",
                ),
            ),
            Collection(
                "consumo",
                "Contadores de consumo",
                billing_models.UsageCounter,
                ("feature", "window_start", "window_end", "used"),
            ),
            Collection(
                "cupons_usados",
                "Cupons resgatados",
                billing_models.CouponRedemption,
                ("coupon_id", "amount_cents", "discount_cents", "created_at"),
            ),
        ),
    ),
)


def _value(raw: Any) -> Any:
    """Serializa para JSON sem perder precisão nem inventar formato."""
    if isinstance(raw, Enum):
        return raw.value
    if isinstance(raw, datetime | date):
        return raw.isoformat()
    if isinstance(raw, Decimal):
        return float(raw)
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return raw


class DataExportService:
    """Reúne, coleção a coleção, o que a conta gerou na plataforma."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _collect(self, collection: Collection, user_id: int) -> dict[str, Any]:
        model = collection.model
        # Todo modelo do catálogo tem ``user_id``; o acesso dinâmico é o preço
        # de a lista ser declarativa, e um erro aqui aparece no primeiro teste.
        owner = getattr(model, "user_id")  # noqa: B009
        newest_first = getattr(model, "id").desc()  # noqa: B009
        total = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(model).where(owner == user_id)
                )
            ).scalar_one()
        )

        stmt = select(model).where(owner == user_id).order_by(newest_first).limit(MAX_ROWS)
        rows: Sequence[Any] = (await self.session.execute(stmt)).scalars().all()

        items = [
            {field: _value(getattr(row, field, None)) for field in collection.fields}
            for row in rows
        ]
        result: dict[str, Any] = {
            "label": collection.label,
            "total": total,
            "items": items,
        }
        if total > len(items):
            # O corte é dito com o número real: entregar uma fatia calada seria
            # pior do que não entregar.
            result["truncated"] = True
            result["note"] = (
                f"Exportados os {len(items)} registros mais recentes de {total}. "
                "Peça o restante pelo suporte para receber o arquivo completo."
            )
        return result

    async def collect(self, user: User) -> dict[str, Any]:
        """Todas as coleções do catálogo, agrupadas por área do produto."""
        payload: dict[str, Any] = {}
        for area, collections in CATALOG:
            grouped: dict[str, Any] = {}
            for collection in collections:
                grouped[collection.key] = await self._collect(collection, user.id)
            payload[area] = grouped
        return payload
