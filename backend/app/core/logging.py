"""Logging estruturado com structlog (JSON em produção, colorido em dev)."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)


def _add_context(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    request_id = request_id_ctx.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    user_id = user_id_ctx.get()
    if user_id:
        event_dict.setdefault("user_id", user_id)
    return event_dict


def configure_logging(level: str = "INFO", fmt: str = "json") -> None:
    """Configura structlog + stdlib logging de forma idempotente."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        _add_context,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level, force=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    for noisy in ("uvicorn.access", "sqlalchemy.engine.Engine", "asyncmy"):
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
