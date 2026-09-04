"""Pagamentos: checkout e webhook idempotente.

Duas regras de segurança governam este arquivo:

**O corpo do webhook não é a verdade.** Ele traz um identificador; o status vem
de uma consulta à API do adquirente, com a credencial da conta. Aceitar o status
do corpo permitiria a qualquer um que descubra a URL declarar um pagamento
aprovado.

**Reenvio não credita duas vezes.** Cada notificação vira uma linha única por
(provedor, id do evento). Todo adquirente reenvia — a idempotência não é um
extra, é o que impede estender uma assinatura em dobro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import decrypt_secret, encrypt_secret, secret_hint
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.billing import PaymentProviderConfig, PaymentStatus, WebhookEvent
from app.models.user import User
from app.payments.base import (
    CheckoutRequest,
    PaymentNotConfiguredError,
    PaymentProvider,
    PaymentSnapshot,
)
from app.payments.mercadopago import MercadoPagoProvider, verify_signature
from app.repositories.billing import (
    PaymentConfigRepository,
    PaymentRepository,
    WebhookRepository,
)
from app.services.billing import BillingService

logger = get_logger(__name__)

PROVIDER_SLUG = "mercadopago"


@dataclass(frozen=True, slots=True)
class WebhookResult:
    accepted: bool
    #: Verdadeiro quando o evento já havia sido processado antes.
    duplicate: bool
    detail: str
    payment_reference: str | None = None


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.configs = PaymentConfigRepository(session)
        self.payments = PaymentRepository(session)
        self.webhooks = WebhookRepository(session)
        self.billing = BillingService(session)

    # ------------------------------------------------------------------ #
    # Configuração
    # ------------------------------------------------------------------ #
    async def config(self) -> PaymentProviderConfig | None:
        return await self.configs.get_by_slug(PROVIDER_SLUG)

    async def save_credentials(
        self,
        actor: User,
        *,
        access_token: str | None = None,
        webhook_secret: str | None = None,
        is_active: bool | None = None,
        is_sandbox: bool | None = None,
    ) -> PaymentProviderConfig:
        """Guarda as credenciais cifradas. Elas nunca voltam pela API."""
        stored = await self.config()
        if stored is None:
            stored = PaymentProviderConfig(slug=PROVIDER_SLUG)
            self.session.add(stored)

        if access_token:
            stored.access_token_encrypted = encrypt_secret(access_token)
            stored.access_token_hint = secret_hint(access_token)
            stored.credentials_set_at = datetime.now(UTC)
            stored.credentials_set_by_user_id = actor.id
        if webhook_secret:
            stored.webhook_secret_encrypted = encrypt_secret(webhook_secret)
            stored.webhook_secret_hint = secret_hint(webhook_secret)
        if is_active is not None:
            stored.is_active = is_active
        if is_sandbox is not None:
            stored.is_sandbox = is_sandbox

        await self.session.commit()
        logger.info("payment.credentials_saved", actor=actor.public_id)
        return stored

    async def build_provider(self) -> PaymentProvider:
        """Monta o provedor a partir da configuração — ou recusa com o motivo."""
        stored = await self.config()
        if stored is None or not stored.is_active or not stored.access_token_encrypted:
            raise PaymentNotConfiguredError()
        return MercadoPagoProvider(decrypt_secret(stored.access_token_encrypted))

    async def _webhook_secret(self) -> str:
        stored = await self.config()
        if stored is None or not stored.webhook_secret_encrypted:
            return ""
        return decrypt_secret(stored.webhook_secret_encrypted)

    # ------------------------------------------------------------------ #
    # Checkout
    # ------------------------------------------------------------------ #
    async def start_checkout(
        self, user: User, reference: str, *, success_url: str, failure_url: str
    ) -> str:
        """Cria a cobrança no adquirente e devolve o endereço de pagamento."""
        payment = await self.payments.get_by_reference(reference)
        if payment is None or payment.user_id != user.id:
            raise NotFoundError("Cobrança não encontrada.")

        provider = await self.build_provider()
        session = await provider.create_checkout(
            CheckoutRequest(
                reference=payment.reference,
                title="Assinatura Game of Concursos",
                amount_cents=payment.amount_cents,
                payer_email=user.email,
                success_url=success_url,
                failure_url=failure_url,
                metadata={"reference": payment.reference},
            )
        )
        payment.provider_reference = session.provider_reference
        payment.checkout_url = session.checkout_url
        payment.raw = session.raw
        await self.session.commit()
        return session.checkout_url

    # ------------------------------------------------------------------ #
    # Webhook
    # ------------------------------------------------------------------ #
    async def handle_webhook(
        self,
        payload: dict[str, Any],
        *,
        signature: str | None,
        request_id: str | None,
    ) -> WebhookResult:
        """Processa uma notificação. Verifica assinatura, deduplica e consulta."""
        data = payload.get("data") or {}
        data_id = str(data.get("id") or payload.get("id") or "")
        topic = str(payload.get("type") or payload.get("topic") or "")

        secret = await self._webhook_secret()
        valid, reason = verify_signature(
            signature_header=signature,
            request_id=request_id,
            data_id=data_id,
            secret=secret,
        )
        if not valid:
            # Notificação não confiável não vira linha nem processamento.
            logger.warning("payment.webhook_rejected", reason=reason, topic=topic)
            return WebhookResult(accepted=False, duplicate=False, detail=reason)

        event_id = f"{topic}:{data_id}" if topic else data_id
        event = WebhookEvent(
            provider=PROVIDER_SLUG,
            event_id=event_id,
            topic=topic,
            received_at=datetime.now(UTC),
            payload=payload,
        )
        self.session.add(event)
        try:
            await self.session.flush()
        except IntegrityError:
            # Já recebido: a chave única é o que garante a idempotência.
            await self.session.rollback()
            logger.info("payment.webhook_duplicate", webhook_event=event_id)
            return WebhookResult(
                accepted=True,
                duplicate=True,
                detail="Evento já processado anteriormente.",
            )

        if not topic.startswith("payment"):
            event.status = "IGNORED"
            event.processed_at = datetime.now(UTC)
            event.detail = f"Tópico não tratado: {topic or 'desconhecido'}."
            await self.session.commit()
            return WebhookResult(accepted=True, duplicate=False, detail=event.detail)

        provider = await self.build_provider()
        snapshot: PaymentSnapshot = await provider.fetch_payment(data_id)

        payment = None
        if snapshot.reference:
            payment = await self.payments.get_by_reference(snapshot.reference)
        if payment is None:
            payment = await self.payments.get_by_provider_reference(snapshot.provider_reference)

        if payment is None:
            event.status = "ORPHAN"
            event.processed_at = datetime.now(UTC)
            event.detail = "Pagamento não encontrado para esta notificação."
            await self.session.commit()
            return WebhookResult(accepted=True, duplicate=False, detail=event.detail)

        payment.provider_reference = snapshot.provider_reference
        payment.raw = snapshot.raw

        if snapshot.status == PaymentStatus.APPROVED:
            await self.billing.confirm_payment(payment)
            detail = "Pagamento confirmado e assinatura liberada."
        elif snapshot.status in {PaymentStatus.REJECTED, PaymentStatus.CANCELED}:
            await self.billing.fail_payment(payment)
            detail = "Pagamento recusado; assinatura em período de tolerância."
        else:
            payment.status = snapshot.status
            await self.session.commit()
            detail = f"Pagamento em {snapshot.status.lower()}."

        event.status = "PROCESSED"
        event.processed_at = datetime.now(UTC)
        event.detail = detail
        await self.session.commit()

        logger.info(
            "payment.webhook_processed",
            webhook_event=event_id,
            status=snapshot.status,
            reference=payment.reference,
        )
        return WebhookResult(
            accepted=True,
            duplicate=False,
            detail=detail,
            payment_reference=payment.reference,
        )
