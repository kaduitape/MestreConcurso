"""Mercado Pago — implementação da porta de pagamento.

Duas decisões de segurança valem ser lidas antes do código:

**A assinatura do webhook é verificada.** O Mercado Pago envia `x-signature` no
formato ``ts=<timestamp>,v1=<hmac>`` e o manifesto assinado é
``id:<data.id>;request-id:<x-request-id>;ts:<ts>;``, com HMAC-SHA256 sobre o
segredo do webhook. A comparação é feita com ``compare_digest``, e há janela de
tolerância de tempo para barrar reenvio antigo.

**O corpo do webhook nunca é a verdade.** Ele informa um id; o status vem de uma
consulta à API com a credencial da conta. Aceitar o status do corpo permitiria a
qualquer um que descubra a URL declarar um pagamento aprovado.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from app.core.logging import get_logger
from app.payments.base import (
    CheckoutRequest,
    CheckoutSession,
    PaymentAuthError,
    PaymentError,
    PaymentProvider,
    PaymentSnapshot,
    PaymentStatus,
)

logger = get_logger(__name__)

API_BASE = "https://api.mercadopago.com"
REQUEST_TIMEOUT = 20.0

# Fora desta janela, a notificação é considerada reenvio e recusada.
SIGNATURE_TOLERANCE_SECONDS = 600

#: Tradução dos status do provedor para os nossos. O que não estiver aqui vira
#: ``PENDING``: um status desconhecido nunca libera acesso.
STATUS_MAP: dict[str, str] = {
    "approved": PaymentStatus.APPROVED,
    "authorized": PaymentStatus.APPROVED,
    "in_process": PaymentStatus.PENDING,
    "pending": PaymentStatus.PENDING,
    "rejected": PaymentStatus.REJECTED,
    "cancelled": PaymentStatus.CANCELED,
    "refunded": PaymentStatus.REFUNDED,
    "charged_back": PaymentStatus.REFUNDED,
}


def verify_signature(
    *,
    signature_header: str | None,
    request_id: str | None,
    data_id: str | None,
    secret: str,
    now: float | None = None,
    tolerance: int = SIGNATURE_TOLERANCE_SECONDS,
) -> tuple[bool, str]:
    """Confere a assinatura do webhook. Devolve (válida, motivo)."""
    if not signature_header:
        return False, "Notificação sem cabeçalho de assinatura."
    if not secret:
        return False, "Segredo de webhook não configurado."

    parts: dict[str, str] = {}
    for chunk in signature_header.split(","):
        key, _, value = chunk.strip().partition("=")
        if key and value:
            parts[key.strip()] = value.strip()

    timestamp = parts.get("ts")
    received = parts.get("v1")
    if not timestamp or not received:
        return False, "Cabeçalho de assinatura em formato inesperado."

    try:
        moment = int(timestamp)
    except ValueError:
        return False, "Carimbo de tempo inválido na assinatura."

    reference = now if now is not None else time.time()
    if abs(reference - moment) > tolerance:
        return False, "Notificação fora da janela de tempo aceita."

    # O manifesto é montado exatamente na ordem documentada pelo provedor.
    manifest = f"id:{data_id or ''};request-id:{request_id or ''};ts:{timestamp};"
    expected = hmac.new(
        secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received):
        return False, "Assinatura não confere."
    return True, ""


class MercadoPagoProvider(PaymentProvider):
    slug = "mercadopago"

    def __init__(self, access_token: str, *, base_url: str = API_BASE) -> None:
        self._token = access_token
        self._base_url = base_url.rstrip("/")

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            # Reenvio da mesma criação não gera duas cobranças.
            headers["X-Idempotency-Key"] = idempotency_key
        return headers

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        payload: dict[str, Any] = {
            "items": [
                {
                    "title": request.title,
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": round(request.amount_cents / 100, 2),
                }
            ],
            "payer": {"email": request.payer_email},
            "external_reference": request.reference,
            "back_urls": {
                "success": request.success_url,
                "failure": request.failure_url,
                "pending": request.failure_url,
            },
            "auto_return": "approved",
            "metadata": request.metadata,
        }

        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{self._base_url}/checkout/preferences",
                    json=payload,
                    headers=self._headers(idempotency_key=request.reference),
                )
        except httpx.HTTPError as error:
            raise PaymentError("Não foi possível falar com o provedor de pagamento.") from error

        if response.status_code in (401, 403):
            raise PaymentAuthError()
        if response.status_code >= 400:
            logger.warning("payment.checkout_failed", status=response.status_code)
            raise PaymentError("O provedor recusou a criação da cobrança.")

        body = response.json()
        url = body.get("init_point") or body.get("sandbox_init_point")
        if not url:
            raise PaymentError("O provedor não devolveu o endereço de pagamento.")

        return CheckoutSession(
            provider_reference=str(body.get("id", "")), checkout_url=str(url), raw=body
        )

    async def fetch_payment(self, provider_reference: str) -> PaymentSnapshot:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{self._base_url}/v1/payments/{provider_reference}",
                    headers=self._headers(),
                )
        except httpx.HTTPError as error:
            raise PaymentError("Não foi possível consultar o pagamento.") from error

        if response.status_code in (401, 403):
            raise PaymentAuthError()
        if response.status_code >= 400:
            raise PaymentError("O provedor não encontrou este pagamento.")

        body = response.json()
        amount = body.get("transaction_amount") or 0
        return PaymentSnapshot(
            provider_reference=str(body.get("id", provider_reference)),
            status=STATUS_MAP.get(str(body.get("status", "")), PaymentStatus.PENDING),
            amount_cents=round(float(amount) * 100),
            reference=body.get("external_reference"),
            raw=body,
        )
