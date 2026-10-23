"""Configuração de provedores de IA — painel administrativo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.ai.registry import available_provider_slugs
from app.api.deps import DbSession, RequestCtx, require_permissions
from app.domain import permissions as perms
from app.domain.ai_features import FEATURE_BY_SLUG, is_routable
from app.domain.model_routing import SignalKey
from app.models.ai import AIFeatureBinding, AIModelRoute, AIRoutingDecision
from app.models.audit import AuditAction
from app.models.user import User
from app.schemas.ai import (
    AIAvailableProviders,
    AIBudgetRead,
    AIBudgetUpdate,
    AICacheStatsRead,
    AIFeatureBindingRead,
    AIFeatureBindingUpdate,
    AIModelRead,
    AIModelRouteCreate,
    AIModelRouteRead,
    AIModelRouteUpdate,
    AIModelUpdate,
    AIProviderCreate,
    AIProviderKeyInput,
    AIProviderRead,
    AIProviderUpdate,
    AIRoutingDecisionRead,
    ConnectionCheckRead,
)
from app.schemas.common import MessageResponse
from app.services.ai_budget import AIBudgetService
from app.services.ai_cache import AICacheService
from app.services.ai_settings import AISettingsService
from app.services.audit import AuditService
from app.services.model_router import ModelRouterService, model_is_usable

router = APIRouter(prefix="/admin/ai", tags=["admin · ia"])

AiReader = Annotated[User, Depends(require_permissions(perms.AI_SETTINGS_READ))]
AiWriter = Annotated[User, Depends(require_permissions(perms.AI_SETTINGS_WRITE))]


def _binding_read(feature: str, binding: AIFeatureBinding | None) -> AIFeatureBindingRead:
    spec = FEATURE_BY_SLUG[feature]
    model = binding.model if binding else None
    reserva = binding.fallback_model if binding else None
    return AIFeatureBindingRead(
        feature=feature,
        label=spec.label,
        description=spec.description,
        kind=spec.kind,
        is_routable=is_routable(feature),
        is_enabled=bool(binding and binding.is_enabled),
        provider_slug=model.provider.slug if model else None,
        model_slug=model.slug if model else None,
        fallback_provider_slug=(reserva.provider.slug if reserva and reserva.provider else None),
        fallback_model_slug=reserva.slug if reserva else None,
        fallback_is_usable=model_is_usable(reserva),
        temperature=binding.temperature if binding else None,
        max_output_tokens=binding.max_output_tokens if binding else None,
        cache_ttl_hours=binding.cache_ttl_hours if binding else None,
        min_support=(
            float((binding.options or {}).get("min_support", 0) or 0)
            if binding is not None
            else None
        ),
    )


@router.get("/providers", response_model=list[AIProviderRead], summary="Provedores configurados")
async def list_providers(_: AiReader, db: DbSession) -> list[AIProviderRead]:
    providers = await AISettingsService(db).list_providers()
    return [AIProviderRead.model_validate(provider) for provider in providers]


@router.get(
    "/providers/available",
    response_model=AIAvailableProviders,
    summary="Adaptadores disponíveis para cadastro",
)
async def list_available(_: AiReader, db: DbSession) -> AIAvailableProviders:
    configured = [provider.slug for provider in await AISettingsService(db).list_providers()]
    return AIAvailableProviders(available=available_provider_slugs(), configured=configured)


@router.post(
    "/providers",
    status_code=status.HTTP_201_CREATED,
    response_model=AIProviderRead,
    summary="Cadastrar provedor",
)
async def create_provider(
    payload: AIProviderCreate, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> AIProviderRead:
    provider = await AISettingsService(db).create_provider(
        slug=payload.slug,
        display_name=payload.display_name,
        base_url=payload.base_url,
        organization=payload.organization,
        actor=actor,
        context=ctx,
    )
    return AIProviderRead.model_validate(provider)


@router.patch("/providers/{slug}", response_model=AIProviderRead, summary="Atualizar provedor")
async def update_provider(
    slug: str, payload: AIProviderUpdate, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> AIProviderRead:
    provider = await AISettingsService(db).update_provider(
        slug,
        display_name=payload.display_name,
        base_url=payload.base_url,
        organization=payload.organization,
        is_active=payload.is_active,
        actor=actor,
        context=ctx,
    )
    return AIProviderRead.model_validate(provider)


@router.put(
    "/providers/{slug}/key",
    response_model=AIProviderRead,
    summary="Cadastrar ou substituir a chave de API",
)
async def set_api_key(
    slug: str, payload: AIProviderKeyInput, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> AIProviderRead:
    provider = await AISettingsService(db).set_api_key(
        slug, payload.api_key, actor=actor, context=ctx
    )
    return AIProviderRead.model_validate(provider)


@router.delete(
    "/providers/{slug}/key", response_model=AIProviderRead, summary="Remover a chave de API"
)
async def remove_api_key(
    slug: str, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> AIProviderRead:
    provider = await AISettingsService(db).remove_api_key(slug, actor=actor, context=ctx)
    return AIProviderRead.model_validate(provider)


@router.post(
    "/providers/{slug}/test",
    response_model=ConnectionCheckRead,
    summary="Testar a conexão com o provedor",
)
async def test_provider(
    slug: str, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> ConnectionCheckRead:
    check = await AISettingsService(db).test_provider(slug, actor=actor, context=ctx)
    return ConnectionCheckRead(
        ok=check.ok,
        message=check.message,
        latency_ms=check.latency_ms,
        models_available=check.models_available,
        sample_models=check.sample_models,
    )


@router.post(
    "/providers/{slug}/models/sync",
    response_model=list[AIModelRead],
    summary="Importar os modelos disponíveis para a chave",
)
async def sync_models(
    slug: str, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> list[AIModelRead]:
    models = await AISettingsService(db).sync_models(slug, actor=actor, context=ctx)
    return [AIModelRead.model_validate(model) for model in models]


@router.patch(
    "/providers/{slug}/models/{model_slug:path}",
    response_model=AIModelRead,
    summary="Ajustar preço ou disponibilidade de um modelo",
)
async def update_model(
    slug: str, model_slug: str, payload: AIModelUpdate, _: AiWriter, db: DbSession
) -> AIModelRead:
    model = await AISettingsService(db).update_model(
        slug,
        model_slug,
        is_active=payload.is_active,
        input_cost_per_1k=payload.input_cost_per_1k,
        output_cost_per_1k=payload.output_cost_per_1k,
    )
    return AIModelRead.model_validate(model)


@router.get(
    "/features",
    response_model=list[AIFeatureBindingRead],
    summary="Modelo usado por cada funcionalidade",
)
async def list_features(_: AiReader, db: DbSession) -> list[AIFeatureBindingRead]:
    rows = await AISettingsService(db).list_bindings()
    return [_binding_read(row["feature"], row["binding"]) for row in rows]


@router.put(
    "/features/{feature:path}",
    response_model=AIFeatureBindingRead,
    summary="Definir o modelo de uma funcionalidade",
)
async def set_feature(
    feature: str,
    payload: AIFeatureBindingUpdate,
    actor: AiWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> AIFeatureBindingRead:
    binding = await AISettingsService(db).set_binding(
        feature,
        provider_slug=payload.provider_slug,
        model_slug=payload.model_slug,
        fallback_provider_slug=payload.fallback_provider_slug,
        fallback_model_slug=payload.fallback_model_slug,
        is_enabled=payload.is_enabled,
        temperature=payload.temperature,
        max_output_tokens=payload.max_output_tokens,
        cache_ttl_hours=payload.cache_ttl_hours,
        min_support=payload.min_support,
        actor=actor,
        context=ctx,
    )
    return _binding_read(feature, binding)


@router.get("/cache", response_model=AICacheStatsRead, summary="Economia gerada pelo cache de IA")
async def cache_stats(_: AiReader, db: DbSession) -> AICacheStatsRead:
    stats = await AICacheService(db).stats()
    return AICacheStatsRead(
        entries=stats.entries,
        total_hits=stats.total_hits,
        tokens_stored=stats.tokens_stored,
        tokens_saved=stats.tokens_saved,
        cost_saved_cents=stats.cost_saved_cents,
        expired_entries=stats.expired_entries,
    )


@router.delete("/cache", response_model=MessageResponse, summary="Limpar o cache de IA")
async def purge_cache(
    actor: AiWriter,
    db: DbSession,
    ctx: RequestCtx,
    feature: Annotated[str | None, Query(max_length=60)] = None,
    expired_only: Annotated[bool, Query()] = False,
) -> MessageResponse:
    removed = await AICacheService(db).purge(feature=feature, expired_only=expired_only)
    await AuditService(db).record(
        AuditAction.AI_CACHE_PURGED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="ai_cache",
        resource_id=feature or "all",
        meta={"removed": removed, "expired_only": expired_only},
    )
    await db.commit()
    return MessageResponse(
        message=f"{removed} entrada(s) removida(s) do cache.", detail={"removed": removed}
    )


# --------------------------------------------------------------------------- #
# Teto de gasto
#
# Os limites vivem no banco e são editáveis aqui — nunca no código. Com o
# controle desligado a medição continua, que é o que permite descobrir qual
# teto faz sentido antes de ligá-lo.
# --------------------------------------------------------------------------- #
def _budget(overview: object) -> AIBudgetRead:
    from app.services.ai_budget import BudgetOverview

    assert isinstance(overview, BudgetOverview)
    return AIBudgetRead(
        is_enabled=overview.limits.is_enabled,
        monthly_limit_cents=overview.limits.monthly_cents,
        per_run_limit_cents=overview.limits.per_run_cents,
        spent_month_cents=overview.spent_month_cents,
        calls_month=overview.calls_month,
        is_complete=overview.is_complete,
        models_without_price=overview.models_without_price,
    )


@router.get("/budget", response_model=AIBudgetRead, summary="Teto de gasto e consumo do mês")
async def get_budget(_: AiReader, db: DbSession) -> AIBudgetRead:
    return _budget(await AIBudgetService(db).overview())


@router.put("/budget", response_model=AIBudgetRead, summary="Definir o teto de gasto")
async def set_budget(
    payload: AIBudgetUpdate, actor: AiWriter, db: DbSession, ctx: RequestCtx
) -> AIBudgetRead:
    service = AIBudgetService(db)
    await service.set_limits(
        actor,
        ctx,
        is_enabled=payload.is_enabled,
        monthly_limit_cents=payload.monthly_limit_cents,
        per_run_limit_cents=payload.per_run_limit_cents,
    )
    return _budget(await service.overview())


# --------------------------------------------------------------------------- #
# Roteador de modelos (Fase 6)
# --------------------------------------------------------------------------- #
def _route_read(row: AIModelRoute) -> AIModelRouteRead:
    exigidos: list[str] = []
    if row.min_input_chars is not None or row.max_input_chars is not None:
        exigidos.append(SignalKey.INPUT_CHARS.value)
    if row.requires_json is not None:
        exigidos.append(SignalKey.NEEDS_JSON.value)
    if row.min_budget_used_pct is not None:
        exigidos.append(SignalKey.BUDGET_USED_PCT.value)
    spec = FEATURE_BY_SLUG.get(row.feature)
    return AIModelRouteRead(
        id=row.id,
        feature=row.feature,
        feature_label=spec.label if spec else row.feature,
        label=row.label,
        priority=row.priority,
        is_enabled=bool(row.is_enabled),
        provider_slug=row.model.provider.slug if row.model and row.model.provider else None,
        model_slug=row.model.slug if row.model else None,
        model_is_usable=model_is_usable(row.model),
        min_input_chars=row.min_input_chars,
        max_input_chars=row.max_input_chars,
        requires_json=row.requires_json,
        min_budget_used_pct=row.min_budget_used_pct,
        required_signals=exigidos,
    )


def _decision_read(row: AIRoutingDecision) -> AIRoutingDecisionRead:
    spec = FEATURE_BY_SLUG.get(row.feature)
    return AIRoutingDecisionRead(
        id=row.id,
        feature=row.feature,
        feature_label=spec.label if spec else row.feature,
        model_slug=row.model_slug,
        provider_slug=row.provider_slug,
        reason=row.reason,
        route_id=row.route_id,
        route_label=row.route_label,
        explanation=row.explanation,
        signals=row.signals or {},
        trace=row.trace or [],
        created_at=row.created_at,
    )


@router.get(
    "/routes",
    response_model=list[AIModelRouteRead],
    summary="Regras do roteador de modelos",
)
async def list_routes(
    _: AiReader,
    db: DbSession,
    feature: Annotated[str | None, Query(description="Filtra por funcionalidade")] = None,
) -> list[AIModelRouteRead]:
    rows = await ModelRouterService(db).list_rules(feature=feature)
    return [_route_read(row) for row in rows]


@router.post(
    "/routes",
    status_code=status.HTTP_201_CREATED,
    response_model=AIModelRouteRead,
    summary="Cadastrar regra de roteamento",
)
async def create_route(
    payload: AIModelRouteCreate,
    actor: AiWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> AIModelRouteRead:
    row = await ModelRouterService(db).create_rule(
        feature=payload.feature,
        label=payload.label,
        priority=payload.priority,
        is_enabled=payload.is_enabled,
        provider_slug=payload.provider_slug,
        model_slug=payload.model_slug,
        min_input_chars=payload.min_input_chars,
        max_input_chars=payload.max_input_chars,
        requires_json=payload.requires_json,
        min_budget_used_pct=payload.min_budget_used_pct,
        actor=actor,
        context=ctx,
    )
    return _route_read(row)


@router.patch(
    "/routes/{route_id}",
    response_model=AIModelRouteRead,
    summary="Atualizar regra de roteamento",
)
async def update_route(
    route_id: int,
    payload: AIModelRouteUpdate,
    actor: AiWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> AIModelRouteRead:
    row = await ModelRouterService(db).update_rule(
        route_id,
        label=payload.label,
        priority=payload.priority,
        is_enabled=payload.is_enabled,
        provider_slug=payload.provider_slug,
        model_slug=payload.model_slug,
        min_input_chars=payload.min_input_chars,
        max_input_chars=payload.max_input_chars,
        requires_json=payload.requires_json,
        min_budget_used_pct=payload.min_budget_used_pct,
        clear_conditions=payload.clear_conditions,
        actor=actor,
        context=ctx,
    )
    return _route_read(row)


@router.delete(
    "/routes/{route_id}",
    response_model=MessageResponse,
    summary="Remover regra de roteamento",
)
async def delete_route(
    route_id: int,
    actor: AiWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> MessageResponse:
    await ModelRouterService(db).delete_rule(route_id, actor=actor, context=ctx)
    return MessageResponse(message="Regra removida.")


@router.get(
    "/routes/decisions",
    response_model=list[AIRoutingDecisionRead],
    summary="Histórico: por que cada modelo foi usado",
)
async def list_decisions(
    _: AiReader,
    db: DbSession,
    feature: Annotated[str | None, Query(description="Filtra por funcionalidade")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIRoutingDecisionRead]:
    rows = await ModelRouterService(db).history(feature=feature, limit=limit)
    return [_decision_read(row) for row in rows]
