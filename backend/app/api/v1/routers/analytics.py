"""Analytics: Mestre Score, projeção, caminho e painéis.

O critério de aceite da fase governa este arquivo: **todo gráfico devolve a
decisão que ele serve, e todo número estimado devolve a faixa**. Não há rota
aqui que entregue um valor solto.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.domain.analytics import Chart, ExamProjection, MasterScore, Path
from app.schemas.analytics import (
    AnalyticsOverviewRead,
    ChartRead,
    DashboardRead,
    MasterScoreRead,
    PathRead,
    PathStepRead,
    ProjectionRead,
    ScoreComponentRead,
    ScoreHistoryRead,
    ScorePointRead,
    SeriesPointRead,
    SubjectProjectionRead,
)
from app.services.analytics import HISTORY_DAYS, AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def master_score_read(score: MasterScore) -> MasterScoreRead:
    return MasterScoreRead(
        value=score.value,
        low=score.low,
        high=score.high,
        band=score.band,
        band_note=score.band_note,
        confidence=score.confidence,
        available_weight=score.available_weight,
        components=[
            ScoreComponentRead(
                key=item.key,
                label=item.label,
                weight=item.weight,
                points=item.points,
                value=item.value,
                low=item.low,
                high=item.high,
                sample=item.sample,
                available=item.available,
                confidence=item.confidence,
                detail=item.detail,
            )
            for item in score.components
        ],
        missing_signals=list(score.missing_signals),
        interval_note=score.interval_note,
        empty_reason=score.empty_reason,
    )


def _projection_read(projection: ExamProjection) -> ProjectionRead:
    return ProjectionRead(
        total_questions=projection.total_questions,
        covered_questions=projection.covered_questions,
        coverage=projection.coverage,
        expected=projection.expected,
        expected_low=projection.expected_low,
        expected_high=projection.expected_high,
        expected_percent=projection.expected_percent,
        subjects=[
            SubjectProjectionRead(
                subject_id=item.subject_id,
                name=item.name,
                questions=item.questions,
                weight=item.weight,
                is_eliminatory=item.is_eliminatory,
                accuracy=item.accuracy,
                low=item.low,
                high=item.high,
                expected=item.expected,
                expected_low=item.expected_low,
                expected_high=item.expected_high,
                sample=item.sample,
                included=item.included,
                confidence=item.confidence,
                detail=item.detail,
                risk_note=item.risk_note,
            )
            for item in projection.subjects
        ],
        confidence=projection.confidence,
        is_reliable=projection.is_reliable,
        disclaimer=projection.disclaimer,
        empty_reason=projection.empty_reason,
    )


def _path_read(path: Path) -> PathRead:
    return PathRead(
        steps=[
            PathStepRead(
                subject_id=item.subject_id,
                subject_name=item.subject_name,
                kind=item.kind,
                label=item.label,
                action=item.action,
                evidence=item.evidence,
                questions_at_stake=item.questions_at_stake,
                is_eliminatory=item.is_eliminatory,
                risk_note=item.risk_note,
            )
            for item in path.steps
        ],
        disclaimer=path.disclaimer,
        empty_reason=path.empty_reason,
    )


def _chart_read(chart: Chart) -> ChartRead:
    return ChartRead(
        key=chart.key,
        title=chart.title,
        decision=chart.decision,
        unit=chart.unit,
        points=[
            SeriesPointRead(
                label=item.label,
                value=item.value,
                low=item.low,
                high=item.high,
                sample=item.sample,
                day=item.day,
            )
            for item in chart.points
        ],
        empty_reason=chart.empty_reason,
        note=chart.note,
    )


@router.get("/master-score", response_model=MasterScoreRead, summary="Meu Mestre Score")
async def master_score(user: CurrentUser, db: DbSession) -> MasterScoreRead:
    """Competência medida, de 0 a 1000, com a faixa ao lado. XP não entra."""
    return master_score_read(await AnalyticsService(db).master_score(user))


@router.get(
    "/master-score/history",
    response_model=ScoreHistoryRead,
    summary="Evolução do Mestre Score",
)
async def master_score_history(
    user: CurrentUser,
    db: DbSession,
    days: Annotated[int, Query(ge=7, le=365)] = HISTORY_DAYS,
) -> ScoreHistoryRead:
    """Cada ponto guarda a própria faixa: a evolução não finge precisão."""
    history = await AnalyticsService(db).history(user, days=days)
    return ScoreHistoryRead(
        points=[
            ScorePointRead(
                day=item.day,
                value=item.value,
                low=item.low,
                high=item.high,
                band=item.band,
                confidence=item.confidence,
            )
            for item in history.points
        ],
        delta=history.delta,
        empty_reason=history.empty_reason,
    )


@router.get("/projection", response_model=ProjectionRead, summary="Se a prova fosse hoje")
async def projection(user: CurrentUser, db: DbSession) -> ProjectionRead:
    """Estimativa de acerto sobre o seu histórico — nunca chance de aprovação."""
    return _projection_read(await AnalyticsService(db).projection(user))


@router.get("/path", response_model=PathRead, summary="Caminho da aprovação")
async def path(user: CurrentUser, db: DbSession) -> PathRead:
    """Ações ordenadas por quantas questões da prova elas colocam em jogo."""
    return _path_read(await AnalyticsService(db).path(user))


@router.get("/dashboard", response_model=DashboardRead, summary="Painéis")
async def dashboard(user: CurrentUser, db: DbSession) -> DashboardRead:
    """Todo gráfico carrega a decisão que ele serve — é o aceite da fase."""
    charts = await AnalyticsService(db).dashboard(user)
    return DashboardRead(charts=[_chart_read(item) for item in charts])


@router.get("/overview", response_model=AnalyticsOverviewRead, summary="Tudo em uma requisição")
async def overview(user: CurrentUser, db: DbSession) -> AnalyticsOverviewRead:
    """A tela inteira de Analytics: score, projeção, caminho e painéis."""
    service = AnalyticsService(db)
    score = await service.master_score(user)
    exam = await service.projection(user)
    return AnalyticsOverviewRead(
        master_score=master_score_read(score),
        projection=_projection_read(exam),
        path=_path_read(await service.path(user)),
        charts=[_chart_read(item) for item in await service.dashboard(user)],
    )
