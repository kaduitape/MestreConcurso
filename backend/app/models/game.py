"""Gamificação: perfil, razão de XP, missões, conquistas e sequência.

A decisão estrutural desta camada: **o saldo nunca é a verdade**. Toda pontuação
vira uma linha em ``xp_transactions``, com o motivo e a métrica que a justificou,
e o saldo do perfil é apenas leitura rápida — sempre reconstruível somando o
razão. Sem isso, um bug de pontuação vira número inexplicável no perfil de quem
estuda, e ninguém consegue auditar de onde veio.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, PublicIdMixin, TimestampMixin
from app.db.types import JsonType, MediumText


class MissionScope(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    SPECIAL = "SPECIAL"


class MissionStatus(StrEnum):
    PENDING = "PENDING"
    DONE = "DONE"  # cumprida, XP ainda não resgatado
    CLAIMED = "CLAIMED"  # XP creditado
    EXPIRED = "EXPIRED"


class GameRule(IdMixin, TimestampMixin, Base):
    """Regra de pontuação vigente. O código traz o padrão; esta tabela vence."""

    __tablename__ = "game_rules"
    __table_args__ = (UniqueConstraint("key", name="uq_game_rules_key"),)

    key: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(120))
    xp_value: Mapped[int] = mapped_column(Integer, default=0)
    daily_cap: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )


class GamificationProfile(IdMixin, TimestampMixin, Base):
    """Leitura rápida do estado do candidato. A verdade é o razão de XP."""

    __tablename__ = "gamification_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_gamification_profiles_user"),)

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp_total: Mapped[int] = mapped_column(Integer, default=0)

    rank_slug: Mapped[str] = mapped_column(String(20), default="FERRO")
    rank_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    # As contribuições que somam o score — é o "por quê?" do rank.
    rank_components: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    rank_missing_signals: Mapped[list[str]] = mapped_column(JsonType, default=list)

    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_on: Mapped[date | None] = mapped_column(Date)
    streak_shields_left: Mapped[int] = mapped_column(Integer, default=2)
    streak_shield_renewed_on: Mapped[date | None] = mapped_column(Date)

    missions_completed: Mapped[int] = mapped_column(Integer, default=0)
    achievements_count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Liga (Fase 3): a comparação é desligável (item 21 do pedido). Quem sai não
    # aparece na tabela de ninguém e não vê a de ninguém.
    league_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    # Anonimato é o padrão: só aparece com nome quem escolheu aparecer.
    league_display_name: Mapped[str | None] = mapped_column(String(40))


class XPTransaction(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma linha por ganho. O saldo do perfil é a soma disto — nunca o contrário."""

    __tablename__ = "xp_transactions"
    __table_args__ = (
        # Idempotência: o mesmo simulado, sessão ou missão nunca pontua duas vezes.
        UniqueConstraint(
            "user_id", "event_kind", "reference", name="uq_xp_transactions_user_event_ref"
        ),
        Index("ix_xp_transactions_user_day", "user_id", "day"),
        Index("ix_xp_transactions_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_kind: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(SmallInteger, default=0)
    base_amount: Mapped[int] = mapped_column(Integer, default=0)
    multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("1"))
    # Frase legível exibida ao lado do ganho no extrato.
    reason: Mapped[str] = mapped_column(String(400), default="")
    reference: Mapped[str] = mapped_column(String(60), default="")
    metrics: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    # Quando o teto diário cortou o ganho, o motivo fica registrado aqui.
    capped: Mapped[bool] = mapped_column(Boolean, default=False)
    cap_reason: Mapped[str | None] = mapped_column(MediumText)
    day: Mapped[date] = mapped_column(Date, index=True)


class Mission(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma missão do candidato, sempre ancorada num sinal real."""

    __tablename__ = "missions"
    __table_args__ = (
        Index("ix_missions_user_period", "user_id", "valid_from", "status"),
        UniqueConstraint("user_id", "kind", "valid_from", name="uq_missions_user_kind_day"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(20), default=MissionScope.DAILY)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(400), default="")

    target_metric: Mapped[str] = mapped_column(String(40))
    target_value: Mapped[int] = mapped_column(Integer, default=1)
    # Recalculado a partir da atividade real; nunca marcado à mão.
    current_value: Mapped[int] = mapped_column(Integer, default=0)
    baseline_value: Mapped[int] = mapped_column(Integer, default=0)

    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    priority: Mapped[str] = mapped_column(String(10), default="MEDIUM")
    difficulty: Mapped[str] = mapped_column(String(10), default="MEDIA")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=15)
    status: Mapped[str] = mapped_column(String(20), default=MissionStatus.PENDING)

    generated_by: Mapped[str] = mapped_column(String(10), default="RULE")
    # O número real que justificou a missão — exibido como "por quê?".
    rationale: Mapped[str] = mapped_column(String(400), default="")
    source: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    valid_from: Mapped[date] = mapped_column(Date, index=True)
    valid_until: Mapped[date] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def progress_ratio(self) -> float:
        if self.target_value <= 0:
            return 0.0
        return round(min(1.0, self.current_value / self.target_value), 4)

    @property
    def is_complete(self) -> bool:
        return self.current_value >= self.target_value


class Achievement(IdMixin, TimestampMixin, Base):
    """Definição de conquista, semeada do catálogo do domínio."""

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("slug", name="uq_achievements_slug"),)

    slug: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(400))
    category: Mapped[str] = mapped_column(String(30))
    icon: Mapped[str] = mapped_column(String(10), default="🏅")
    tier: Mapped[str] = mapped_column(String(20), default="BRONZE")
    criteria: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    # Conquista secreta não aparece antes de ser desbloqueada.
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserAchievement(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_achievements"
    __table_args__ = (
        UniqueConstraint("user_id", "achievement_id", name="uq_user_achievements_user_item"),
        Index("ix_user_achievements_user_unlocked", "user_id", "unlocked_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    achievement_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("achievements.id", ondelete="CASCADE")
    )
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    progress: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)

    achievement: Mapped[Achievement] = relationship(lazy="selectin")


class StreakDay(IdMixin, TimestampMixin, Base):
    """Um dia do histórico de constância. É daqui que sai a sequência."""

    __tablename__ = "streak_days"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_streak_days_user_day"),
        Index("ix_streak_days_user_day", "user_id", "day"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    tasks_done: Mapped[int] = mapped_column(Integer, default=0)
    mission_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    qualified: Mapped[bool] = mapped_column(Boolean, default=False)
    shield_used: Mapped[bool] = mapped_column(Boolean, default=False)


class RankSnapshot(IdMixin, TimestampMixin, Base):
    """Foto diária do rank. Sem histórico, "meu rank caiu" seria só sensação.

    Guardamos junto o XP do dia **de propósito**: é o que permite mostrar, lado a
    lado, que o acúmulo subiu e o desempenho não. Colunas separadas — o XP nunca
    entra no cálculo do rank, nem aqui nem em lugar nenhum.
    """

    __tablename__ = "rank_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "day", name="uq_rank_snapshots_user_day"),
        Index("ix_rank_snapshots_user_day", "user_id", "day"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    day: Mapped[date] = mapped_column(Date)
    rank_slug: Mapped[str] = mapped_column(String(20), default="FERRO")
    rank_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0"))
    components: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    missing_signals: Mapped[list[str]] = mapped_column(JsonType, default=list)
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)


class Season(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Um período fechado com placar próprio.

    O XP da temporada **não é um contador**: ele é somado do razão dentro da
    janela. Assim a temporada não pode divergir do extrato, e reabrir ou corrigir
    uma data recalcula o placar em vez de deixar dois números conflitantes.
    """

    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_seasons_slug"),
        Index("ix_seasons_window", "starts_on", "ends_on"),
    )

    slug: Mapped[str] = mapped_column(String(60), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(400))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Preenchido quando a temporada é fechada e as posições são congeladas.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SeasonParticipation(IdMixin, TimestampMixin, Base):
    """A posição do candidato numa temporada, congelada no fechamento."""

    __tablename__ = "season_participations"
    __table_args__ = (
        UniqueConstraint("season_id", "user_id", name="uq_season_participations_season_user"),
    )

    season_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("seasons.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    seasonal_xp: Mapped[int] = mapped_column(Integer, default=0)
    qualified_days: Mapped[int] = mapped_column(Integer, default=0)
    position: Mapped[int | None] = mapped_column(Integer)
    participants: Mapped[int] = mapped_column(Integer, default=0)
    division_index: Mapped[int] = mapped_column(Integer, default=0)
    context_label: Mapped[str] = mapped_column(String(160), default="")
    # Prêmios concedidos, com o critério que os justificou.
    rewards: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GameRun(IdMixin, PublicIdMixin, TimestampMixin, Base):
    """Uma rodada de desafio: Boss Battle, Sobrevivência, Combo ou Relógio.

    As questões são escolhidas na largada e **congeladas** em ``question_ids``.
    Sem isso, uma rodada em andamento mudaria de conteúdo a cada requisição, e o
    placar não seria reproduzível.
    """

    __tablename__ = "game_runs"
    __table_args__ = (
        Index("ix_game_runs_user_status", "user_id", "status"),
        Index("ix_game_runs_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    question_ids: Mapped[list[int]] = mapped_column(JsonType, default=list)
    # Regra da seleção, para auditoria: por que estas questões e não outras.
    selection: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    subject_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("subjects.id", ondelete="SET NULL")
    )
    subject_label: Mapped[str | None] = mapped_column(String(200))

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    score: Mapped[int] = mapped_column(Integer, default=0)
    best_combo: Mapped[int] = mapped_column(Integer, default=0)
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    achieved: Mapped[bool] = mapped_column(Boolean, default=False)
    # Placar aberto: as linhas que explicam de onde saiu o XP da rodada.
    summary: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
