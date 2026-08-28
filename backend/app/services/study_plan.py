"""Criação e manutenção do plano de estudo.

O serviço traduz o que existe no banco (edital analisado ou cargo cadastrado) para
a entrada do planejador, grava a agenda gerada e mantém o plano vivo: conclusão de
tarefas, replanejamento de atrasos e sprints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.intelligence import adjust_shares_by_priority
from app.domain.planner import (
    SubjectInput,
    SubjectShare,
    WeeklyAvailability,
    allocate_subject_shares,
    build_calendar,
    build_schedule,
    build_sprint,
)
from app.domain.planner.availability import total_available_minutes
from app.domain.planner.rebalance import PendingTask, RebalanceResult, rebalance
from app.models.audit import AuditAction
from app.models.catalog import Competition, Position, PositionSubject, Topic
from app.models.notice import Notice, NoticeStatus
from app.models.notice_analysis import NoticeSubject
from app.models.study import (
    StudyAvailability,
    StudyPlan,
    StudyPlanStatus,
    StudyTask,
    StudyTaskKind,
    StudyTaskSource,
    StudyTaskStatus,
    UserSubjectProgress,
)
from app.models.user import User
from app.repositories.intelligence import UserPriorityRepository
from app.repositories.study import (
    StudyPlanRepository,
    StudyTaskRepository,
    UserSubjectProgressRepository,
)
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

# Sem data de prova conhecida, o plano cobre um horizonte fixo — e a interface diz
# que se trata de um horizonte provisório, não de uma data real.
DEFAULT_HORIZON_DAYS = 120
MAX_HORIZON_DAYS = 730


@dataclass(frozen=True, slots=True)
class SubjectSource:
    """De onde vieram as disciplinas do plano."""

    origin: str  # NOTICE | POSITION
    subjects: list[SubjectInput]
    label: str


@dataclass(frozen=True, slots=True)
class TodayMission:
    day: date
    tasks: list[StudyTask]
    planned_minutes: int
    done_minutes: int
    overdue_count: int
    days_until_exam: int | None
    plan: StudyPlan


class StudyPlanService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.plans = StudyPlanRepository(session)
        self.tasks = StudyTaskRepository(session)
        self.progress = UserSubjectProgressRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Origem das disciplinas
    # ------------------------------------------------------------------ #
    async def _subjects_from_notice(self, notice: Notice) -> SubjectSource:
        rows = list(
            (
                await self.session.execute(
                    select(NoticeSubject)
                    .where(NoticeSubject.notice_id == notice.id)
                    .options(selectinload(NoticeSubject.topics))
                    .order_by(NoticeSubject.order_index)
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            raise ConflictError(
                "O edital analisado não trouxe disciplinas para montar o plano.",
                code="notice_without_subjects",
            )
        return SubjectSource(
            origin="NOTICE",
            label=notice.title,
            subjects=[
                SubjectInput(
                    key=f"ns:{row.public_id}",
                    name=row.raw_label,
                    weight=row.weight,
                    questions_count=row.questions_count,
                    topics_count=len(row.topics),
                    subject_id=row.subject_id,
                )
                for row in rows
            ],
        )

    async def _subjects_from_position(self, position: Position) -> SubjectSource:
        links = list(
            (
                await self.session.execute(
                    select(PositionSubject)
                    .where(PositionSubject.position_id == position.id)
                    .options(selectinload(PositionSubject.subject))
                )
            )
            .scalars()
            .all()
        )
        if not links:
            raise ConflictError(
                "O cargo escolhido ainda não tem disciplinas vinculadas.",
                code="position_without_subjects",
            )

        rows = (
            await self.session.execute(
                select(Topic.subject_id, func.count())
                .where(Topic.subject_id.in_([link.subject_id for link in links]))
                .group_by(Topic.subject_id)
            )
        ).all()
        topic_counts: dict[int, int] = {int(row[0]): int(row[1]) for row in rows}
        return SubjectSource(
            origin="POSITION",
            label=position.name,
            subjects=[
                SubjectInput(
                    key=f"sub:{link.subject.slug}",
                    name=link.subject.name,
                    weight=link.weight,
                    questions_count=link.questions_count,
                    topics_count=topic_counts.get(link.subject_id, 0),
                    color_token=link.subject.color_token,
                    subject_id=link.subject_id,
                )
                for link in links
            ],
        )

    # ------------------------------------------------------------------ #
    # Criação
    # ------------------------------------------------------------------ #
    async def create_plan(
        self,
        user: User,
        *,
        availability_minutes: dict[int, int],
        notice_public_id: str | None = None,
        position_public_id: str | None = None,
        exam_date: date | None = None,
        name: str | None = None,
        starts_on: date | None = None,
        context: RequestContext,
    ) -> StudyPlan:
        if not any(availability_minutes.values()):
            raise ValidationError(
                "Informe pelo menos um dia com tempo disponível.",
                code="empty_availability",
            )

        availability = WeeklyAvailability(availability_minutes)
        source, notice, position, competition = await self._resolve_source(
            notice_public_id, position_public_id
        )
        exam = exam_date or (competition.exam_date if competition else None)
        start = starts_on or datetime.now(UTC).date()
        end = exam or (start + timedelta(days=DEFAULT_HORIZON_DAYS))
        if end < start:
            raise ValidationError(
                "A data da prova já passou; escolha outra referência.", code="exam_in_past"
            )
        if (end - start).days > MAX_HORIZON_DAYS:
            end = start + timedelta(days=MAX_HORIZON_DAYS)

        # Um plano ativo por vez: o anterior é arquivado, não apagado.
        current = await self.plans.get_active(user.id)
        if current is not None:
            current.status = StudyPlanStatus.ARCHIVED

        plan = StudyPlan(
            user_id=user.id,
            competition_id=competition.id if competition else None,
            notice_id=notice.id if notice else None,
            position_id=position.id if position else None,
            name=name or f"Plano — {source.label}",
            exam_date=exam,
            starts_on=start,
            weekly_minutes_target=availability.weekly_minutes,
            config={"origin": source.origin, "horizon_end": end.isoformat()},
        )
        self.session.add(plan)
        await self.session.flush()

        self.session.add_all(
            [
                StudyAvailability(study_plan_id=plan.id, weekday=weekday, minutes=minutes)
                for weekday, minutes in availability_minutes.items()
                if minutes > 0
            ]
        )
        await self.session.flush()

        await self._generate_tasks(plan, source.subjects, availability, start, end, exam)

        await self.audit.record(
            AuditAction.STUDY_PLAN_CREATED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="study_plan",
            resource_id=plan.public_id,
            meta={"origin": source.origin, "weekly_minutes": availability.weekly_minutes},
        )
        await self.session.commit()
        # Releitura com as relações carregadas: o objeto recém-inserido não tem a
        # disponibilidade na sessão, e acessá-la depois dispararia lazy load.
        return await self._reload(plan.id)

    async def _reload(self, plan_id: int) -> StudyPlan:
        stmt = (
            select(StudyPlan)
            .where(StudyPlan.id == plan_id)
            .options(selectinload(StudyPlan.availability))
            .execution_options(populate_existing=True)
        )
        plan = (await self.session.execute(stmt)).scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Plano não encontrado.")
        return plan

    async def _resolve_source(
        self, notice_public_id: str | None, position_public_id: str | None
    ) -> tuple[SubjectSource, Notice | None, Position | None, Competition | None]:
        if notice_public_id:
            notice = (
                await self.session.execute(
                    select(Notice)
                    .where(Notice.public_id == notice_public_id)
                    .options(selectinload(Notice.competition))
                )
            ).scalar_one_or_none()
            if notice is None:
                raise NotFoundError("Edital não encontrado.")
            if notice.status != NoticeStatus.CONFIRMED:
                raise ConflictError(
                    "Só é possível montar o plano a partir de um edital confirmado.",
                    code="notice_not_confirmed",
                )
            source = await self._subjects_from_notice(notice)
            return source, notice, None, notice.competition

        if position_public_id:
            position = (
                await self.session.execute(
                    select(Position)
                    .where(Position.public_id == position_public_id)
                    .options(selectinload(Position.competition))
                )
            ).scalar_one_or_none()
            if position is None:
                raise NotFoundError("Cargo não encontrado.")
            source = await self._subjects_from_position(position)
            return source, None, position, position.competition

        raise ValidationError(
            "Escolha um edital confirmado ou um cargo para montar o plano.",
            code="plan_source_required",
        )

    async def _generate_tasks(
        self,
        plan: StudyPlan,
        subjects: list[SubjectInput],
        availability: WeeklyAvailability,
        start: date,
        end: date,
        exam: date | None,
    ) -> int:
        calendar = build_calendar(availability, start=start, end=end)
        total_minutes = total_available_minutes(calendar)
        shares = allocate_subject_shares(subjects, total_minutes)
        shares = await self._apply_priority(plan.user_id, shares, total_minutes)
        schedule = build_schedule(calendar=calendar, shares=shares, exam_date=exam)

        colors = {subject.key: subject.color_token for subject in subjects}
        self.session.add_all(
            [
                StudyTask(
                    study_plan_id=plan.id,
                    user_id=plan.user_id,
                    scheduled_for=task.day,
                    kind=task.kind,
                    subject_key=task.subject_key,
                    subject_label=task.subject_name,
                    color_token=colors.get(task.subject_key or "", "subject-especifica"),
                    planned_minutes=task.minutes,
                    order_index=task.order_index,
                    source=StudyTaskSource.PLANNER,
                    score_breakdown=dict(task.reason),
                )
                for task in schedule.tasks
            ]
        )

        plan.config = {
            **plan.config,
            "shares": [
                {
                    "key": share.key,
                    "name": share.name,
                    "share": share.share,
                    "minutes": share.minutes,
                    "breakdown": share.breakdown,
                }
                for share in shares
            ],
            "minutes_by_kind": schedule.minutes_by_kind,
            "total_planned_minutes": schedule.total_minutes,
        }
        plan.generated_at = datetime.now(UTC)
        await self.session.flush()
        await self._sync_progress_rows(plan, shares)
        logger.info(
            "study_plan.generated",
            plan=plan.public_id,
            tasks=len(schedule.tasks),
            minutes=schedule.total_minutes,
        )
        return len(schedule.tasks)

    async def _apply_priority(
        self, user_id: int, shares: list[SubjectShare], total_minutes: int
    ) -> list[SubjectShare]:
        """Inclina a divisão do tempo na direção do Priority Score, quando ele existe.

        Sem score calculado, nada muda: a linha de base do edital continua valendo,
        e a interface diz que a personalização por desempenho ainda não entrou.
        """
        scores = await UserPriorityRepository(self.session).scores_by_scope(user_id)
        if not scores:
            return shares

        baseline = {share.key: share.share for share in shares}
        adjusted = adjust_shares_by_priority(baseline, scores)
        result: list[SubjectShare] = []
        for share in shares:
            new_share = adjusted.get(share.key, share.share)
            breakdown = dict(share.breakdown)
            score = scores.get(share.key)
            if score is not None:
                breakdown["prioridade_por_desempenho"] = score
                breakdown["ajuste_de_tempo"] = round(new_share - share.share, 6)
            result.append(
                SubjectShare(
                    key=share.key,
                    name=share.name,
                    share=round(new_share, 6),
                    minutes=round(total_minutes * new_share),
                    color_token=share.color_token,
                    subject_id=share.subject_id,
                    breakdown=breakdown,
                )
            )
        return result

    async def _sync_progress_rows(self, plan: StudyPlan, shares: list[Any]) -> None:
        existing = {row.subject_key: row for row in await self.progress.list_for_user(plan.user_id)}
        for share in shares:
            row = existing.get(share.key)
            if row is None:
                # Os defaults do modelo só valem no INSERT; a linha nova precisa
                # nascer com os contadores zerados para as contas abaixo.
                row = UserSubjectProgress(
                    user_id=plan.user_id,
                    subject_key=share.key,
                    subject_label=share.name,
                    subject_id=share.subject_id,
                    color_token=share.color_token,
                    planned_minutes=0,
                    studied_minutes=0,
                    tasks_done=0,
                    tasks_skipped=0,
                    completion=Decimal("0"),
                )
                self.session.add(row)
            row.subject_label = share.name
            row.subject_id = share.subject_id
            row.planned_minutes = share.minutes
            row.completion = (
                Decimal(str(round(min(1.0, row.studied_minutes / share.minutes), 4)))
                if share.minutes
                else Decimal("0")
            )
        await self.session.flush()

    # ------------------------------------------------------------------ #
    # Uso diário
    # ------------------------------------------------------------------ #
    async def get_active_plan(self, user: User) -> StudyPlan:
        plan = await self.plans.get_active(user.id)
        if plan is None:
            raise NotFoundError(
                "Você ainda não tem um plano de estudo ativo.", code="no_active_plan"
            )
        return plan

    async def today_mission(self, user: User, *, day: date | None = None) -> TodayMission:
        plan = await self.get_active_plan(user)
        target = day or datetime.now(UTC).date()
        tasks = list(await self.tasks.for_day(user.id, target))
        overdue = await self.tasks.overdue(user.id, target)

        return TodayMission(
            day=target,
            tasks=tasks,
            planned_minutes=sum(
                task.planned_minutes for task in tasks if task.status != StudyTaskStatus.DROPPED
            ),
            done_minutes=sum(
                task.actual_minutes for task in tasks if task.status == StudyTaskStatus.DONE
            ),
            overdue_count=len(overdue),
            days_until_exam=(plan.exam_date - target).days if plan.exam_date else None,
            plan=plan,
        )

    async def complete_task(
        self, user: User, public_id: str, *, minutes: int | None = None
    ) -> StudyTask:
        task = await self._get_task(user, public_id)
        task.status = StudyTaskStatus.DONE
        task.actual_minutes = minutes if minutes is not None else task.planned_minutes
        task.completed_at = datetime.now(UTC)
        await self._apply_progress(task, done=True)
        await self.session.commit()
        return task

    async def skip_task(self, user: User, public_id: str) -> StudyTask:
        task = await self._get_task(user, public_id)
        task.status = StudyTaskStatus.SKIPPED
        await self._apply_progress(task, done=False)
        await self.session.commit()
        return task

    async def reopen_task(self, user: User, public_id: str) -> StudyTask:
        task = await self._get_task(user, public_id)
        if task.status == StudyTaskStatus.DONE:
            await self._apply_progress(task, done=True, undo=True)
        task.status = StudyTaskStatus.PENDING
        task.actual_minutes = 0
        task.completed_at = None
        await self.session.commit()
        return task

    async def _get_task(self, user: User, public_id: str) -> StudyTask:
        task = await self.tasks.get_by_public_id(public_id, user.id)
        if task is None:
            raise NotFoundError("Tarefa não encontrada.")
        return task

    async def _apply_progress(self, task: StudyTask, *, done: bool, undo: bool = False) -> None:
        if not task.subject_key:
            return
        row = await self.progress.get_for_subject(task.user_id, task.subject_key)
        if row is None:
            row = UserSubjectProgress(
                user_id=task.user_id,
                subject_key=task.subject_key,
                subject_label=task.subject_label or task.subject_key,
                color_token=task.color_token,
                planned_minutes=0,
                studied_minutes=0,
                tasks_done=0,
                tasks_skipped=0,
                completion=Decimal("0"),
            )
            self.session.add(row)
            await self.session.flush()

        sign = -1 if undo else 1
        if done:
            row.studied_minutes = max(0, row.studied_minutes + sign * task.actual_minutes)
            row.tasks_done = max(0, row.tasks_done + sign)
            row.last_studied_at = None if undo else datetime.now(UTC)
        else:
            row.tasks_skipped += 1

        row.completion = (
            Decimal(str(round(min(1.0, row.studied_minutes / row.planned_minutes), 4)))
            if row.planned_minutes
            else Decimal("0")
        )

    # ------------------------------------------------------------------ #
    # Replanejamento
    # ------------------------------------------------------------------ #
    async def rebalance_plan(
        self, user: User, *, today: date | None = None, context: RequestContext
    ) -> RebalanceResult:
        """Redistribui atrasos respeitando o teto diário; o excedente sai do plano."""
        plan = await self.get_active_plan(user)
        target = today or datetime.now(UTC).date()
        overdue = list(await self.tasks.overdue(user.id, target))
        if not overdue:
            return RebalanceResult([], [], 0, 0)

        horizon = plan.exam_date or (target + timedelta(days=DEFAULT_HORIZON_DAYS))
        availability = WeeklyAvailability(
            {item.weekday: item.minutes for item in plan.availability}
        )
        calendar = build_calendar(availability, start=target, end=horizon)
        committed = await self.tasks.committed_minutes(plan.id, target, horizon)

        result = rebalance(
            pending=[
                PendingTask(
                    kind=task.kind,
                    subject_key=task.subject_key,
                    subject_name=task.subject_label,
                    minutes=task.planned_minutes,
                    original_day=task.scheduled_for,
                    reschedule_count=task.reschedule_count,
                    reason=dict(task.score_breakdown or {}),
                )
                for task in overdue
            ],
            calendar=calendar,
            committed_minutes=committed,
            today=target,
        )

        for task in overdue:
            task.status = StudyTaskStatus.RESCHEDULED

        colors = {task.subject_key: task.color_token for task in overdue}
        self.session.add_all(
            [
                StudyTask(
                    study_plan_id=plan.id,
                    user_id=user.id,
                    scheduled_for=planned.day,
                    kind=planned.kind,
                    subject_key=planned.subject_key,
                    subject_label=planned.subject_name,
                    color_token=colors.get(planned.subject_key, "subject-especifica"),
                    planned_minutes=planned.minutes,
                    order_index=planned.order_index,
                    source=StudyTaskSource.REBALANCE,
                    reschedule_count=int(planned.reason.get("tentativa", 1)),
                    rescheduled_from=date.fromisoformat(
                        str(planned.reason.get("remarcada_de", planned.day.isoformat()))
                    ),
                    score_breakdown=dict(planned.reason),
                )
                for planned in result.rescheduled
            ]
        )

        # O que não coube é declarado como removido — nunca vira dívida escondida.
        dropped_keys = {(item.original_day, item.subject_key, item.kind) for item in result.dropped}
        for task in overdue:
            if (task.scheduled_for, task.subject_key, task.kind) in dropped_keys:
                task.status = StudyTaskStatus.DROPPED

        plan.recalculated_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.STUDY_PLAN_REBALANCED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="study_plan",
            resource_id=plan.public_id,
            meta={
                "rescheduled": len(result.rescheduled),
                "dropped": len(result.dropped),
            },
        )
        await self.session.commit()
        return result

    async def regenerate(
        self,
        user: User,
        *,
        availability_minutes: dict[int, int] | None = None,
        context: RequestContext,
    ) -> StudyPlan:
        """Refaz a agenda futura preservando o histórico do que já foi feito."""
        plan = await self.get_active_plan(user)
        today = datetime.now(UTC).date()

        if availability_minutes:
            await self.session.execute(
                delete(StudyAvailability).where(StudyAvailability.study_plan_id == plan.id)
            )
            self.session.add_all(
                [
                    StudyAvailability(study_plan_id=plan.id, weekday=weekday, minutes=minutes)
                    for weekday, minutes in availability_minutes.items()
                    if minutes > 0
                ]
            )
            plan.weekly_minutes_target = sum(availability_minutes.values())
            await self.session.flush()
            plan = await self._reload(plan.id)

        # Só o futuro pendente é descartado: o passado é histórico do candidato.
        await self.session.execute(
            delete(StudyTask).where(
                StudyTask.study_plan_id == plan.id,
                StudyTask.scheduled_for >= today,
                StudyTask.status == StudyTaskStatus.PENDING,
            )
        )

        availability = WeeklyAvailability(
            {item.weekday: item.minutes for item in plan.availability}
        )
        source_subjects = await self._current_subjects(plan)
        horizon = plan.exam_date or (today + timedelta(days=DEFAULT_HORIZON_DAYS))
        await self._generate_tasks(
            plan, source_subjects, availability, today, horizon, plan.exam_date
        )

        plan.recalculated_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.STUDY_PLAN_REGENERATED,
            actor=user,
            actor_ip=context.ip_address,
            resource_type="study_plan",
            resource_id=plan.public_id,
        )
        await self.session.commit()
        return await self._reload(plan.id)

    async def _current_subjects(self, plan: StudyPlan) -> list[SubjectInput]:
        if plan.notice_id:
            notice = await self.session.get(Notice, plan.notice_id)
            if notice is not None:
                return (await self._subjects_from_notice(notice)).subjects
        if plan.position_id:
            position = await self.session.get(Position, plan.position_id)
            if position is not None:
                return (await self._subjects_from_position(position)).subjects
        raise ConflictError(
            "A origem das disciplinas deste plano não está mais disponível.",
            code="plan_source_missing",
        )

    # ------------------------------------------------------------------ #
    # Sprint
    # ------------------------------------------------------------------ #
    async def create_sprint(
        self, user: User, minutes: int, *, subject_key: str | None = None
    ) -> list[StudyTask]:
        """Monta um estudo para o tempo disponível agora, já como tarefas do dia."""
        plan = await self.get_active_plan(user)
        today = datetime.now(UTC).date()

        subject_label: str | None = None
        color = "subject-especifica"
        if subject_key:
            row = await self.progress.get_for_subject(user.id, subject_key)
            if row is None:
                raise NotFoundError("Disciplina não encontrada no seu plano.")
            subject_label = row.subject_label
            color = row.color_token

        sprint = build_sprint(
            minutes, focus_subject_key=subject_key, focus_subject_name=subject_label
        )
        existing = len(list(await self.tasks.for_day(user.id, today)))

        created = [
            StudyTask(
                study_plan_id=plan.id,
                user_id=user.id,
                scheduled_for=today,
                kind=block.kind,
                subject_key=block.subject_key,
                subject_label=block.subject_name,
                color_token=color,
                planned_minutes=block.minutes,
                order_index=existing + index,
                source=StudyTaskSource.SPRINT,
                score_breakdown={
                    "motivo": "sprint pedido pelo candidato",
                    "duracao_solicitada": minutes,
                },
            )
            for index, block in enumerate(sprint.blocks)
        ]
        self.session.add_all(created)
        await self.session.commit()
        logger.info("study_plan.sprint", user=user.public_id, minutes=minutes)
        return created


_KIND_LABELS: dict[str, str] = {
    StudyTaskKind.THEORY.value: "Teoria",
    StudyTaskKind.QUESTIONS.value: "Questões",
    StudyTaskKind.REVIEW.value: "Revisão",
    StudyTaskKind.FLASHCARDS.value: "Flashcards",
    StudyTaskKind.SIMULATION.value: "Simulado",
    StudyTaskKind.SPRINT.value: "Sprint",
}


def kind_label(kind: str) -> str:
    return _KIND_LABELS.get(kind, kind)
