"""Fase 4: duelos, eventos, Modo Guerra e card compartilhável.

O que reúne estas quatro coisas é a saída da plataforma: pela primeira vez os
números do candidato encontram outra pessoa — um adversário, um evento coletivo
ou um link publicado. É onde exagerar seria mais fácil e mais caro.

O duelo reaproveita a rodada de desafio da Fase 3: cada lado tem a sua
``GameRun``, ambas apontando para o mesmo duelo e para **a mesma lista de
questões**.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.slugify import slugify
from app.domain.game import (
    DUEL_EXPIRY_HOURS,
    DUEL_SPEC,
    CardInput,
    DayActivity,
    DuelOutcome,
    DuelResult,
    DuelSide,
    DuelStatus,
    EventGoal,
    EventProgress,
    RunStatus,
    ShareCard,
    WarPlan,
    WarProgress,
    WarStatus,
    build_card,
    build_progress,
    evaluate_event,
    evaluate_run,
    resolve,
    review_plan,
    validate_goals,
    validate_plan,
)
from app.domain.game.challenges import RunAnswer
from app.models.flashcard import FlashcardReview
from app.models.game import (
    Duel,
    EventParticipation,
    GameRun,
    ShareCardRecord,
    SpecialEvent,
    StreakDay,
    WarCampaign,
)
from app.models.question import QuestionAttempt
from app.models.study import StudyPlan, StudyPlanStatus, StudySession
from app.models.user import User
from app.repositories.game import (
    DuelRepository,
    EventParticipationRepository,
    ShareCardRepository,
    SpecialEventRepository,
    WarCampaignRepository,
)
from app.repositories.question import QuestionRepository
from app.services.game_challenges import ChallengeService
from app.services.game_engine import GameEngine

logger = get_logger(__name__)

# Quantos dias de histórico são olhados para avisar sobre uma meta irrealista.
HISTORY_WINDOW_DAYS = 21

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _duel_code() -> str:
    """Código curto, sem caracteres que se confundem ao ler em voz alta."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


@dataclass(frozen=True, slots=True)
class DuelView:
    duel: Duel
    result: DuelResult
    my_run: GameRun | None
    is_challenger: bool
    challenger_name: str
    opponent_name: str | None


class SocialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.duels = DuelRepository(session)
        self.events = SpecialEventRepository(session)
        self.participations = EventParticipationRepository(session)
        self.campaigns = WarCampaignRepository(session)
        self.cards = ShareCardRepository(session)
        self.questions = QuestionRepository(session)
        self.engine = GameEngine(session)
        self.challenges = ChallengeService(session)

    # ------------------------------------------------------------------ #
    # Duelos
    # ------------------------------------------------------------------ #
    async def _display_name(self, user: User) -> str:
        """O nome que o adversário vê. Anonimato continua sendo o padrão."""
        profile = await self.engine.profile_for(user)
        return profile.league_display_name or "Candidato"

    async def _side(self, run: GameRun | None, name: str, key: str) -> DuelSide:
        if run is None:
            return DuelSide(user_key=key, display_name=name)

        rows = list(
            (
                await self.session.execute(
                    select(QuestionAttempt)
                    .where(QuestionAttempt.game_run_id == run.id)
                    .order_by(QuestionAttempt.id)
                )
            )
            .scalars()
            .all()
        )
        answers = [
            RunAnswer(is_correct=bool(item.is_correct), time_seconds=item.time_seconds)
            for item in rows
        ]
        state = evaluate_run(DUEL_SPEC, answers, elapsed_seconds=0)
        return DuelSide(
            user_key=key,
            display_name=name,
            answered=state.answered,
            correct=state.correct,
            time_seconds=sum(item.time_seconds for item in rows),
            finished=run.status != RunStatus.RUNNING,
        )

    async def _runs(self, duel: Duel) -> dict[int, GameRun]:
        rows = (
            (await self.session.execute(select(GameRun).where(GameRun.duel_id == duel.id)))
            .scalars()
            .all()
        )
        return {row.user_id: row for row in rows}

    async def _start_side(self, user: User, duel: Duel) -> GameRun:
        """Cria a rodada daquele lado com a lista de questões do duelo."""
        run = GameRun(
            user_id=user.id,
            duel_id=duel.id,
            mode=DUEL_SPEC.mode,
            status=RunStatus.RUNNING,
            question_ids=list(duel.question_ids),
            selection={"rule": "questões do duelo — as mesmas para os dois lados"},
            started_at=datetime.now(UTC),
        )
        self.session.add(run)
        await self.session.commit()
        return run

    async def create_duel(self, user: User) -> DuelView:
        running = await self.challenges.runs.running_for(user.id)
        if running is not None:
            raise ConflictError(
                "Termine a rodada em andamento antes de abrir um duelo.",
                code="run_already_running",
            )

        questions = list(await self.questions.pick_for_simulation(limit=DUEL_SPEC.questions))
        if len(questions) < DUEL_SPEC.questions:
            raise ConflictError(
                (
                    f"O banco tem {len(questions)} questão(ões) e o duelo precisa de "
                    f"{DUEL_SPEC.questions}. O convite não foi criado."
                ),
                code="not_enough_questions",
            )

        duel = Duel(
            code=_duel_code(),
            challenger_id=user.id,
            status=DuelStatus.OPEN,
            question_ids=[item.id for item in questions],
            expires_at=datetime.now(UTC) + timedelta(hours=DUEL_EXPIRY_HOURS),
        )
        self.session.add(duel)
        try:
            await self.session.commit()
        except IntegrityError:
            # Colisão de código: sorteia outro em vez de falhar para o candidato.
            await self.session.rollback()
            duel.code = _duel_code()
            self.session.add(duel)
            await self.session.commit()

        await self._start_side(user, duel)
        logger.info("duel.created", user=user.public_id, code=duel.code)
        return await self.duel_view(user, duel.public_id)

    async def accept_duel(self, user: User, code: str) -> DuelView:
        duel = await self.duels.get_by_code(code.strip().upper())
        if duel is None:
            raise NotFoundError("Desafio não encontrado.")
        if duel.challenger_id == user.id:
            raise ValidationError(
                "Você não pode aceitar o próprio desafio.", code="cannot_duel_yourself"
            )
        if duel.opponent_id is not None:
            raise ConflictError("Este desafio já tem adversário.", code="duel_already_taken")
        if self._expired(duel):
            raise ConflictError("Este convite expirou.", code="duel_expired")

        duel.opponent_id = user.id
        duel.status = DuelStatus.RUNNING
        await self.session.commit()
        await self._start_side(user, duel)

        logger.info("duel.accepted", user=user.public_id, code=duel.code)
        return await self.duel_view(user, duel.public_id)

    def _expired(self, duel: Duel) -> bool:
        expires = duel.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return datetime.now(UTC) > expires

    async def duel_view(self, user: User, public_id: str) -> DuelView:
        duel = await self.duels.get_by_public_id(public_id)
        if duel is None:
            raise NotFoundError("Desafio não encontrado.")
        if user.id not in {duel.challenger_id, duel.opponent_id}:
            raise NotFoundError("Desafio não encontrado.")

        challenger = await self.session.get(User, duel.challenger_id)
        opponent = await self.session.get(User, duel.opponent_id) if duel.opponent_id else None
        assert challenger is not None

        challenger_name = await self._display_name(challenger)
        opponent_name = await self._display_name(opponent) if opponent else None

        runs = await self._runs(duel)
        challenger_side = await self._side(
            runs.get(duel.challenger_id), challenger_name, challenger.public_id
        )
        opponent_side = (
            await self._side(runs.get(opponent.id), opponent_name or "", opponent.public_id)
            if opponent
            else None
        )

        expired = self._expired(duel)
        result = resolve(challenger_side, opponent_side, expired=expired)

        # O resultado é congelado assim que deixa de ser indefinido.
        if duel.status not in {DuelStatus.FINISHED, DuelStatus.CANCELED} and result.outcome not in {
            DuelOutcome.UNDECIDED
        }:
            duel.status = (
                DuelStatus.EXPIRED
                if result.outcome == DuelOutcome.EXPIRED
                else (DuelStatus.FINISHED)
            )
            duel.outcome = result.outcome
            duel.resolved_at = datetime.now(UTC)
            duel.result = {"headline": result.headline, "lines": list(result.lines)}
            if result.winner_key == challenger.public_id:
                duel.winner_id = challenger.id
            elif opponent is not None and result.winner_key == opponent.public_id:
                duel.winner_id = opponent.id
            await self.session.commit()

        return DuelView(
            duel=duel,
            result=result,
            my_run=runs.get(user.id),
            is_challenger=duel.challenger_id == user.id,
            challenger_name=challenger_name,
            opponent_name=opponent_name,
        )

    async def duel_history(self, user: User) -> list[Duel]:
        return list(await self.duels.for_user(user.id))

    # ------------------------------------------------------------------ #
    # Eventos
    # ------------------------------------------------------------------ #
    async def _window_metrics(self, user: User, starts_on: date, ends_on: date) -> dict[str, int]:
        """Os mesmos números do resto da plataforma, recortados pela janela."""
        focus_seconds = int(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(StudySession.focus_seconds), 0)).where(
                        StudySession.user_id == user.id,
                        func.date(StudySession.started_at) >= starts_on,
                        func.date(StudySession.started_at) <= ends_on,
                    )
                )
            ).scalar_one()
        )
        questions = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        QuestionAttempt.user_id == user.id,
                        func.date(QuestionAttempt.created_at) >= starts_on,
                        func.date(QuestionAttempt.created_at) <= ends_on,
                    )
                )
            ).scalar_one()
        )
        reviews = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        FlashcardReview.user_id == user.id,
                        func.date(FlashcardReview.created_at) >= starts_on,
                        func.date(FlashcardReview.created_at) <= ends_on,
                    )
                )
            ).scalar_one()
        )
        challenges = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        GameRun.user_id == user.id,
                        GameRun.status == RunStatus.FINISHED,
                        func.date(GameRun.ended_at) >= starts_on,
                        func.date(GameRun.ended_at) <= ends_on,
                    )
                )
            ).scalar_one()
        )
        qualified = int(
            (
                await self.session.execute(
                    select(func.count()).where(
                        StreakDay.user_id == user.id,
                        StreakDay.qualified.is_(True),
                        StreakDay.day >= starts_on,
                        StreakDay.day <= ends_on,
                    )
                )
            ).scalar_one()
        )
        return {
            "focus_minutes": focus_seconds // 60,
            "questions": questions,
            "reviews": reviews,
            "challenges": challenges,
            "qualified_days": qualified,
        }

    async def event_progress(
        self, user: User, event: SpecialEvent, *, today: date | None = None
    ) -> EventProgress:
        day = today or datetime.now(UTC).date()
        goals = [EventGoal(item["metric"], int(item["target"])) for item in event.goals or []]
        metrics = await self._window_metrics(user, event.starts_on, event.ends_on)
        progress = evaluate_event(
            goals,
            metrics,
            starts_on=event.starts_on,
            ends_on=event.ends_on,
            today=day,
            reward_label=event.reward_label,
            reward_utility=event.reward_utility,
        )

        record = await self.participations.get_for(event.id, user.id)
        if record is None:
            record = EventParticipation(event_id=event.id, user_id=user.id)
            self.session.add(record)
        record.progress = [
            {
                "metric": item.metric,
                "label": item.label,
                "current": item.current,
                "target": item.target,
                "completed": item.completed,
            }
            for item in progress.goals
        ]
        if progress.completed and not record.completed:
            record.completed = True
            record.completed_at = datetime.now(UTC)
        await self.session.commit()
        return progress

    async def open_events(
        self, user: User, *, today: date | None = None
    ) -> list[tuple[SpecialEvent, EventProgress]]:
        day = today or datetime.now(UTC).date()
        events = list(await self.events.open_on(day))
        return [(event, await self.event_progress(user, event, today=day)) for event in events]

    async def create_event(
        self,
        *,
        name: str,
        starts_on: date,
        ends_on: date,
        goals: list[dict[str, int | str]],
        description: str | None = None,
        reward_label: str | None = None,
        reward_utility: str | None = None,
    ) -> SpecialEvent:
        parsed = [EventGoal(str(item["metric"]), int(item["target"])) for item in goals]
        errors = validate_goals(parsed)
        if ends_on < starts_on:
            errors.append("O evento termina antes de começar.")
        if reward_label and not reward_utility:
            # Prêmio sem utilidade declarada é exatamente o que esta camada não faz.
            errors.append("Todo prêmio precisa declarar para que serve.")
        if errors:
            raise ValidationError(" ".join(errors), code="invalid_event")

        event = SpecialEvent(
            slug=slugify(f"{name}-{starts_on.isoformat()}", max_length=80),
            name=name,
            description=description,
            starts_on=starts_on,
            ends_on=ends_on,
            goals=[{"metric": item.metric, "target": item.target} for item in parsed],
            reward_label=reward_label,
            reward_utility=reward_utility,
        )
        self.session.add(event)
        await self.session.commit()
        logger.info("event.created", slug=event.slug)
        return event

    # ------------------------------------------------------------------ #
    # Modo Guerra
    # ------------------------------------------------------------------ #
    async def _average_minutes(self, user: User, *, today: date) -> float | None:
        """Média diária real das últimas semanas. ``None`` sem histórico."""
        since = today - timedelta(days=HISTORY_WINDOW_DAYS)
        row = (
            await self.session.execute(
                select(
                    func.coalesce(func.sum(StreakDay.minutes), 0),
                    func.count(),
                ).where(StreakDay.user_id == user.id, StreakDay.day >= since)
            )
        ).one()
        days = int(row[1])
        if days == 0:
            return None
        return round(int(row[0]) / days, 1)

    async def start_campaign(
        self, user: User, *, days: int, daily_minutes: int, daily_questions: int
    ) -> WarCampaign:
        running = await self.campaigns.running_for(user.id)
        if running is not None:
            raise ConflictError(
                "Você já tem um Modo Guerra em andamento.", code="campaign_already_running"
            )

        plan = WarPlan(days=days, daily_minutes=daily_minutes, daily_questions=daily_questions)
        errors = validate_plan(plan)
        if errors:
            raise ValidationError(" ".join(errors), code="invalid_war_plan")

        today = datetime.now(UTC).date()
        warnings = review_plan(plan, average_minutes=await self._average_minutes(user, today=today))

        campaign = WarCampaign(
            user_id=user.id,
            status=WarStatus.RUNNING,
            starts_on=today,
            days=days,
            daily_minutes=daily_minutes,
            daily_questions=daily_questions,
            warnings=[{"field": item.field_name, "message": item.message} for item in warnings],
        )
        self.session.add(campaign)
        await self.session.commit()
        logger.info("war.started", user=user.public_id, days=days)
        return campaign

    async def campaign_progress(
        self, campaign: WarCampaign, *, today: date | None = None
    ) -> WarProgress:
        day = today or datetime.now(UTC).date()
        ends_on = campaign.starts_on + timedelta(days=campaign.days - 1)

        rows = (
            await self.session.execute(
                select(StreakDay.day, StreakDay.minutes).where(
                    StreakDay.user_id == campaign.user_id,
                    StreakDay.day >= campaign.starts_on,
                    StreakDay.day <= ends_on,
                )
            )
        ).all()
        questions = (
            await self.session.execute(
                select(
                    func.date(QuestionAttempt.created_at),
                    func.count(),
                )
                .where(
                    QuestionAttempt.user_id == campaign.user_id,
                    func.date(QuestionAttempt.created_at) >= campaign.starts_on,
                    func.date(QuestionAttempt.created_at) <= ends_on,
                )
                .group_by(func.date(QuestionAttempt.created_at))
            )
        ).all()

        by_day: dict[date, list[int]] = {}
        for row in rows:
            by_day.setdefault(row[0], [0, 0])[0] = int(row[1])
        for row in questions:
            key = row[0] if isinstance(row[0], date) else date.fromisoformat(str(row[0]))
            by_day.setdefault(key, [0, 0])[1] = int(row[1])

        activity = [
            DayActivity(day=key, minutes=value[0], questions=value[1])
            for key, value in by_day.items()
        ]
        return build_progress(
            WarPlan(campaign.days, campaign.daily_minutes, campaign.daily_questions),
            activity,
            starts_on=campaign.starts_on,
            today=day,
            status=campaign.status,
        )

    async def current_campaign(self, user: User) -> tuple[WarCampaign, WarProgress] | None:
        campaign = await self.campaigns.running_for(user.id)
        if campaign is None:
            return None

        progress = await self.campaign_progress(campaign)
        if progress.is_over and campaign.status == WarStatus.RUNNING:
            campaign.status = WarStatus.FINISHED
            campaign.ended_at = datetime.now(UTC)
            campaign.days_met = progress.days_met
            campaign.succeeded = progress.succeeded
            await self.session.commit()
        return campaign, progress

    async def abandon_campaign(self, user: User) -> WarCampaign:
        campaign = await self.campaigns.running_for(user.id)
        if campaign is None:
            raise NotFoundError("Nenhum Modo Guerra em andamento.")

        progress = await self.campaign_progress(campaign)
        campaign.status = WarStatus.ABANDONED
        campaign.ended_at = datetime.now(UTC)
        campaign.days_met = progress.days_met
        campaign.succeeded = False
        await self.session.commit()
        return campaign

    async def campaign_history(self, user: User) -> list[WarCampaign]:
        return list(await self.campaigns.history_for(user.id))

    # ------------------------------------------------------------------ #
    # Card compartilhável
    # ------------------------------------------------------------------ #
    async def build_card(
        self, user: User, *, include: set[str], display_name: str | None = None
    ) -> ShareCard:
        snapshot = await self.engine.snapshot(user)
        metrics = snapshot["metrics"]
        has_plan = (
            await self.session.execute(
                select(StudyPlan.id).where(
                    StudyPlan.user_id == user.id, StudyPlan.status == StudyPlanStatus.ACTIVE
                )
            )
        ).scalar_one_or_none() is not None

        profile = await self.engine.profile_for(user)
        name = (display_name or profile.league_display_name or "Candidato").strip()[:80]

        return build_card(
            CardInput(
                display_name=name,
                level=snapshot["level"].level,
                rank_name=snapshot["rank"].name,
                xp_total=snapshot["level"].xp_total,
                current_streak=snapshot["streak"].current,
                questions_answered=int(metrics.get("questions_answered", 0)),
                accuracy=metrics.get("accuracy"),
                reviews=int(metrics.get("flashcard_reviews", 0)),
                recall_rate=metrics.get("recall_rate"),
                coverage=metrics.get("coverage"),
                has_plan=has_plan,
            ),
            include=include,
        )

    async def publish_card(
        self, user: User, *, include: set[str], display_name: str | None = None
    ) -> ShareCardRecord:
        """Congela o card e devolve o link. Nada é publicado por padrão."""
        card = await self.build_card(user, include=include, display_name=display_name)
        record = ShareCardRecord(
            user_id=user.id,
            token=secrets.token_urlsafe(32),
            display_name=card.display_name,
            headline=card.headline,
            stats=[
                {
                    "key": item.key,
                    "label": item.label,
                    "value": item.value,
                    "detail": item.detail,
                }
                for item in card.stats
            ],
            omitted=list(card.omitted),
            footer=card.footer,
        )
        self.session.add(record)
        await self.session.commit()
        logger.info("share_card.published", user=user.public_id)
        return record

    async def public_card(self, token: str) -> ShareCardRecord:
        record = await self.cards.get_by_token(token)
        if record is None or record.revoked_at is not None:
            raise NotFoundError("Card não encontrado ou revogado.")
        return record

    async def revoke_card(self, user: User, public_id: str) -> ShareCardRecord:
        record = await self.cards.get_by(public_id=public_id, user_id=user.id)
        if record is None:
            raise NotFoundError("Card não encontrado.")
        record.revoked_at = datetime.now(UTC)
        await self.session.commit()
        return record

    async def my_cards(self, user: User) -> list[ShareCardRecord]:
        return list(await self.cards.for_user(user.id))
