"""Temporadas e ligas — o placar do período e a comparação por contexto.

O XP da temporada é **somado do razão** dentro da janela, nunca acumulado num
contador próprio. Isso custa uma consulta a mais e paga com o que importa: a
temporada não tem como divergir do extrato que o candidato pode auditar.

A liga junta quem disputa o mesmo cargo. Comparar candidatos de concursos
diferentes não informaria nada — e ainda desanimaria quem estuda para uma prova
mais difícil (item 21 do pedido).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.slugify import slugify
from app.domain.game import (
    League,
    LeagueEntry,
    SeasonOutcome,
    SeasonStanding,
    SeasonWindow,
    build_league,
    rewards_for,
)
from app.domain.game.seasons import SEASON_LENGTH_DAYS
from app.models.catalog import Competition, Position
from app.models.game import (
    GameRun,
    GamificationProfile,
    Season,
    SeasonParticipation,
    StreakDay,
    XPTransaction,
)
from app.models.question import QuestionAttempt
from app.models.study import StudyPlan, StudyPlanStatus
from app.models.user import User
from app.repositories.game import (
    ProfileRepository,
    SeasonParticipationRepository,
    SeasonRepository,
)
from app.services.game_engine import GameEngine

logger = get_logger(__name__)

# Sem plano vinculado a um cargo, não há com quem comparar de forma honesta.
NO_CONTEXT_LABEL = ""


@dataclass(frozen=True, slots=True)
class SeasonView:
    season: Season | None
    window: SeasonWindow | None
    standing: SeasonStanding
    outcome: SeasonOutcome | None
    days_left: int | None
    progress: float
    empty_reason: str | None = None


class SeasonService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.seasons = SeasonRepository(session)
        self.participations = SeasonParticipationRepository(session)
        self.profiles = ProfileRepository(session)
        self.engine = GameEngine(session)

    # ------------------------------------------------------------------ #
    # Temporada corrente
    # ------------------------------------------------------------------ #
    async def current(self, *, today: date | None = None) -> Season | None:
        return await self.seasons.active_on(today or datetime.now(UTC).date())

    async def seasonal_xp(self, user: User, season: Season) -> int:
        """Soma do razão dentro da janela. Uma consulta, uma verdade."""
        stmt = select(func.coalesce(func.sum(XPTransaction.amount), 0)).where(
            XPTransaction.user_id == user.id,
            XPTransaction.day >= season.starts_on,
            XPTransaction.day <= season.ends_on,
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def _standing(self, user: User, season: Season) -> SeasonStanding:
        qualified = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        StreakDay.user_id == user.id,
                        StreakDay.qualified.is_(True),
                        StreakDay.day >= season.starts_on,
                        StreakDay.day <= season.ends_on,
                    )
                )
            ).scalar_one()
        )
        questions = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        QuestionAttempt.user_id == user.id,
                        func.date(QuestionAttempt.created_at) >= season.starts_on,
                        func.date(QuestionAttempt.created_at) <= season.ends_on,
                    )
                )
            ).scalar_one()
        )
        challenges = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        GameRun.user_id == user.id,
                        GameRun.status == "FINISHED",
                        func.date(GameRun.ended_at) >= season.starts_on,
                        func.date(GameRun.ended_at) <= season.ends_on,
                    )
                )
            ).scalar_one()
        )
        return SeasonStanding(
            seasonal_xp=await self.seasonal_xp(user, season),
            qualified_days=qualified,
            questions=questions,
            challenges=challenges,
        )

    async def view(self, user: User, *, today: date | None = None) -> SeasonView:
        """A temporada como o candidato a vê, com posição quando a liga existe."""
        day = today or datetime.now(UTC).date()
        season = await self.current(today=day)
        if season is None:
            return SeasonView(
                season=None,
                window=None,
                standing=SeasonStanding(),
                outcome=None,
                days_left=None,
                progress=0.0,
                empty_reason=(
                    "Nenhuma temporada aberta no momento. As temporadas são períodos "
                    "definidos pela administração — não há placar fora deles."
                ),
            )

        window = SeasonWindow(season.name, season.starts_on, season.ends_on)
        standing = await self._standing(user, season)

        league = await self.league(user, season=season)
        if league.your_position is not None:
            standing = SeasonStanding(
                seasonal_xp=standing.seasonal_xp,
                qualified_days=standing.qualified_days,
                questions=standing.questions,
                challenges=standing.challenges,
                position=league.your_division_position,
                participants=league.participants,
            )

        return SeasonView(
            season=season,
            window=window,
            standing=standing,
            outcome=rewards_for(standing),
            days_left=window.days_left(day),
            progress=window.progress(day),
        )

    # ------------------------------------------------------------------ #
    # Liga
    # ------------------------------------------------------------------ #
    async def context_of(self, user: User) -> tuple[int | None, str]:
        """O cargo-alvo do plano ativo — é ele que define com quem comparar.

        Leitura pública: o ranking da Batalha RPG compara pelo **mesmo contexto**
        da liga, e reusar esta consulta é o que garante que as duas telas não
        divirjam sobre quem disputa com quem.
        """
        plan = (
            (
                await self.session.execute(
                    select(StudyPlan)
                    .where(StudyPlan.user_id == user.id, StudyPlan.status == StudyPlanStatus.ACTIVE)
                    .order_by(StudyPlan.created_at.desc())
                    .limit(1)
                )
            )
            .scalars()
            .first()
        )
        if plan is None or plan.position_id is None:
            return None, NO_CONTEXT_LABEL

        row = (
            await self.session.execute(
                select(Position.name, Competition.name)
                .join(Competition, Competition.id == Position.competition_id)
                .where(Position.id == plan.position_id)
            )
        ).first()
        if row is None:
            return plan.position_id, NO_CONTEXT_LABEL
        return plan.position_id, f"{row[1]} · {row[0]}"

    async def league(self, user: User, *, season: Season | None = None) -> League:
        """Monta a liga do contexto do candidato, respeitando quem saiu."""
        season = season or await self.current()
        if season is None:
            return League(
                context_label="",
                participants=0,
                empty_reason="A liga existe dentro de uma temporada, e não há temporada aberta.",
            )

        profile = await self.engine.profile_for(user)
        if profile.league_opt_out:
            return League(
                context_label="",
                participants=0,
                empty_reason=(
                    "Você desligou a comparação com outros candidatos. Nada do seu estudo "
                    "depende dela — ligue quando quiser."
                ),
            )

        position_id, context_label = await self.context_of(user)
        if position_id is None:
            return League(
                context_label="",
                participants=0,
                empty_reason=(
                    "A liga compara candidatos ao mesmo cargo. Vincule seu plano a um cargo "
                    "para saber com quem você está disputando."
                ),
            )

        rows = (
            await self.session.execute(
                select(
                    User.public_id,
                    func.coalesce(func.sum(XPTransaction.amount), 0),
                    GamificationProfile.league_display_name,
                )
                .join(StudyPlan, StudyPlan.user_id == User.id)
                # Perfil de gamificação nasce no primeiro ganho de XP: quem ainda
                # não pontuou participa da liga com zero, em vez de sumir dela.
                .outerjoin(GamificationProfile, GamificationProfile.user_id == User.id)
                .outerjoin(
                    XPTransaction,
                    (XPTransaction.user_id == User.id)
                    & (XPTransaction.day >= season.starts_on)
                    & (XPTransaction.day <= season.ends_on),
                )
                .where(
                    StudyPlan.position_id == position_id,
                    StudyPlan.status == StudyPlanStatus.ACTIVE,
                    or_(
                        GamificationProfile.id.is_(None),
                        GamificationProfile.league_opt_out.is_(False),
                    ),
                )
                .group_by(User.public_id, GamificationProfile.league_display_name)
            )
        ).all()

        active_days = await self._active_days_by_user(season)
        entries = [
            LeagueEntry(
                user_key=str(row[0]),
                seasonal_xp=int(row[1]),
                active_days=active_days.get(str(row[0]), 0),
                display_name=row[2],
            )
            for row in rows
        ]
        return build_league(entries, you_key=user.public_id, context_label=context_label)

    async def _active_days_by_user(self, season: Season) -> dict[str, int]:
        rows = (
            await self.session.execute(
                select(User.public_id, func.count())
                .join(StreakDay, StreakDay.user_id == User.id)
                .where(
                    StreakDay.qualified.is_(True),
                    StreakDay.day >= season.starts_on,
                    StreakDay.day <= season.ends_on,
                )
                .group_by(User.public_id)
            )
        ).all()
        return {str(row[0]): int(row[1]) for row in rows}

    # ------------------------------------------------------------------ #
    # Preferência de comparação (item 21: desligável)
    # ------------------------------------------------------------------ #
    async def set_preferences(
        self, user: User, *, opt_out: bool | None = None, display_name: str | None = None
    ) -> GamificationProfile:
        profile = await self.engine.profile_for(user)
        if opt_out is not None:
            profile.league_opt_out = opt_out
        if display_name is not None:
            cleaned = display_name.strip()
            if len(cleaned) > 40:
                raise ValidationError("Nome de exibição muito longo.", code="display_name_too_long")
            # String vazia volta ao anonimato, que é o padrão.
            profile.league_display_name = cleaned or None
        await self.session.commit()
        return profile

    # ------------------------------------------------------------------ #
    # Administração
    # ------------------------------------------------------------------ #
    async def create(
        self,
        *,
        name: str,
        starts_on: date,
        ends_on: date | None = None,
        description: str | None = None,
    ) -> Season:
        """Cria a temporada. Janelas sobrepostas são recusadas, não acomodadas."""
        end = ends_on or (starts_on + timedelta(days=SEASON_LENGTH_DAYS - 1))
        if end < starts_on:
            raise ValidationError("A temporada termina antes de começar.", code="invalid_window")

        overlapping = (
            await self.session.execute(
                select(Season.id).where(
                    Season.is_active.is_(True),
                    Season.starts_on <= end,
                    Season.ends_on >= starts_on,
                )
            )
        ).first()
        if overlapping is not None:
            raise ConflictError(
                "Já existe uma temporada ativa nesse período.", code="season_overlap"
            )

        slug = slugify(f"{name}-{starts_on.isoformat()}", max_length=60)
        season = Season(
            slug=slug,
            name=name,
            description=description,
            starts_on=starts_on,
            ends_on=end,
            is_active=True,
        )
        self.session.add(season)
        await self.session.commit()
        logger.info("season.created", slug=slug, starts_on=str(starts_on), ends_on=str(end))
        return season

    async def close(self, slug: str) -> list[SeasonParticipation]:
        """Congela as posições e concede os prêmios de critério cumprido.

        Fechar é um ato administrativo explícito: enquanto ninguém fecha, nada é
        congelado, e o placar continua sendo recalculado do razão.
        """
        season = await self.seasons.get_by_slug(slug)
        if season is None:
            raise NotFoundError("Temporada não encontrada.")
        if season.closed_at is not None:
            raise ConflictError("Esta temporada já foi fechada.", code="season_already_closed")

        users = list(
            (
                await self.session.execute(
                    select(User)
                    .join(XPTransaction, XPTransaction.user_id == User.id)
                    .where(
                        XPTransaction.day >= season.starts_on,
                        XPTransaction.day <= season.ends_on,
                    )
                    .distinct()
                )
            )
            .scalars()
            .all()
        )

        now = datetime.now(UTC)
        records: list[SeasonParticipation] = []
        for participant in users:
            standing = await self._standing(participant, season)
            league = await self.league(participant, season=season)
            final = SeasonStanding(
                seasonal_xp=standing.seasonal_xp,
                qualified_days=standing.qualified_days,
                questions=standing.questions,
                challenges=standing.challenges,
                position=league.your_division_position,
                participants=league.participants,
            )
            outcome = rewards_for(final)

            record = await self.participations.get_for(season.id, participant.id)
            if record is None:
                record = SeasonParticipation(season_id=season.id, user_id=participant.id)
                self.session.add(record)

            record.seasonal_xp = final.seasonal_xp
            record.qualified_days = final.qualified_days
            record.position = final.position
            record.participants = final.participants
            record.division_index = league.division_index
            record.context_label = league.context_label
            record.rewards = [
                {
                    "slug": item.slug,
                    "label": item.label,
                    "utility": item.utility,
                    "criterion": item.criterion,
                }
                for item in outcome.rewards
            ]
            record.closed_at = now
            records.append(record)

            # O escudo é o único prêmio com efeito mecânico — e o efeito é este.
            if any(item.slug == "escudo-extra" for item in outcome.rewards):
                profile = await self.engine.profile_for(participant)
                profile.streak_shields_left += 1

        season.closed_at = now
        season.is_active = False
        await self.session.commit()
        logger.info("season.closed", slug=season.slug, participants=len(records))
        return records

    async def history(self, user: User) -> list[SeasonParticipation]:
        return list(await self.participations.history_for(user.id))
