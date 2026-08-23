"""Persistência do que se sabe sobre cada banca.

Tudo o que for apurado — estatística calculada em Python ou interpretação vinda de
IA — é gravado com origem, amostra e validade. As telas leem daqui; o provedor de
IA só é acionado quando não existe registro válido, e o resultado volta para cá.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.board_knowledge import BoardKnowledgeEntry, KnowledgeSource
from app.models.user import User
from app.repositories.board_knowledge import BoardKnowledgeRepository
from app.repositories.catalog import ExamBoardRepository

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KnowledgeInput:
    kind: str
    entry_key: str
    title: str
    content: str | None = None
    data: dict[str, Any] | None = None
    source: str = KnowledgeSource.EDITORIAL
    confidence: Decimal | None = None
    sample_exams: int | None = None
    sample_questions: int | None = None
    period_start_year: int | None = None
    period_end_year: int | None = None
    subject_id: int | None = None
    provider_slug: str | None = None
    model_slug: str | None = None
    prompt_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    ttl_days: int | None = None


class BoardKnowledgeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = BoardKnowledgeRepository(session)
        self.boards = ExamBoardRepository(session)

    async def _board_id(self, board_public_id: str) -> int:
        board = await self.boards.get_by_public_id(board_public_id)
        if board is None:
            raise NotFoundError("Banca não encontrada.")
        return board.id

    async def list_entries(
        self, board_public_id: str, *, kind: str | None = None
    ) -> list[BoardKnowledgeEntry]:
        board_id = await self._board_id(board_public_id)
        return list(await self.repository.list_for_board(board_id, kind=kind))

    async def get_valid(
        self, exam_board_id: int, kind: str, entry_key: str
    ) -> BoardKnowledgeEntry | None:
        """Registro ainda válido — é o que evita nova chamada ao provedor de IA."""
        entry = await self.repository.get_entry(exam_board_id, kind, entry_key)
        if entry is None or entry.is_expired:
            return None
        return entry

    async def upsert(
        self,
        board_public_id: str,
        payload: KnowledgeInput,
        *,
        actor: User | None = None,
    ) -> BoardKnowledgeEntry:
        board_id = await self._board_id(board_public_id)
        entry = await self.repository.get_entry(board_id, payload.kind, payload.entry_key)
        now = datetime.now(UTC)

        if entry is None:
            entry = BoardKnowledgeEntry(
                exam_board_id=board_id, kind=payload.kind, entry_key=payload.entry_key
            )
            self.session.add(entry)

        entry.title = payload.title
        entry.content = payload.content
        entry.data = payload.data or {}
        entry.source = payload.source
        entry.confidence = payload.confidence
        entry.sample_exams = payload.sample_exams
        entry.sample_questions = payload.sample_questions
        entry.period_start_year = payload.period_start_year
        entry.period_end_year = payload.period_end_year
        entry.subject_id = payload.subject_id
        entry.provider_slug = payload.provider_slug
        entry.model_slug = payload.model_slug
        entry.prompt_version = payload.prompt_version
        entry.input_tokens = payload.input_tokens
        entry.output_tokens = payload.output_tokens
        entry.collected_at = now
        entry.expires_at = now + timedelta(days=payload.ttl_days) if payload.ttl_days else None
        if actor is not None and payload.source == KnowledgeSource.EDITORIAL:
            entry.reviewed_by_user_id = actor.id
            entry.reviewed_at = now

        await self.session.commit()
        await self.session.refresh(entry)
        logger.info(
            "board_knowledge.saved",
            board_id=board_id,
            kind=payload.kind,
            key=payload.entry_key,
            source=payload.source,
        )
        return entry

    async def delete(self, board_public_id: str, entry_id: int) -> None:
        board_id = await self._board_id(board_public_id)
        entry = await self.repository.get(entry_id)
        if entry is None or entry.exam_board_id != board_id:
            raise NotFoundError("Registro de conhecimento não encontrado.")
        await self.repository.delete(entry)
        await self.session.commit()

    async def coverage(self, board_public_id: str) -> dict[str, Any]:
        """Resumo do que já está guardado — mostra o que ainda precisaria de apuração."""
        board_id = await self._board_id(board_public_id)
        entries = await self.repository.list_for_board(board_id)
        by_kind: dict[str, int] = {}
        for entry in entries:
            by_kind[entry.kind] = by_kind.get(entry.kind, 0) + 1
        return {
            "total": len(entries),
            "by_kind": by_kind,
            "by_source": await self.repository.count_by_source(board_id),
            "expired": sum(1 for entry in entries if entry.is_expired),
            "ai_tokens_stored": sum(entry.input_tokens + entry.output_tokens for entry in entries),
        }
