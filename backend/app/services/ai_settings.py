"""Configuração de provedores de IA pelo painel administrativo."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    AIProvider,
    ConnectionCheck,
    ProviderCredentials,
    ProviderError,
    ProviderNotConfiguredError,
)
from app.ai.registry import available_provider_slugs, build_provider
from app.core.crypto import decrypt_secret, encrypt_secret, secret_hint
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.ai import AIFeature, AIFeatureBinding, AIModel, AIProviderConfig
from app.models.audit import AuditAction
from app.models.user import User
from app.repositories.ai import (
    AIFeatureBindingRepository,
    AIModelRepository,
    AIProviderRepository,
)
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "aisa": {
        "display_name": "AISA.one",
        "base_url": "https://api.aisa.one/v1",
    },
    "openai": {
        "display_name": "OpenAI (ChatGPT)",
        "base_url": "https://api.openai.com/v1",
    },
}


@dataclass(frozen=True, slots=True)
class ResolvedModel:
    """Modelo pronto para uso, já com o provedor instanciado."""

    provider: AIProvider
    provider_slug: str
    model_slug: str
    binding: AIFeatureBinding
    model: AIModel


class AISettingsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.providers = AIProviderRepository(session)
        self.models = AIModelRepository(session)
        self.bindings = AIFeatureBindingRepository(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Provedores
    # ------------------------------------------------------------------ #
    async def list_providers(self) -> list[AIProviderConfig]:
        return list(await self.providers.list_all())

    async def get_provider(self, slug: str) -> AIProviderConfig:
        provider = await self.providers.get_by_slug(slug)
        if provider is None:
            raise NotFoundError("Provedor de IA não cadastrado.")
        return provider

    async def create_provider(
        self,
        *,
        slug: str,
        display_name: str | None,
        base_url: str | None,
        organization: str | None,
        actor: User,
        context: RequestContext,
    ) -> AIProviderConfig:
        normalized = slug.strip().lower()
        if normalized not in available_provider_slugs():
            raise ValidationError(
                "Provedor sem adaptador implementado.",
                code="ai_provider_unsupported",
                details={"available": available_provider_slugs()},
            )
        if await self.providers.get_by_slug(normalized) is not None:
            raise ConflictError("Este provedor já está cadastrado.")

        defaults = PROVIDER_DEFAULTS.get(normalized, {})
        provider = AIProviderConfig(
            slug=normalized,
            display_name=display_name or defaults.get("display_name", normalized),
            base_url=base_url or defaults.get("base_url"),
            organization=organization,
            is_active=False,
        )
        self.session.add(provider)
        await self.audit.record(
            AuditAction.AI_PROVIDER_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_provider",
            resource_id=normalized,
        )
        await self.session.commit()
        return await self.get_provider(normalized)

    async def update_provider(
        self,
        slug: str,
        *,
        display_name: str | None = None,
        base_url: str | None = None,
        organization: str | None = None,
        is_active: bool | None = None,
        actor: User,
        context: RequestContext,
    ) -> AIProviderConfig:
        provider = await self.get_provider(slug)
        if is_active and not provider.has_api_key:
            raise ValidationError(
                "Cadastre a chave de API antes de ativar o provedor.",
                code="ai_provider_missing_key",
            )

        if display_name is not None:
            provider.display_name = display_name
        if base_url is not None:
            provider.base_url = base_url or None
        if organization is not None:
            provider.organization = organization or None
        if is_active is not None:
            provider.is_active = is_active

        await self.audit.record(
            AuditAction.AI_PROVIDER_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_provider",
            resource_id=slug,
            meta={"is_active": provider.is_active},
        )
        await self.session.commit()
        return await self.get_provider(slug)

    async def set_api_key(
        self, slug: str, api_key: str, *, actor: User, context: RequestContext
    ) -> AIProviderConfig:
        """Grava a chave cifrada. O valor em claro nunca volta pela API."""
        provider = await self.get_provider(slug)
        cleaned = api_key.strip()
        if len(cleaned) < 20:
            raise ValidationError(
                "A chave informada é curta demais para ser válida.",
                code="ai_invalid_api_key",
            )

        provider.api_key_encrypted = encrypt_secret(cleaned)
        provider.api_key_hint = secret_hint(cleaned)
        provider.api_key_set_at = datetime.now(UTC)
        provider.api_key_set_by_user_id = actor.id
        provider.last_test_status = None
        provider.last_test_message = None

        await self.audit.record(
            AuditAction.AI_PROVIDER_KEY_SET,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_provider",
            resource_id=slug,
            meta={"hint": provider.api_key_hint},
        )
        await self.session.commit()
        return await self.get_provider(slug)

    async def remove_api_key(
        self, slug: str, *, actor: User, context: RequestContext
    ) -> AIProviderConfig:
        provider = await self.get_provider(slug)
        provider.api_key_encrypted = None
        provider.api_key_hint = None
        provider.api_key_set_at = None
        provider.is_active = False
        await self.audit.record(
            AuditAction.AI_PROVIDER_KEY_REMOVED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_provider",
            resource_id=slug,
        )
        await self.session.commit()
        return await self.get_provider(slug)

    def build_client(self, provider: AIProviderConfig) -> AIProvider:
        if not provider.api_key_encrypted:
            raise ProviderNotConfiguredError("Cadastre a chave de API deste provedor.")
        credentials = ProviderCredentials(
            api_key=decrypt_secret(provider.api_key_encrypted),
            base_url=provider.base_url,
            organization=provider.organization,
        )
        return build_provider(provider.slug, credentials)

    async def test_provider(
        self, slug: str, *, actor: User, context: RequestContext
    ) -> ConnectionCheck:
        """Chamada real ao fornecedor — o resultado exibido não é simulado."""
        provider = await self.get_provider(slug)
        client = self.build_client(provider)
        try:
            check = await client.test_connection()
        except ProviderError as exc:
            provider.last_tested_at = datetime.now(UTC)
            provider.last_test_status = "FAILED"
            provider.last_test_message = exc.message[:255]
            await self.audit.record(
                AuditAction.AI_PROVIDER_TESTED,
                actor=actor,
                actor_ip=context.ip_address,
                resource_type="ai_provider",
                resource_id=slug,
                status="FAILURE",
                meta={"error": exc.code},
            )
            await self.session.commit()
            raise

        provider.last_tested_at = datetime.now(UTC)
        provider.last_test_status = "OK"
        provider.last_test_message = (
            f"{check.models_available} modelo(s) disponíveis · {check.latency_ms} ms"
        )
        await self.audit.record(
            AuditAction.AI_PROVIDER_TESTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_provider",
            resource_id=slug,
            meta={"latency_ms": check.latency_ms, "models": check.models_available},
        )
        await self.session.commit()
        return check

    # ------------------------------------------------------------------ #
    # Modelos
    # ------------------------------------------------------------------ #
    async def sync_models(
        self, slug: str, *, actor: User, context: RequestContext
    ) -> list[AIModel]:
        """Importa a lista de modelos que a chave realmente pode usar."""
        provider = await self.get_provider(slug)
        client = self.build_client(provider)
        discovered = await client.list_models()
        now = datetime.now(UTC)

        existing = {model.slug: model for model in provider.models}
        for info in discovered:
            model = existing.get(info.slug)
            if model is None:
                model = AIModel(provider_id=provider.id, slug=info.slug)
                self.session.add(model)
                existing[info.slug] = model
            model.display_name = info.display_name
            model.kind = info.kind
            model.context_window = info.context_window
            model.max_output_tokens = info.max_output_tokens
            # Preço definido manualmente pelo admin não é sobrescrito por padrão.
            if model.input_cost_per_1k is None:
                model.input_cost_per_1k = info.input_cost_per_1k
            if model.output_cost_per_1k is None:
                model.output_cost_per_1k = info.output_cost_per_1k
            model.supports_tools = info.supports_tools
            model.supports_json = info.supports_json
            model.discovered_at = now

        await self.audit.record(
            AuditAction.AI_MODELS_SYNCED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_provider",
            resource_id=slug,
            meta={"models": len(discovered)},
        )
        await self.session.commit()
        return list(await self.models.list_for_provider(provider.id))

    async def update_model(
        self,
        provider_slug: str,
        model_slug: str,
        *,
        is_active: bool | None = None,
        input_cost_per_1k: Decimal | None = None,
        output_cost_per_1k: Decimal | None = None,
    ) -> AIModel:
        provider = await self.get_provider(provider_slug)
        model = await self.models.get_by_slug(provider.id, model_slug)
        if model is None:
            raise NotFoundError("Modelo não encontrado neste provedor.")
        if is_active is not None:
            model.is_active = is_active
        if input_cost_per_1k is not None:
            model.input_cost_per_1k = input_cost_per_1k
        if output_cost_per_1k is not None:
            model.output_cost_per_1k = output_cost_per_1k
        await self.session.commit()
        return model

    # ------------------------------------------------------------------ #
    # Vínculo modelo × funcionalidade
    # ------------------------------------------------------------------ #
    async def list_bindings(self) -> list[dict[str, Any]]:
        """Uma linha por funcionalidade, mesmo as ainda não configuradas."""
        stored = {binding.feature: binding for binding in await self.bindings.list_all()}
        result: list[dict[str, Any]] = []
        for feature in AIFeature:
            binding = stored.get(feature.value)
            result.append(
                {
                    "feature": feature.value,
                    "binding": binding,
                }
            )
        return result

    async def set_binding(
        self,
        feature: str,
        *,
        provider_slug: str | None,
        model_slug: str | None,
        is_enabled: bool,
        temperature: Decimal | None,
        max_output_tokens: int | None,
        cache_ttl_hours: int | None,
        actor: User,
        context: RequestContext,
    ) -> AIFeatureBinding:
        if feature not in {item.value for item in AIFeature}:
            raise ValidationError(
                "Funcionalidade desconhecida.",
                details={"available": [item.value for item in AIFeature]},
            )

        model: AIModel | None = None
        if provider_slug and model_slug:
            provider = await self.get_provider(provider_slug)
            model = await self.models.get_by_slug(provider.id, model_slug)
            if model is None:
                raise NotFoundError("Modelo não encontrado neste provedor.")
            if is_enabled and not provider.is_active:
                raise ValidationError(
                    "Ative o provedor antes de habilitar a funcionalidade.",
                    code="ai_provider_inactive",
                )
        elif is_enabled:
            raise ValidationError(
                "Escolha um modelo antes de habilitar a funcionalidade.",
                code="ai_model_required",
            )

        binding = await self.bindings.get_by_feature(feature)
        if binding is None:
            binding = AIFeatureBinding(feature=feature)
            self.session.add(binding)

        binding.model_id = model.id if model else None
        binding.is_enabled = is_enabled
        if temperature is not None:
            binding.temperature = temperature
        binding.max_output_tokens = max_output_tokens
        binding.cache_ttl_hours = cache_ttl_hours

        await self.audit.record(
            AuditAction.AI_BINDING_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="ai_feature",
            resource_id=feature,
            meta={"model": model.slug if model else None, "enabled": is_enabled},
        )
        await self.session.commit()
        resolved = await self.bindings.get_by_feature(feature)
        assert resolved is not None
        return resolved

    async def resolve_feature(self, feature: str) -> ResolvedModel:
        """Provedor + modelo ativos para a funcionalidade, prontos para uso.

        Levanta ``ProviderNotConfiguredError`` quando nada foi configurado — a plataforma
        prefere avisar a fingir que respondeu.
        """
        binding = await self.bindings.get_by_feature(feature)
        if binding is None or not binding.is_enabled or binding.model is None:
            raise ProviderNotConfiguredError(
                f"A funcionalidade '{feature}' ainda não tem modelo configurado."
            )

        model = binding.model
        provider_config = model.provider
        if not provider_config.is_active:
            raise ProviderNotConfiguredError("O provedor desta funcionalidade está inativo.")

        return ResolvedModel(
            provider=self.build_client(provider_config),
            provider_slug=provider_config.slug,
            model_slug=model.slug,
            binding=binding,
            model=model,
        )
