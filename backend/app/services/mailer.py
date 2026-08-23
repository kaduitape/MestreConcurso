"""Despacho de e-mails: assíncrono via Celery, com fallback direto."""

from __future__ import annotations

from dataclasses import asdict

from app.core.config import settings
from app.core.logging import get_logger
from app.services.email import EmailMessageData, get_email_backend

logger = get_logger(__name__)


class EmailDispatcher:
    """Envia por worker quando há broker; caso contrário, envia inline.

    Nunca deixa uma falha de e-mail derrubar o fluxo de autenticação — o erro é
    registrado e o chamador segue, já que o usuário pode pedir reenvio.
    """

    async def dispatch(self, message: EmailMessageData) -> None:
        if settings.email_backend == "console":
            await get_email_backend().send(message)
            return
        try:
            from app.workers.tasks.email import send_email_task

            send_email_task.apply_async(kwargs={"payload": asdict(message)}, retry=False)
        except Exception as exc:
            logger.warning("email.enqueue_failed", error=str(exc), to=message.to)
            try:
                await get_email_backend().send(message)
            except Exception as inner:
                logger.error("email.send_failed", error=str(inner), to=message.to)


_dispatcher = EmailDispatcher()


def get_email_dispatcher() -> EmailDispatcher:
    return _dispatcher
