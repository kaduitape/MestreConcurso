"""Pipeline de análise de edital: PDF → texto → trechos → índice → IA → prova.

Sequência e responsabilidades:

``ler → extrair → estruturar → indexar → extrair com IA → conferir citações → gravar``

O que a IA faz aqui é interpretar texto. Quem decide se algo vale como fato é o
validador de citações, em Python. Documento já processado (mesmo checksum) e
resposta já obtida (mesma impressão digital) são reaproveitados — nenhum token é
pago duas vezes pelo mesmo edital.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    ChatMessage,
    CompletionRequest,
    ProviderError,
    ProviderNotConfiguredError,
)
from app.ai.prompts import get_prompt, latest_version
from app.ai.schemas import EXPECTED_FIELDS, ExtractedField, NoticeExtraction
from app.ai.vector_store import (
    COLLECTION_NOTICES,
    GLOBAL_TENANT,
    QdrantVectorStore,
    VectorPoint,
    VectorStore,
    new_vector_id,
)
from app.core.config import settings
from app.core.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.evidence import ChunkRef, coverage_summary, verify_quote
from app.models.ai import AIFeature
from app.models.audit import AuditAction
from app.models.document import Document, DocumentChunk, DocumentKind, DocumentStatus
from app.models.notice import Notice, NoticeFile, NoticeFileStatus, NoticeStatus
from app.models.notice_analysis import (
    EvidenceLevel,
    NoticeEvent,
    NoticeFact,
    NoticeSection,
    NoticeSubject,
    NoticeTopic,
)
from app.models.user import User
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService
from app.services.analysis_progress import AnalysisProgress, StepStatus
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.chunking import Chunk, chunk_pages, estimate_tokens
from app.services.pdf_extractor import extract_pdf, ocr_available
from app.services.storage import LocalFileStorage, get_storage

logger = get_logger(__name__)

PROMPT_SLUG = "notice_extraction"
# Orçamento de contexto para a extração; trechos além disso são descartados por
# prioridade de seção, nunca aleatoriamente.
MAX_CONTEXT_CHARS = 90_000

# Seções que mais carregam os campos que precisamos.
_SECTION_PRIORITY = {
    "GENERAL": 0,
    "POSITIONS": 1,
    "REGISTRATION": 2,
    "EXAM_RULES": 3,
    "SCHEDULE": 4,
    "ELIMINATION": 5,
    "DISCIPLINES": 6,
    "PHYSICAL_TEST": 7,
    "APPEALS": 8,
    "ATTACHMENT": 9,
}


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    notice_public_id: str
    document_id: int
    chunk_count: int
    facts_created: int
    subjects_created: int
    events_created: int
    coverage: dict[str, float | int]
    cached: bool
    reused_document: bool


def select_chunks_for_extraction(
    chunks: list[DocumentChunk], *, max_chars: int = MAX_CONTEXT_CHARS
) -> list[DocumentChunk]:
    """Escolhe os trechos que vão ao modelo, priorizando as seções que importam."""
    ordered = sorted(
        chunks,
        key=lambda chunk: (
            _SECTION_PRIORITY.get(chunk.section_kind or "GENERAL", 5),
            chunk.chunk_index,
        ),
    )
    selected: list[DocumentChunk] = []
    total = 0
    for chunk in ordered:
        size = len(chunk.content)
        if total + size > max_chars:
            continue
        selected.append(chunk)
        total += size
    return sorted(selected, key=lambda chunk: chunk.chunk_index)


def build_document_context(chunks: list[DocumentChunk]) -> str:
    """Monta o contexto marcando página e trecho — é assim que a citação fica rastreável."""
    parts = [
        f"[pagina {chunk.page_number} | trecho {chunk.chunk_index}]\n{chunk.content}"
        for chunk in chunks
    ]
    return "\n\n".join(parts)


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class NoticeAnalysisService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: LocalFileStorage | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.session = session
        self.storage = storage or get_storage()
        self.ai_settings = AISettingsService(session)
        self.cache = AICacheService(session)
        self.audit = AuditService(session)
        self._vector_store = vector_store

    # ------------------------------------------------------------------ #
    # Entrada principal
    # ------------------------------------------------------------------ #
    async def analyze(
        self, notice: Notice, *, actor: User | None, context: RequestContext
    ) -> AnalysisOutcome:
        file = self._pick_file(notice)
        progress = AnalysisProgress(self.session, notice)
        await progress.start()

        notice.status = NoticeStatus.PROCESSING
        await self.session.commit()

        try:
            outcome = await self._run(notice, file, progress)
        except AppError as exc:
            notice.status = NoticeStatus.FAILED
            file.status = NoticeFileStatus.FAILED
            file.error_message = exc.message[:500]
            await progress.finish(error=exc.message)
            await self.session.commit()
            logger.warning("notice.analysis.failed", notice=notice.public_id, error=exc.code)
            raise

        notice.status = NoticeStatus.AWAITING_CONFIRMATION
        file.status = NoticeFileStatus.PROCESSED
        file.processed_at = datetime.now(UTC)
        await progress.finish()
        await self.audit.record(
            AuditAction.NOTICE_ANALYZED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice",
            resource_id=notice.public_id,
            meta={
                "facts": outcome.facts_created,
                "subjects": outcome.subjects_created,
                "coverage": outcome.coverage,
                "cached": outcome.cached,
            },
        )
        await self.session.commit()
        return outcome

    def _pick_file(self, notice: Notice) -> NoticeFile:
        if not notice.files:
            raise ConflictError(
                "Envie o PDF do edital antes de analisar.", code="notice_without_file"
            )
        return sorted(notice.files, key=lambda item: item.created_at)[-1]

    # ------------------------------------------------------------------ #
    # Etapas
    # ------------------------------------------------------------------ #
    async def _run(
        self, notice: Notice, file: NoticeFile, progress: AnalysisProgress
    ) -> AnalysisOutcome:
        await progress.update("read", StepStatus.RUNNING)
        content = self.storage.read(file.storage_key)
        await progress.update("read", StepStatus.DONE, f"{round(len(content) / 1024)} KB lidos")

        document, reused = await self._ensure_document(notice, file, content, progress)
        chunks = list(
            (
                await self.session.execute(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_id == document.id)
                    .order_by(DocumentChunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )
        if not chunks:
            raise ValidationError(
                "Não foi possível extrair texto aproveitável deste PDF.",
                code="empty_extraction",
            )

        await self._index_chunks(document, chunks, progress)

        extraction, cached, model_slug, prompt_version = await self._extract_with_ai(
            document, chunks, progress
        )

        await progress.update("verify", StepStatus.RUNNING)
        refs = [
            ChunkRef(
                id=chunk.id,
                content=chunk.content,
                page_number=chunk.page_number,
                char_start=chunk.char_start,
            )
            for chunk in chunks
        ]

        await progress.update("persist", StepStatus.RUNNING)
        facts, levels = await self._persist_facts(
            notice, extraction, refs, model_slug, prompt_version
        )
        subjects = await self._persist_subjects(notice, extraction, refs)
        events = await self._persist_events(notice, extraction, refs)
        await self._persist_sections(notice, chunks)

        coverage = coverage_summary(levels)
        await progress.update(
            "verify",
            StepStatus.DONE,
            f"{coverage['official']} de {coverage['total']} campos com citação conferida",
        )
        await progress.update(
            "persist",
            StepStatus.DONE,
            f"{facts} campos · {subjects} disciplinas · {events} datas",
        )

        extra = dict(notice.extra or {})
        extra["coverage"] = coverage
        notice.extra = extra
        await self.session.commit()

        return AnalysisOutcome(
            notice_public_id=notice.public_id,
            document_id=document.id,
            chunk_count=len(chunks),
            facts_created=facts,
            subjects_created=subjects,
            events_created=events,
            coverage=coverage,
            cached=cached,
            reused_document=reused,
        )

    async def _ensure_document(
        self,
        notice: Notice,
        file: NoticeFile,
        content: bytes,
        progress: AnalysisProgress,
    ) -> tuple[Document, bool]:
        """Reaproveita a extração quando o mesmo PDF já foi processado antes."""
        existing = (
            await self.session.execute(
                select(Document).where(
                    Document.checksum_sha256 == file.checksum_sha256,
                    Document.kind == DocumentKind.NOTICE,
                    Document.status.in_([DocumentStatus.CHUNKED, DocumentStatus.INDEXED]),
                )
            )
        ).scalar_one_or_none()

        if existing is not None:
            file.document_id = existing.id
            await self.session.commit()
            await progress.update("extract", StepStatus.SKIPPED, "documento idêntico já processado")
            await progress.update(
                "structure",
                StepStatus.SKIPPED,
                f"{existing.chunk_count} trechos reaproveitados",
            )
            return existing, True

        await progress.update("extract", StepStatus.RUNNING)
        result = extract_pdf(content)
        if result.needs_ocr:
            hint = (
                "O PDF parece digitalizado e o OCR não está disponível neste ambiente."
                if not ocr_available()
                else "O OCR não conseguiu recuperar texto suficiente deste PDF."
            )
            raise ValidationError(hint, code="ocr_required")

        await progress.update(
            "extract",
            StepStatus.DONE,
            f"{result.page_count} páginas · {result.char_count} caracteres"
            + (f" · OCR em {len(result.ocr_pages)} página(s)" if result.ocr_pages else ""),
        )

        await progress.update("structure", StepStatus.RUNNING)
        chunks = chunk_pages(result.pages)

        document = Document(
            kind=DocumentKind.NOTICE,
            owner_type="notice",
            owner_id=notice.id,
            tenant=GLOBAL_TENANT,
            checksum_sha256=file.checksum_sha256,
            status=DocumentStatus.CHUNKED,
            extraction_method=result.method,
            page_count=result.page_count,
            char_count=result.char_count,
            text_coverage=round(result.text_coverage, 4),
            chunk_count=len(chunks),
        )
        self.session.add(document)
        await self.session.flush()

        self.session.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    page_number=chunk.page_number,
                    page_end=chunk.page_end,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    heading_path=chunk.heading_path,
                    section_kind=chunk.section_kind,
                )
                for chunk in chunks
            ]
        )
        file.document_id = document.id
        file.page_count = result.page_count
        await self.session.commit()

        await progress.update(
            "structure", StepStatus.DONE, f"{len(chunks)} trechos com página e posição"
        )
        return document, False

    async def _index_chunks(
        self, document: Document, chunks: list[DocumentChunk], progress: AnalysisProgress
    ) -> None:
        """Vetoriza os trechos, se houver modelo de embeddings configurado."""
        if document.status == DocumentStatus.INDEXED:
            await progress.update("index", StepStatus.SKIPPED, "já indexado anteriormente")
            return

        try:
            resolved = await self.ai_settings.resolve_feature(AIFeature.EMBEDDINGS)
        except ProviderNotConfiguredError:
            await progress.update(
                "index",
                StepStatus.SKIPPED,
                "sem modelo de embeddings configurado — a busca semântica fica indisponível",
            )
            return

        await progress.update("index", StepStatus.RUNNING)
        try:
            result = await resolved.provider.embed(
                [chunk.content for chunk in chunks], resolved.model_slug
            )
        except ProviderError as exc:
            await progress.update("index", StepStatus.FAILED, exc.message)
            logger.warning("notice.index_failed", error=exc.code)
            return

        store = self._vector_store or QdrantVectorStore()
        dimensions = len(result.vectors[0]) if result.vectors else settings.embedding_dimensions
        await store.ensure_collection(COLLECTION_NOTICES, dimensions)

        points: list[VectorPoint] = []
        for chunk, vector in zip(chunks, result.vectors, strict=False):
            vector_id = new_vector_id()
            chunk.vector_id = vector_id
            chunk.embedding_model = resolved.model_slug
            points.append(
                VectorPoint(
                    id=vector_id,
                    vector=vector,
                    payload={
                        "tenant": document.tenant,
                        "owner_type": document.owner_type,
                        "owner_id": document.owner_id,
                        "document_id": document.id,
                        "chunk_id": chunk.id,
                        "page": chunk.page_number,
                        "section_kind": chunk.section_kind,
                    },
                )
            )

        await store.upsert(COLLECTION_NOTICES, points)
        document.status = DocumentStatus.INDEXED
        document.embedding_model = resolved.model_slug
        document.indexed_at = datetime.now(UTC)
        await self.session.commit()
        await progress.update("index", StepStatus.DONE, f"{len(points)} trechos indexados")

    async def _extract_with_ai(
        self,
        document: Document,
        chunks: list[DocumentChunk],
        progress: AnalysisProgress,
    ) -> tuple[NoticeExtraction, bool, str, str]:
        resolved = await self.ai_settings.resolve_feature(AIFeature.NOTICE_EXTRACTION)
        version = latest_version(PROMPT_SLUG)
        prompt = get_prompt(PROMPT_SLUG, version)

        cache_key = fingerprint(
            feature=AIFeature.NOTICE_EXTRACTION,
            model_slug=resolved.model_slug,
            prompt_version=version,
            payload={"checksum": document.checksum_sha256},
        )
        cached_entry = await self.cache.get(cache_key)
        if cached_entry is not None:
            await progress.update(
                "ai", StepStatus.SKIPPED, "resposta já obtida antes — nenhum token gasto"
            )
            return (
                NoticeExtraction.model_validate(cached_entry.payload),
                True,
                cached_entry.model_slug,
                cached_entry.prompt_version or version,
            )

        await progress.update("ai", StepStatus.RUNNING, f"modelo {resolved.model_slug}")
        selected = select_chunks_for_extraction(chunks)
        context = build_document_context(selected)

        request = CompletionRequest(
            messages=[
                ChatMessage(role="system", content=prompt.template),
                ChatMessage(
                    role="user",
                    # O conteúdo do edital entra como DADO. Instruções que apareçam
                    # dentro dele são ignoradas por contrato explícito no prompt.
                    content=(
                        "Extraia os dados do edital a seguir.\n\n"
                        "<untrusted_document>\n"
                        f"{context}\n"
                        "</untrusted_document>"
                    ),
                ),
            ],
            model=resolved.model_slug,
            temperature=float(resolved.binding.temperature or 0),
            max_output_tokens=resolved.binding.max_output_tokens,
            json_response=True,
        )

        try:
            completion = await resolved.provider.complete(request)
        except ProviderError as exc:
            await progress.update("ai", StepStatus.FAILED, exc.message)
            raise

        try:
            payload = json.loads(completion.content)
            extraction = NoticeExtraction.model_validate(payload)
        except (json.JSONDecodeError, ValueError) as exc:
            await progress.update("ai", StepStatus.FAILED, "resposta fora do formato esperado")
            raise ValidationError(
                "A resposta do modelo não seguiu o formato esperado.",
                code="invalid_ai_response",
            ) from exc

        await self.cache.store(
            cache_key=cache_key,
            feature=AIFeature.NOTICE_EXTRACTION,
            provider_slug=resolved.provider_slug,
            model_slug=resolved.model_slug,
            payload=extraction.model_dump(mode="json"),
            prompt_version=version,
            input_tokens=completion.usage.input_tokens,
            output_tokens=completion.usage.output_tokens,
            ttl_hours=resolved.binding.cache_ttl_hours,
        )
        await progress.update(
            "ai",
            StepStatus.DONE,
            f"{completion.usage.total} tokens · {completion.latency_ms} ms",
        )
        return extraction, False, resolved.model_slug, version

    # ------------------------------------------------------------------ #
    # Persistência
    # ------------------------------------------------------------------ #
    async def _persist_facts(
        self,
        notice: Notice,
        extraction: NoticeExtraction,
        refs: list[ChunkRef],
        model_slug: str,
        prompt_version: str,
    ) -> tuple[int, list[str]]:
        await self.session.execute(
            delete(NoticeFact).where(
                NoticeFact.notice_id == notice.id,
                NoticeFact.evidence_level != EvidenceLevel.CONFIRMED,
            )
        )

        confirmed = {
            fact.field_path
            for fact in (
                await self.session.execute(
                    select(NoticeFact).where(NoticeFact.notice_id == notice.id)
                )
            )
            .scalars()
            .all()
        }

        levels: list[str] = []
        created = 0
        for field_path, label in EXPECTED_FIELDS.items():
            if field_path in confirmed:
                levels.append(EvidenceLevel.CONFIRMED)
                continue

            field = extraction.fields.get(field_path) or ExtractedField()
            match = verify_quote(field.quote, refs) if field.value is not None else None
            level = (
                EvidenceLevel.NOT_FOUND
                if field.value is None
                else (match.level if match else EvidenceLevel.INFERRED)
            )
            levels.append(level)

            self.session.add(
                NoticeFact(
                    notice_id=notice.id,
                    field_path=field_path,
                    label=label,
                    value={"raw": field.value},
                    evidence_level=level,
                    confidence=_parse_decimal(field.confidence),
                    # Página só acompanha o dado quando a citação foi conferida:
                    # página "informada" pelo modelo, sem prova, seria falsa origem.
                    page_number=match.page_number if match else None,
                    quote=match.quote if match else field.quote,
                    char_start=match.char_start if match else None,
                    char_end=match.char_end if match else None,
                    chunk_id=match.chunk_id if match else None,
                    extracted_by="AI",
                    model_slug=model_slug,
                    prompt_version=prompt_version,
                )
            )
            created += 1

        await self.session.flush()
        return created, levels

    async def _persist_subjects(
        self, notice: Notice, extraction: NoticeExtraction, refs: list[ChunkRef]
    ) -> int:
        await self.session.execute(
            delete(NoticeSubject).where(NoticeSubject.notice_id == notice.id)
        )
        await self.session.flush()

        for order, subject in enumerate(extraction.subjects):
            match = verify_quote(subject.quote, refs)
            record = NoticeSubject(
                notice_id=notice.id,
                raw_label=subject.name[:255],
                weight=_parse_decimal(subject.weight),
                questions_count=subject.questions_count,
                order_index=order,
                evidence_level=match.level,
                page_number=match.page_number,
                quote=match.quote,
            )
            self.session.add(record)
            await self.session.flush()

            self.session.add_all(
                [
                    NoticeTopic(
                        notice_subject_id=record.id,
                        raw_label=topic[:500],
                        order_index=index,
                        page_number=record.page_number,
                    )
                    for index, topic in enumerate(subject.topics)
                ]
            )

        await self.session.flush()
        return len(extraction.subjects)

    async def _persist_events(
        self, notice: Notice, extraction: NoticeExtraction, refs: list[ChunkRef]
    ) -> int:
        await self.session.execute(delete(NoticeEvent).where(NoticeEvent.notice_id == notice.id))

        created = 0
        for event in extraction.events:
            start = _parse_date(event.date_start)
            if start is None:
                # Evento sem data legível não vira registro: data inventada é pior que ausente.
                continue
            match = verify_quote(event.quote, refs)
            self.session.add(
                NoticeEvent(
                    notice_id=notice.id,
                    kind=event.kind[:30],
                    title=event.title[:255],
                    date_start=start,
                    date_end=_parse_date(event.date_end),
                    is_critical=event.is_critical,
                    evidence_level=match.level,
                    page_number=match.page_number,
                )
            )
            created += 1

        await self.session.flush()
        return created

    async def _persist_sections(self, notice: Notice, chunks: list[DocumentChunk]) -> None:
        """Guarda as seções detectadas na estruturação (sem IA)."""
        await self.session.execute(
            delete(NoticeSection).where(NoticeSection.notice_id == notice.id)
        )

        seen: dict[str, NoticeSection] = {}
        for chunk in chunks:
            heading = chunk.heading_path
            if not heading or heading in seen:
                if heading and heading in seen:
                    seen[heading].page_end = chunk.page_end or chunk.page_number
                continue
            section = NoticeSection(
                notice_id=notice.id,
                title=heading[:300],
                kind=chunk.section_kind or "GENERAL",
                page_start=chunk.page_number,
                page_end=chunk.page_end or chunk.page_number,
                order_index=len(seen),
            )
            seen[heading] = section
            self.session.add(section)

        await self.session.flush()

    # ------------------------------------------------------------------ #
    # Revisão humana
    # ------------------------------------------------------------------ #
    async def review_fact(
        self,
        notice: Notice,
        fact_id: int,
        *,
        value: Any,
        actor: User,
        context: RequestContext,
    ) -> NoticeFact:
        """Corrigir ou confirmar um campo o promove a CONFIRMADO (origem humana)."""
        fact = (
            await self.session.execute(
                select(NoticeFact).where(
                    NoticeFact.id == fact_id, NoticeFact.notice_id == notice.id
                )
            )
        ).scalar_one_or_none()
        if fact is None:
            raise NotFoundError("Campo não encontrado neste edital.")

        fact.value = {"raw": value}
        fact.evidence_level = EvidenceLevel.CONFIRMED
        fact.extracted_by = "HUMAN"
        fact.reviewed_by_user_id = actor.id
        fact.reviewed_at = datetime.now(UTC)

        await self.audit.record(
            AuditAction.NOTICE_FACT_REVIEWED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice_fact",
            resource_id=str(fact.id),
            meta={"field": fact.field_path},
        )
        await self.session.commit()
        return fact

    async def confirm(self, notice: Notice, *, actor: User, context: RequestContext) -> Notice:
        if notice.status != NoticeStatus.AWAITING_CONFIRMATION:
            raise ConflictError(
                "Só é possível confirmar um edital que terminou a análise.",
                code="notice_not_ready",
            )

        pending = (
            (
                await self.session.execute(
                    select(NoticeFact).where(
                        NoticeFact.notice_id == notice.id,
                        NoticeFact.evidence_level == EvidenceLevel.INFERRED,
                    )
                )
            )
            .scalars()
            .all()
        )

        notice.status = NoticeStatus.CONFIRMED
        extra = dict(notice.extra or {})
        extra["confirmed_at"] = datetime.now(UTC).isoformat()
        extra["pending_inferred_at_confirmation"] = len(pending)
        notice.extra = extra

        await self.audit.record(
            AuditAction.NOTICE_CONFIRMED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice",
            resource_id=notice.public_id,
            meta={"inferred_fields": len(pending)},
        )
        await self.session.commit()
        return notice


def estimate_context_tokens(chunks: list[DocumentChunk]) -> int:
    """Tokens aproximados do contexto — usado para orçamento antes da chamada."""
    return sum(estimate_tokens(chunk.content) for chunk in chunks)


__all__ = [
    "AnalysisOutcome",
    "Chunk",
    "NoticeAnalysisService",
    "build_document_context",
    "estimate_context_tokens",
    "select_chunks_for_extraction",
]
