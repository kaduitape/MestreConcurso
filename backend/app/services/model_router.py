"""Roteador de modelos: aplica as regras, registra a decisão, guarda o rastro.

O domínio (``app/domain/model_routing.py``) decide; aqui acontece o que o
domínio não pode fazer: ler as regras do banco, descobrir se o modelo de cada
regra está realmente utilizável, medir a pressão do orçamento e **gravar a
decisão**.

A gravação é o ponto do roteador. Um roteador que escolhe bem e não registra
nada troca um comportamento previsível (um modelo por funcionalidade) por um
comportamento que ninguém consegue explicar depois — e o critério de aceite
desta fase é exatamente poder dizer por que aquele modelo foi usado naquela
execução.

Como em ``record_usage``, a decisão é gravada em **sessão própria**: ela
precisa sobreviver ao erro de quem chamou. Se a funcionalidade falhar depois e
desfizer a transação dela, a chamada de IA já aconteceu e o motivo dela
continua valendo.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain import model_routing as routing
from app.domain.ai_features import FEATURE_BY_SLUG
from app.models.ai import AIFeature, AIFeatureBinding, AIModel, AIModelRoute, AIRoutingDecision
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.ai import (
    AIModelRepository,
    AIModelRouteRepository,
    AIProviderRepository,
    AIRoutingDecisionRepository,
)
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RouteOutcome:
    """O que o roteador devolve para quem vai chamar o provedor."""

    decision: routing.Decision
    model: AIModel
    #: Identificador da decisão gravada. ``None`` quando a gravação falhou — o
    #: gasto é registrado de qualquer forma, só sem o vínculo com a explicação.
    decision_id: int | None


def model_is_usable(model: AIModel | None) -> bool:
    """Modelo ativo, de provedor ativo e com chave cadastrada."""
    if model is None or not model.is_active:
        return False
    provider = model.provider
    return bool(provider and provider.is_active and provider.has_api_key)


def to_rule(row: AIModelRoute) -> routing.Rule:
    return routing.Rule(
        id=row.id,
        label=row.label,
        priority=row.priority,
        is_enabled=bool(row.is_enabled),
        model_id=row.model_id,
        model_slug=row.model.slug if row.model else None,
        provider_slug=row.model.provider.slug if row.model and row.model.provider else None,
        model_is_usable=model_is_usable(row.model),
        min_input_chars=row.min_input_chars,
        max_input_chars=row.max_input_chars,
        requires_json=row.requires_json,
        min_budget_used_pct=(
            Decimal(row.min_budget_used_pct) if row.min_budget_used_pct is not None else None
        ),
    )


def trace_as_json(decision: routing.Decision) -> list[dict[str, object]]:
    """O rastro em forma serializável, uma entrada por regra avaliada."""
    return [
        {
            "rule_id": item.rule_id,
            "label": item.label,
            "priority": item.priority,
            "outcome": item.outcome.value,
            "detail": item.detail,
            "missing_signals": [signal.value for signal in item.missing_signals],
            "conditions": [
                {
                    "signal": condition.signal.value,
                    "description": condition.description,
                    "outcome": condition.outcome.value,
                    "observed": condition.observed,
                }
                for condition in item.conditions
            ],
        }
        for item in decision.trace
    ]


class ModelRouterService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.routes = AIModelRouteRepository(session)
        self.decisions = AIRoutingDecisionRepository(session)
        self.models = AIModelRepository(session)
        self.providers = AIProviderRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Decisão
    # ------------------------------------------------------------------ #
    async def signals(self, declared: routing.Signals | None) -> routing.Signals:
        """Completa o que a chamada declarou com o que só o servidor sabe.

        A pressão de orçamento não é algo que o chamador saiba: depende do teto
        cadastrado e do gasto do mês. Sem teto, o sinal fica ausente em vez de
        virar zero.
        """
        base = declared or routing.Signals()
        from app.services.ai_budget import AIBudgetService

        gasto, teto = await AIBudgetService(self.session).month_spend_and_limit()
        pct = routing.budget_used_pct(gasto, teto)
        return routing.Signals(
            input_chars=base.input_chars,
            needs_json=base.needs_json,
            budget_used_pct=pct,
        )

    async def decide(
        self,
        feature: str,
        *,
        binding: AIFeatureBinding,
        declared: routing.Signals | None = None,
    ) -> RouteOutcome:
        """Escolhe o modelo da chamada e grava a decisão."""
        padrao = binding.model
        if padrao is None:  # pragma: no cover - resolve_feature já barrou antes
            raise NotFoundError("A funcionalidade não tem modelo vinculado.")

        linhas = list(await self.routes.list_for_feature(feature))
        regras = [to_rule(linha) for linha in linhas]
        sinais = await self.signals(declared)

        decisao = routing.choose(
            regras,
            sinais,
            default_model_id=padrao.id,
            default_model_slug=padrao.slug,
            default_provider_slug=padrao.provider.slug if padrao.provider else None,
        )

        escolhido = padrao
        if decisao.model_id is not None and decisao.model_id != padrao.id:
            por_id = {linha.model_id: linha.model for linha in linhas if linha.model is not None}
            alvo = por_id.get(decisao.model_id)
            if alvo is None:  # pragma: no cover - invariante de ``evaluate``
                # Não deveria acontecer: uma regra só vence com o modelo dela
                # carregado e utilizável. Se acontecer, o vínculo atende — e a
                # explicação diz exatamente isso, em vez de registrar uma
                # escolha que não foi feita ou de alegar que não havia regra.
                decisao = replace(
                    decisao,
                    model_id=padrao.id,
                    model_slug=padrao.slug,
                    provider_slug=padrao.provider.slug if padrao.provider else None,
                    reason=routing.RouteReason.BINDING_DEFAULT,
                    explanation=(
                        f'a regra "{decisao.rule_label}" venceu, mas o modelo dela não '
                        "estava disponível na hora do uso; valeu o modelo vinculado à "
                        "funcionalidade"
                    ),
                    rule_id=None,
                    rule_label=None,
                )
            else:
                escolhido = alvo

        decision_id = await self.record(feature, decisao)
        return RouteOutcome(decision=decisao, model=escolhido, decision_id=decision_id)

    async def record(self, feature: str, decision: routing.Decision) -> int | None:
        """Grava a decisão em sessão própria e devolve o identificador."""
        factory = get_session_factory()
        try:
            async with factory() as session:
                linha = AIRoutingDecision(
                    feature=feature,
                    model_id=decision.model_id,
                    model_slug=decision.model_slug or "",
                    provider_slug=decision.provider_slug or "",
                    reason=decision.reason.value,
                    route_id=decision.rule_id,
                    route_label=decision.rule_label,
                    explanation=decision.explanation[:500],
                    signals=decision.signals.as_dict(),
                    trace=trace_as_json(decision),
                )
                session.add(linha)
                await session.commit()
                return linha.id
        except Exception as exc:  # pragma: no cover - rastro não derruba a feature
            # Mesmo critério de ``record_usage``: a contabilidade não pode
            # impedir a funcionalidade de responder. O log é o que denuncia.
            logger.warning("ai.routing.record_failed", feature=feature, error=str(exc))
            return None

    async def history(
        self, *, feature: str | None = None, limit: int = 50
    ) -> list[AIRoutingDecision]:
        return list(await self.decisions.recent(feature=feature, limit=limit))

    # ------------------------------------------------------------------ #
    # Cadastro das regras
    # ------------------------------------------------------------------ #
    async def list_rules(self, *, feature: str | None = None) -> list[AIModelRoute]:
        if feature:
            return list(await self.routes.list_for_feature(feature))
        return list(await self.routes.list_all())

    async def create_rule(
        self,
        *,
        feature: str,
        label: str,
        priority: int,
        is_enabled: bool,
        provider_slug: str,
        model_slug: str,
        min_input_chars: int | None,
        max_input_chars: int | None,
        requires_json: bool | None,
        min_budget_used_pct: Decimal | None,
        actor: User,
        context: RequestContext,
    ) -> AIModelRoute:
        self._check_feature(feature)
        if await self.routes.count_for_feature(feature) >= routing.MAX_RULES_PER_FEATURE:
            raise ValidationError(
                f"Esta funcionalidade já tem {routing.MAX_RULES_PER_FEATURE} regras. "
                "Remova uma antes de cadastrar outra.",
                code="ai_route_limit_reached",
            )
        modelo = await self._model(provider_slug, model_slug)
        self._check_conditions(min_input_chars, max_input_chars)

        linha = AIModelRoute(
            feature=feature,
            label=label.strip(),
            priority=priority,
            is_enabled=is_enabled,
            model_id=modelo.id,
            min_input_chars=min_input_chars,
            max_input_chars=max_input_chars,
            requires_json=requires_json,
            min_budget_used_pct=min_budget_used_pct,
        )
        self.session.add(linha)
        await self.session.flush()
        await self.audit.record(
            AuditAction.AI_ROUTE_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_model_route",
            resource_id=str(linha.id),
            meta={"feature": feature, "label": linha.label, "model": modelo.slug},
        )
        await self.session.commit()
        encontrada = await self.routes.get_with_model(linha.id)
        assert encontrada is not None
        return encontrada

    async def update_rule(
        self,
        route_id: int,
        *,
        label: str | None,
        priority: int | None,
        is_enabled: bool | None,
        provider_slug: str | None,
        model_slug: str | None,
        min_input_chars: int | None,
        max_input_chars: int | None,
        requires_json: bool | None,
        min_budget_used_pct: Decimal | None,
        clear_conditions: bool,
        actor: User,
        context: RequestContext,
    ) -> AIModelRoute:
        linha = await self.routes.get_with_model(route_id)
        if linha is None:
            raise NotFoundError("Regra de roteamento não encontrada.")

        if label is not None:
            linha.label = label.strip()
        if priority is not None:
            linha.priority = priority
        if is_enabled is not None:
            linha.is_enabled = is_enabled
        if provider_slug and model_slug:
            modelo = await self._model(provider_slug, model_slug)
            linha.model_id = modelo.id

        # Apagar condição é uma intenção explícita: sem isso, ``None`` no corpo
        # da requisição seria indistinguível de "não quis mexer nesta".
        if clear_conditions:
            linha.min_input_chars = None
            linha.max_input_chars = None
            linha.requires_json = None
            linha.min_budget_used_pct = None
        if min_input_chars is not None:
            linha.min_input_chars = min_input_chars
        if max_input_chars is not None:
            linha.max_input_chars = max_input_chars
        if requires_json is not None:
            linha.requires_json = requires_json
        if min_budget_used_pct is not None:
            linha.min_budget_used_pct = min_budget_used_pct
        self._check_conditions(linha.min_input_chars, linha.max_input_chars)

        await self.audit.record(
            AuditAction.AI_ROUTE_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_model_route",
            resource_id=str(linha.id),
            meta={"feature": linha.feature, "label": linha.label},
        )
        await self.session.commit()
        encontrada = await self.routes.get_with_model(route_id)
        assert encontrada is not None
        return encontrada

    async def delete_rule(self, route_id: int, *, actor: User, context: RequestContext) -> None:
        linha = await self.routes.get_with_model(route_id)
        if linha is None:
            raise NotFoundError("Regra de roteamento não encontrada.")
        feature, label = linha.feature, linha.label
        await self.session.delete(linha)
        await self.audit.record(
            AuditAction.AI_ROUTE_DELETED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_model_route",
            resource_id=str(route_id),
            meta={"feature": feature, "label": label},
        )
        await self.session.commit()

    # ------------------------------------------------------------------ #
    # Apoio
    # ------------------------------------------------------------------ #
    def _check_feature(self, feature: str) -> None:
        spec = FEATURE_BY_SLUG.get(feature)
        if spec is None:
            raise ValidationError(
                "Funcionalidade desconhecida.",
                details={"available": [item.value for item in AIFeature]},
            )
        if spec.kind == "embedding":
            # Vetor gerado por outro modelo vive em outro espaço. A busca
            # compararia os dois como se fossem comparáveis e devolveria
            # trechos errados com a mesma cara de certos. Rotear embedding
            # seria quebrar a busca semântica em troca de economia.
            raise ValidationError(
                "Embeddings não aceitam regra de roteamento: trocar o modelo faria os "
                "vetores novos viverem em outro espaço do que os já indexados, e a "
                "busca compararia os dois como se fossem comparáveis.",
                code="ai_route_feature_not_routable",
            )
        if spec.kind == "speech":
            # A narração de uma aula é gerada cena por cena. Modelo diferente
            # entre cenas trocaria a voz do narrador no meio da aula.
            raise ValidationError(
                "A narração não aceita regra de roteamento: o áudio é gerado cena por "
                "cena, e um modelo diferente entre cenas trocaria a voz do narrador no "
                "meio da aula.",
                code="ai_route_feature_not_routable",
            )

    @staticmethod
    def _check_conditions(minimo: int | None, maximo: int | None) -> None:
        if minimo is not None and maximo is not None and minimo > maximo:
            raise ValidationError(
                "O tamanho mínimo da entrada ficou acima do máximo: nenhuma chamada "
                "atenderia esta regra.",
                code="ai_route_impossible_condition",
            )

    async def _model(self, provider_slug: str, model_slug: str) -> AIModel:
        provider = await self.providers.get_by_slug(provider_slug)
        if provider is None:
            raise NotFoundError("Provedor não encontrado.")
        modelo = await self.models.get_by_slug(provider.id, model_slug)
        if modelo is None:
            raise NotFoundError("Modelo não encontrado neste provedor.")
        if modelo.kind == "embedding":
            # A regra vale para funcionalidades de texto; apontar para um modelo
            # de embedding criaria uma regra que só falha na hora da chamada.
            raise ValidationError(
                "Modelo de embedding não atende uma funcionalidade de texto: a regra "
                "existiria para falhar na hora da chamada.",
                code="ai_route_model_kind_mismatch",
            )
        return modelo
