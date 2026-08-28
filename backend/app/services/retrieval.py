"""Recuperação de trechos para o Mestre IA.

Busca semântica no Qdrant, busca léxica local sobre os candidatos e fusão RRF —
tudo com o filtro de tenant montado dentro do ``VectorStore``. O serviço devolve
trechos com página e documento, porque sem isso não existe citação conferível.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.base import ProviderError, ProviderNotConfiguredError
from app.ai.vector_store import COLLECTION_NOTICES, QdrantVectorStore, VectorStore
from app.core.logging import get_logger
from app.domain.tutor import (
    Passage,
    PreparedQuery,
    RetrievalOutcome,
    budget_passages,
    fuse,
    lexical_rank,
)
from app.models.ai import AIFeature
from app.models.document import DocumentChunk
from app.models.notice import Notice
from app.services.ai_settings import AISettingsService

logger = get_logger(__name__)

# Quantos candidatos a busca semântica traz antes da fusão.
DENSE_LIMIT = 40
# Quantos trechos entram no contexto final.
CONTEXT_LIMIT = 8
# Orçamento de contexto, em caracteres (aproxima o limite de tokens da feature).
CONTEXT_MAX_CHARS = 9000


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    outcome: RetrievalOutcome
    embedding_model: str | None = None


class RetrievalService:
    def __init__(self, session: AsyncSession, vector_store: VectorStore | None = None) -> None:
        self.session = session
        self.ai_settings = AISettingsService(session)
        self._vector_store = vector_store

    async def search(
        self, query: PreparedQuery, *, tenant: str, notice_id: int | None = None
    ) -> RetrievalResult:
        """Recupera os trechos que podem sustentar uma resposta."""
        try:
            resolved = await self.ai_settings.resolve_feature(AIFeature.EMBEDDINGS)
        except ProviderNotConfiguredError:
            return RetrievalResult(
                outcome=RetrievalOutcome(
                    blocked_reason=(
                        "A busca semântica está indisponível: nenhum modelo de embeddings "
                        "foi configurado no painel. Sem ela não consigo citar origem."
                    )
                )
            )

        try:
            embedded = await resolved.provider.embed([query.expanded], resolved.model_slug)
        except ProviderError as exc:
            logger.warning("retrieval.embed_failed", error=exc.code)
            return RetrievalResult(
                outcome=RetrievalOutcome(
                    blocked_reason=(
                        "Não consegui consultar a base agora (falha no provedor de IA). "
                        "Tente novamente em instantes."
                    )
                )
            )

        if not embedded.vectors:
            return RetrievalResult(
                outcome=RetrievalOutcome(blocked_reason="A consulta não pôde ser vetorizada.")
            )

        store = self._vector_store or QdrantVectorStore()
        hits = await store.search(
            COLLECTION_NOTICES,
            embedded.vectors[0],
            tenant=tenant,
            limit=DENSE_LIMIT,
            extra_filter={"document_id": notice_id} if notice_id else None,
        )
        if not hits:
            return RetrievalResult(
                outcome=RetrievalOutcome(
                    blocked_reason=(
                        "Sua base ainda não tem material indexado sobre isso. "
                        "Envie e analise o edital para que eu possa responder com origem."
                    )
                ),
                embedding_model=resolved.model_slug,
            )

        by_chunk = {int(hit.payload.get("chunk_id", 0)): hit.score for hit in hits}
        rows = list(
            (
                await self.session.execute(
                    select(DocumentChunk)
                    .options(selectinload(DocumentChunk.document))
                    .where(DocumentChunk.id.in_([key for key in by_chunk if key]))
                )
            )
            .scalars()
            .all()
        )

        titles = await self._document_titles(rows)
        candidates = [
            Passage(
                chunk_id=row.id,
                content=row.content,
                page_number=row.page_number,
                char_start=row.char_start,
                document_id=row.document_id,
                document_title=titles.get(row.document_id, "Documento"),
                score=by_chunk.get(row.id, 0.0),
                section=row.section_kind,
            )
            for row in rows
        ]
        candidates.sort(key=lambda item: -item.score)

        outcome = fuse(
            dense=candidates,
            lexical_order=lexical_rank(query.keywords, candidates),
            limit=CONTEXT_LIMIT,
        )
        if outcome.has_base:
            outcome = RetrievalOutcome(
                passages=budget_passages(outcome.passages, max_chars=CONTEXT_MAX_CHARS),
                top_score=outcome.top_score,
                dense_count=outcome.dense_count,
                lexical_count=outcome.lexical_count,
            )

        logger.info(
            "retrieval.done",
            tenant=tenant,
            hits=len(hits),
            passages=len(outcome.passages),
            top_score=round(outcome.top_score, 4),
        )
        return RetrievalResult(outcome=outcome, embedding_model=resolved.model_slug)

    async def _document_titles(self, rows: list[DocumentChunk]) -> dict[int, str]:
        """Nome legível de cada documento — é o que aparece no chip de citação."""
        notice_ids = {
            row.document.owner_id
            for row in rows
            if row.document is not None and row.document.owner_type == "notice"
        }
        titles: dict[int, str] = {}
        if notice_ids:
            found = (
                await self.session.execute(
                    select(Notice.id, Notice.title).where(Notice.id.in_(notice_ids))
                )
            ).all()
            by_notice = {int(item[0]): str(item[1]) for item in found}
            for row in rows:
                document = row.document
                if document is not None and document.owner_type == "notice":
                    titles[document.id] = by_notice.get(document.owner_id, "Edital")
        for row in rows:
            titles.setdefault(row.document_id, "Documento")
        return titles
