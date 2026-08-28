"""Configuração do Celery (filas, agendamentos e políticas)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging(settings.log_level, settings.log_format)

celery_app = Celery(
    "mestre_concurso",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks.email",
        "app.workers.tasks.maintenance",
        "app.workers.tasks.documents",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    task_default_queue="default",
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
    task_routes={
        "email.*": {"queue": "notifications"},
        "maintenance.*": {"queue": "default"},
        "documents.*": {"queue": "documents"},
        # Fases seguintes: ai.* (LLM dedicado), analytics.*
    },
    beat_schedule={
        "purge-expired-tokens-and-sessions": {
            "task": "maintenance.purge_expired",
            "schedule": crontab(minute=15),
        },
    },
)
