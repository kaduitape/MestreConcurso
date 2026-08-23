"""Progresso da análise de edital, persistido para poder ser acompanhado ao vivo.

O worker roda em outro processo, então o estado precisa estar no banco: é ele que
alimenta a tela de acompanhamento (SSE) e sobrevive a reinício do container.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.notice import Notice

logger = get_logger(__name__)


class StepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


# Ordem fixa das etapas exibidas ao usuário.
STEPS: tuple[tuple[str, str], ...] = (
    ("read", "Lendo o arquivo enviado"),
    ("extract", "Extraindo o texto do PDF"),
    ("structure", "Estruturando seções e trechos"),
    ("index", "Indexando para busca semântica"),
    ("ai", "Identificando os dados do edital"),
    ("verify", "Conferindo cada citação no documento"),
    ("persist", "Gravando o resultado"),
)


def initial_steps() -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, "status": StepStatus.PENDING, "detail": None, "at": None}
        for key, label in STEPS
    ]


class AnalysisProgress:
    """Escreve o andamento em ``notices.extra['analysis']``."""

    def __init__(self, session: AsyncSession, notice: Notice) -> None:
        self.session = session
        self.notice = notice

    def _state(self) -> dict[str, Any]:
        extra = dict(self.notice.extra or {})
        analysis = dict(extra.get("analysis") or {})
        if not analysis.get("steps"):
            analysis["steps"] = initial_steps()
        return analysis

    async def start(self) -> None:
        analysis = {
            "steps": initial_steps(),
            "started_at": datetime.now(UTC).isoformat(),
            "finished_at": None,
            "error": None,
        }
        await self._save(analysis)

    async def update(self, key: str, status: str, detail: str | None = None) -> None:
        analysis = self._state()
        for step in analysis["steps"]:
            if step["key"] == key:
                step["status"] = status
                step["detail"] = detail
                step["at"] = datetime.now(UTC).isoformat()
                break
        await self._save(analysis)
        logger.info("notice.analysis.step", key=key, status=status, detail=detail)

    async def finish(self, error: str | None = None) -> None:
        analysis = self._state()
        analysis["finished_at"] = datetime.now(UTC).isoformat()
        analysis["error"] = error
        if error:
            for step in analysis["steps"]:
                if step["status"] == StepStatus.RUNNING:
                    step["status"] = StepStatus.FAILED
                    step["detail"] = error
        await self._save(analysis)

    async def _save(self, analysis: dict[str, Any]) -> None:
        extra = dict(self.notice.extra or {})
        extra["analysis"] = analysis
        # Reatribuir o dicionário inteiro garante que o SQLAlchemy detecte a mudança.
        self.notice.extra = extra
        await self.session.commit()
