"""Tarefas de envio de e-mail."""

from __future__ import annotations

import asyncio
from typing import Any

from celery import shared_task

from app.core.logging import get_logger
from app.services.email import EmailMessageData, get_email_backend

logger = get_logger(__name__)


@shared_task(
    name="email.send",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(OSError,),
    retry_backoff=True,
)
def send_email_task(self: Any, payload: dict[str, Any]) -> None:
    """Envia um e-mail transacional já renderizado."""
    message = EmailMessageData(**payload)
    asyncio.run(get_email_backend().send(message))
    logger.info("email.task.sent", to=message.to, subject=message.subject)
