"""Comandos administrativos executáveis via `python -m app.cli <comando>`."""

from __future__ import annotations

import asyncio
import sys

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, get_session_factory
from app.services.seed import (
    ensure_bootstrap_admin,
    sync_gamification,
    sync_rbac,
    sync_trap_patterns,
)

logger = get_logger(__name__)


async def _seed() -> None:
    factory = get_session_factory()
    async with factory() as session:
        await sync_rbac(session)
        await sync_trap_patterns(session)
        await sync_gamification(session)
        await ensure_bootstrap_admin(session)
    await dispose_engine()


COMMANDS = {"seed": _seed}


def main() -> int:
    configure_logging(settings.log_level, settings.log_format)
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Uso: python -m app.cli [{'|'.join(COMMANDS)}]", file=sys.stderr)
        return 2
    asyncio.run(COMMANDS[sys.argv[1]]())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
