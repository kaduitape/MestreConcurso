"""Porta de pagamento — contrato neutro, como a porta de IA da Fase 2.

O sistema não fala Mercado Pago: fala ``PaymentProvider``. Isso mantém o serviço
de assinatura testável sem rede e deixa a troca de adquirente como uma
implementação nova, não uma reescrita.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core.errors import AppError


class PaymentError(AppError):
    status_code = 502
    code = "payment_provider_error"
    message = "O provedor de pagamento não respondeu como esperado."


class PaymentAuthError(PaymentError):
    status_code = 401
    code = "payment_provider_unauthorized"
    message = "Credencial do provedor de pagamento inválida."


class PaymentNotConfiguredError(AppError):
    status_code = 409
    code = "payment_not_configured"
    message = (
        "O provedor de pagamento ainda não foi configurado. Um administrador "
        "precisa cadastrar a credencial antes de cobrar."
    )


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"
    CANCELED = "CANCELED"


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    reference: str
    title: str
    amount_cents: int
    payer_email: str
    #: Para onde o candidato volta depois de pagar.
    success_url: str
    failure_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    provider_reference: str
    #: A URL para onde o candidato é enviado.
    checkout_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentSnapshot:
    provider_reference: str
    status: str
    amount_cents: int
    reference: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    """O que o sistema precisa de um adquirente — nada além."""

    slug: str

    @abstractmethod
    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Cria a cobrança e devolve para onde mandar o candidato."""

    @abstractmethod
    async def fetch_payment(self, provider_reference: str) -> PaymentSnapshot:
        """Consulta o pagamento na origem.

        O webhook diz *que algo aconteceu*; quem diz *o que aconteceu* é esta
        consulta. Confiar no corpo do webhook seria aceitar o status de quem
        quer que consiga chamar a URL.
        """
