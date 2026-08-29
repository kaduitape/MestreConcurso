"""Envio de e-mails transacionais (backends: console e SMTP)."""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class EmailMessageData:
    to: str
    subject: str
    text_body: str
    html_body: str | None = None


class EmailBackend:
    async def send(self, message: EmailMessageData) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleEmailBackend(EmailBackend):
    """Backend de desenvolvimento: registra o e-mail no log estruturado."""

    async def send(self, message: EmailMessageData) -> None:
        logger.info(
            "email.sent.console",
            to=message.to,
            subject=message.subject,
            body=message.text_body,
        )


class SmtpEmailBackend(EmailBackend):
    async def send(self, message: EmailMessageData) -> None:
        email = EmailMessage()
        email["From"] = settings.email_from
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.text_body)
        if message.html_body:
            email.add_alternative(message.html_body, subtype="html")

        await aiosmtplib.send(
            email,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_tls,
            use_tls=settings.smtp_ssl,
            timeout=15,
        )
        logger.info("email.sent.smtp", to=message.to, subject=message.subject)


def get_email_backend() -> EmailBackend:
    return SmtpEmailBackend() if settings.email_backend == "smtp" else ConsoleEmailBackend()


def _layout(title: str, intro: str, action_label: str, action_url: str, footer: str) -> str:
    return f"""\
<!doctype html>
<html lang="pt-BR"><body style="margin:0;background:#0b1120;padding:32px;font-family:
  -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0">
  <div style="max-width:520px;margin:0 auto;background:#111a2e;border:1px solid #1e293b;
    border-radius:16px;padding:32px">
    <p style="margin:0 0 8px;font-size:13px;letter-spacing:.12em;color:#818cf8">
      CONCURSO MESTRE IA</p>
    <h1 style="margin:0 0 16px;font-size:22px;color:#f8fafc">{title}</h1>
    <p style="margin:0 0 24px;line-height:1.6;color:#cbd5e1">{intro}</p>
    <a href="{action_url}" style="display:inline-block;background:linear-gradient(135deg,
      #2563eb,#7c3aed);color:#fff;text-decoration:none;padding:12px 22px;border-radius:10px;
      font-weight:600">{action_label}</a>
    <p style="margin:24px 0 0;font-size:12px;color:#64748b;line-height:1.6">{footer}</p>
    <p style="margin:12px 0 0;font-size:12px;color:#475569;word-break:break-all">{action_url}</p>
  </div>
</body></html>"""


def build_verification_email(to: str, name: str, token: str) -> EmailMessageData:
    url = f"{settings.frontend_url}/verificar-email?token={token}"
    hours = settings.email_verification_expire_hours
    return EmailMessageData(
        to=to,
        subject="Confirme seu e-mail — Game of Concursos",
        text_body=(
            f"Olá, {name}!\n\nConfirme seu e-mail para ativar sua conta:\n{url}\n\n"
            f"O link expira em {hours} horas.\n"
            "Se não foi você quem criou a conta, ignore esta mensagem."
        ),
        html_body=_layout(
            f"Olá, {name}!",
            "Confirme seu e-mail para ativar sua conta e montar sua estratégia de estudo.",
            "Confirmar e-mail",
            url,
            f"O link expira em {hours} horas. Se não foi você, ignore esta mensagem.",
        ),
    )


def build_password_reset_email(to: str, name: str, token: str) -> EmailMessageData:
    url = f"{settings.frontend_url}/redefinir-senha?token={token}"
    minutes = settings.password_reset_expire_minutes
    return EmailMessageData(
        to=to,
        subject="Redefinição de senha — Game of Concursos",
        text_body=(
            f"Olá, {name}!\n\nRecebemos um pedido para redefinir sua senha:\n{url}\n\n"
            f"O link expira em {minutes} minutos e só pode ser usado uma vez.\n"
            "Se não foi você, nenhuma ação é necessária."
        ),
        html_body=_layout(
            "Redefinição de senha",
            f"Olá, {name}. Use o botão abaixo para definir uma nova senha.",
            "Redefinir senha",
            url,
            f"O link expira em {minutes} minutos e é de uso único. "
            "Se não foi você, nenhuma ação é necessária.",
        ),
    )


def build_password_changed_email(to: str, name: str) -> EmailMessageData:
    url = f"{settings.frontend_url}/entrar"
    return EmailMessageData(
        to=to,
        subject="Sua senha foi alterada — Game of Concursos",
        text_body=(
            f"Olá, {name}!\n\nA senha da sua conta foi alterada e todas as outras sessões "
            "foram encerradas.\nSe não foi você, redefina sua senha imediatamente: "
            f"{settings.frontend_url}/esqueci-senha"
        ),
        html_body=_layout(
            "Senha alterada",
            f"Olá, {name}. A senha da sua conta foi alterada e as demais sessões foram encerradas.",
            "Acessar a plataforma",
            url,
            "Se não foi você, redefina sua senha imediatamente.",
        ),
    )
