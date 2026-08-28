"""Plano de estudo, missão do dia, calendário, sprint e cronômetro."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, RequestCtx, rate_limit
from app.models.study import StudyPlan, StudyTask, StudyTaskStatus
from app.repositories.study import (
    StudySessionRepository,
    StudyTaskRepository,
    UserSubjectProgressRepository,
)
from app.schemas.study import (
    WEEKDAY_LABELS,
    AvailabilityRead,
    CalendarDayRead,
    CalendarRead,
    RebalanceRead,
    SessionFinishInput,
    SessionRead,
    SessionStartInput,
    SprintInput,
    StudyPlanCreate,
    StudyPlanRead,
    StudyPlanUpdate,
    StudyTaskRead,
    SubjectProgressRead,
    SubjectShareRead,
    TaskCompleteInput,
    TodayMissionRead,
)
from app.services.study_plan import StudyPlanService, kind_label
from app.services.study_session import StudySessionService

router = APIRouter(prefix="/study", tags=["estudo"])

MAX_CALENDAR_DAYS = 120


def _task_read(task: StudyTask) -> StudyTaskRead:
    data = StudyTaskRead.model_validate(task)
    return data.model_copy(update={"kind_label": kind_label(task.kind)})


def _plan_read(plan: StudyPlan, *, today: date | None = None) -> StudyPlanRead:
    config = plan.config or {}
    reference = today or datetime.now(UTC).date()
    return StudyPlanRead(
        public_id=plan.public_id,
        name=plan.name,
        status=plan.status,
        exam_date=plan.exam_date,
        starts_on=plan.starts_on,
        weekly_minutes_target=plan.weekly_minutes_target,
        generated_at=plan.generated_at,
        recalculated_at=plan.recalculated_at,
        availability=[
            AvailabilityRead(
                weekday=item.weekday,
                minutes=item.minutes,
                label=WEEKDAY_LABELS[item.weekday],
            )
            for item in sorted(plan.availability, key=lambda item: item.weekday)
        ],
        shares=[SubjectShareRead(**share) for share in config.get("shares", [])],
        minutes_by_kind=config.get("minutes_by_kind", {}),
        total_planned_minutes=config.get("total_planned_minutes", 0),
        days_until_exam=(plan.exam_date - reference).days if plan.exam_date else None,
    )


@router.post(
    "/plan",
    status_code=status.HTTP_201_CREATED,
    response_model=StudyPlanRead,
    summary="Criar plano de estudo",
    dependencies=[Depends(rate_limit("10/hour", scope="study:plan"))],
)
async def create_plan(
    payload: StudyPlanCreate, user: CurrentUser, db: DbSession, ctx: RequestCtx
) -> StudyPlanRead:
    plan = await StudyPlanService(db).create_plan(
        user,
        availability_minutes=payload.minutes_by_weekday,
        notice_public_id=payload.notice_public_id,
        position_public_id=payload.position_public_id,
        exam_date=payload.exam_date,
        name=payload.name,
        context=ctx,
    )
    return _plan_read(plan)


@router.get("/plan", response_model=StudyPlanRead, summary="Meu plano ativo")
async def get_plan(user: CurrentUser, db: DbSession) -> StudyPlanRead:
    return _plan_read(await StudyPlanService(db).get_active_plan(user))


@router.patch(
    "/plan", response_model=StudyPlanRead, summary="Atualizar disponibilidade e refazer a agenda"
)
async def update_plan(
    payload: StudyPlanUpdate, user: CurrentUser, db: DbSession, ctx: RequestCtx
) -> StudyPlanRead:
    plan = await StudyPlanService(db).regenerate(
        user, availability_minutes=payload.minutes_by_weekday, context=ctx
    )
    return _plan_read(plan)


@router.get("/today", response_model=TodayMissionRead, summary="Sua missão de hoje")
async def today(
    user: CurrentUser,
    db: DbSession,
    day: Annotated[date | None, Query(description="Padrão: hoje")] = None,
) -> TodayMissionRead:
    mission = await StudyPlanService(db).today_mission(user, day=day)
    return TodayMissionRead(
        day=mission.day,
        plan_public_id=mission.plan.public_id,
        plan_name=mission.plan.name,
        days_until_exam=mission.days_until_exam,
        planned_minutes=mission.planned_minutes,
        done_minutes=mission.done_minutes,
        overdue_count=mission.overdue_count,
        tasks=[_task_read(task) for task in mission.tasks],
    )


@router.get("/calendar", response_model=CalendarRead, summary="Agenda por período")
async def calendar(
    user: CurrentUser,
    db: DbSession,
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
) -> CalendarRead:
    service = StudyPlanService(db)
    plan = await service.get_active_plan(user)
    first = start or datetime.now(UTC).date()
    last = end or (first + timedelta(days=30))
    if (last - first).days > MAX_CALENDAR_DAYS:
        last = first + timedelta(days=MAX_CALENDAR_DAYS)

    tasks = await StudyTaskRepository(db).for_range(user.id, first, last)
    by_day: dict[date, list[StudyTask]] = {}
    for task in tasks:
        by_day.setdefault(task.scheduled_for, []).append(task)

    days = [
        CalendarDayRead(
            day=day,
            planned_minutes=sum(
                task.planned_minutes for task in items if task.status != StudyTaskStatus.DROPPED
            ),
            done_minutes=sum(
                task.actual_minutes for task in items if task.status == StudyTaskStatus.DONE
            ),
            tasks=[_task_read(task) for task in items],
        )
        for day, items in sorted(by_day.items())
    ]
    return CalendarRead(start=first, end=last, days=days, exam_date=plan.exam_date)


@router.post("/tasks/{public_id}/complete", response_model=StudyTaskRead, summary="Concluir tarefa")
async def complete_task(
    public_id: str, payload: TaskCompleteInput, user: CurrentUser, db: DbSession
) -> StudyTaskRead:
    task = await StudyPlanService(db).complete_task(user, public_id, minutes=payload.minutes)
    return _task_read(task)


@router.post("/tasks/{public_id}/skip", response_model=StudyTaskRead, summary="Pular tarefa")
async def skip_task(public_id: str, user: CurrentUser, db: DbSession) -> StudyTaskRead:
    return _task_read(await StudyPlanService(db).skip_task(user, public_id))


@router.post("/tasks/{public_id}/reopen", response_model=StudyTaskRead, summary="Reabrir tarefa")
async def reopen_task(public_id: str, user: CurrentUser, db: DbSession) -> StudyTaskRead:
    return _task_read(await StudyPlanService(db).reopen_task(user, public_id))


@router.post(
    "/rebalance",
    response_model=RebalanceRead,
    summary="Replanejar os atrasos",
    dependencies=[Depends(rate_limit("20/hour", scope="study:rebalance"))],
)
async def rebalance_plan(user: CurrentUser, db: DbSession, ctx: RequestCtx) -> RebalanceRead:
    result = await StudyPlanService(db).rebalance_plan(user, context=ctx)
    return RebalanceRead(
        rescheduled=len(result.rescheduled),
        dropped=len(result.dropped),
        dropped_minutes=result.dropped_minutes,
        days_touched=result.days_touched,
        summary=result.summary,
    )


@router.post(
    "/sprint",
    status_code=status.HTTP_201_CREATED,
    response_model=list[StudyTaskRead],
    summary="Montar um sprint com o tempo disponível agora",
)
async def create_sprint(
    payload: SprintInput, user: CurrentUser, db: DbSession
) -> list[StudyTaskRead]:
    tasks = await StudyPlanService(db).create_sprint(
        user, payload.minutes, subject_key=payload.subject_key
    )
    return [_task_read(task) for task in tasks]


@router.get(
    "/progress", response_model=list[SubjectProgressRead], summary="Progresso por disciplina"
)
async def progress(user: CurrentUser, db: DbSession) -> list[SubjectProgressRead]:
    rows = await UserSubjectProgressRepository(db).list_for_user(user.id)
    return [SubjectProgressRead.model_validate(row) for row in rows]


# --------------------------------------------------------------------------- #
# Cronômetro
# --------------------------------------------------------------------------- #
def _session_read(record: object) -> SessionRead:
    data = SessionRead.model_validate(record)
    task = getattr(record, "task", None)
    return data.model_copy(update={"task_public_id": task.public_id if task else None})


@router.get("/sessions/current", response_model=SessionRead | None, summary="Sessão em andamento")
async def current_session(user: CurrentUser, db: DbSession) -> SessionRead | None:
    record = await StudySessionService(db).current(user)
    return _session_read(record) if record else None


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionRead,
    summary="Iniciar cronômetro",
)
async def start_session(
    payload: SessionStartInput, user: CurrentUser, db: DbSession
) -> SessionRead:
    record = await StudySessionService(db).start(user, task_public_id=payload.task_public_id)
    return _session_read(record)


@router.post("/sessions/{public_id}/pause", response_model=SessionRead, summary="Pausar")
async def pause_session(public_id: str, user: CurrentUser, db: DbSession) -> SessionRead:
    return _session_read(await StudySessionService(db).pause(user, public_id))


@router.post("/sessions/{public_id}/resume", response_model=SessionRead, summary="Retomar")
async def resume_session(public_id: str, user: CurrentUser, db: DbSession) -> SessionRead:
    return _session_read(await StudySessionService(db).resume(user, public_id))


@router.post("/sessions/{public_id}/finish", response_model=SessionRead, summary="Finalizar")
async def finish_session(
    public_id: str, payload: SessionFinishInput, user: CurrentUser, db: DbSession
) -> SessionRead:
    record = await StudySessionService(db).finish(user, public_id, notes=payload.notes)
    return _session_read(record)


@router.get(
    "/sessions/week-minutes",
    response_model=dict[str, int],
    summary="Minutos estudados nos últimos 7 dias",
)
async def week_minutes(user: CurrentUser, db: DbSession) -> dict[str, int]:
    """Soma o tempo real de foco — sem estimativa e sem contar tempo pausado."""
    today_date = datetime.now(UTC)
    minutes = await StudySessionRepository(db).minutes_between(
        user.id, today_date - timedelta(days=7), today_date
    )
    return {"minutes": minutes}
