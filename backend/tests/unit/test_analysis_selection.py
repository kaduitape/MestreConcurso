"""Escolha dos trechos enviados ao modelo e montagem do contexto."""

from __future__ import annotations

from app.models.document import DocumentChunk
from app.services.notice_analysis import (
    build_document_context,
    estimate_context_tokens,
    select_chunks_for_extraction,
)


def _chunk(index: int, kind: str, size: int = 100, page: int = 1) -> DocumentChunk:
    return DocumentChunk(
        document_id=1,
        chunk_index=index,
        content="x" * size,
        page_number=page,
        char_start=0,
        char_end=size,
        section_kind=kind,
    )


def test_priority_sections_survive_the_budget() -> None:
    chunks = [
        _chunk(0, "ATTACHMENT", 400),
        _chunk(1, "GENERAL", 400),
        _chunk(2, "APPEALS", 400),
        _chunk(3, "REGISTRATION", 400),
    ]
    selected = select_chunks_for_extraction(chunks, max_chars=800)

    kinds = {chunk.section_kind for chunk in selected}
    # Com orçamento apertado ficam as seções que carregam os campos pedidos.
    assert kinds == {"GENERAL", "REGISTRATION"}


def test_selection_keeps_document_order() -> None:
    chunks = [_chunk(index, "GENERAL", 50) for index in range(5)]
    selected = select_chunks_for_extraction(chunks, max_chars=10_000)
    assert [chunk.chunk_index for chunk in selected] == [0, 1, 2, 3, 4]


def test_selection_respects_budget() -> None:
    chunks = [_chunk(index, "GENERAL", 300) for index in range(10)]
    selected = select_chunks_for_extraction(chunks, max_chars=1000)
    assert sum(len(chunk.content) for chunk in selected) <= 1000


def test_context_marks_page_and_chunk() -> None:
    context = build_document_context([_chunk(7, "GENERAL", 20, page=12)])
    # O marcador é o que permite ao modelo devolver a página correta da citação.
    assert "[pagina 12 | trecho 7]" in context


def test_context_estimate_is_positive() -> None:
    assert estimate_context_tokens([_chunk(0, "GENERAL", 400)]) > 0
