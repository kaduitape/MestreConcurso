"""Extração de PDF e divisão em trechos."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.models.document import ExtractionMethod
from app.models.notice_analysis import NoticeSectionKind
from app.services.chunking import chunk_pages, detect_section_kind, estimate_tokens
from app.services.pdf_extractor import extract_pdf, normalize_text
from tests.pdf_fixtures import EDITAL_PAGES, build_edital_pdf, build_scanned_pdf


def test_extracts_every_page_with_text() -> None:
    result = extract_pdf(build_edital_pdf())

    assert result.page_count == len(EDITAL_PAGES)
    assert result.method == ExtractionMethod.TEXT_LAYER
    assert result.text_coverage == 1.0
    assert result.needs_ocr is False
    assert "Cebraspe" in result.pages[0].text
    assert "crase" in result.pages[2].text.lower()


def test_page_numbers_start_at_one() -> None:
    result = extract_pdf(build_edital_pdf())
    assert [page.number for page in result.pages] == [1, 2, 3, 4]


def test_scanned_pdf_is_flagged_for_ocr() -> None:
    # Sem camada de texto e sem Tesseract disponível, o documento é sinalizado
    # em vez de seguir adiante com conteúdo vazio.
    result = extract_pdf(build_scanned_pdf(), allow_ocr=False)
    assert result.text_coverage == 0.0
    assert result.needs_ocr is True


def test_rejects_pdf_above_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import pdf_extractor

    monkeypatch.setattr(pdf_extractor.settings, "max_pdf_pages", 2)
    with pytest.raises(ValidationError) as exc:
        extract_pdf(build_edital_pdf())
    assert exc.value.code == "pdf_too_long"


def test_rejects_corrupted_file() -> None:
    with pytest.raises(ValidationError) as exc:
        extract_pdf(b"%PDF-1.4 conteudo corrompido")
    assert exc.value.code == "unreadable_pdf"


def test_normalize_joins_hyphenated_words() -> None:
    assert normalize_text("adminis-\ntração pública") == "administração pública"
    assert normalize_text("linha   com    espaços") == "linha com espaços"


def test_chunking_preserves_page_and_offsets() -> None:
    result = extract_pdf(build_edital_pdf())
    chunks = chunk_pages(result.pages, target_tokens=120, overlap_tokens=20)

    assert len(chunks) > 1
    assert all(chunk.page_number >= 1 for chunk in chunks)
    assert all(chunk.char_end >= chunk.char_start for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    # Toda informação continua rastreável até a página de origem.
    assert {chunk.page_number for chunk in chunks} <= {1, 2, 3, 4}


def test_chunking_keeps_headings() -> None:
    result = extract_pdf(build_edital_pdf())
    chunks = chunk_pages(result.pages, target_tokens=120, overlap_tokens=20)
    headings = [chunk.heading_path for chunk in chunks if chunk.heading_path]
    assert any("CONTEÚDO PROGRAMÁTICO" in heading.upper() for heading in headings)


def test_chunking_classifies_sections() -> None:
    result = extract_pdf(build_edital_pdf())
    chunks = chunk_pages(result.pages, target_tokens=120, overlap_tokens=20)
    kinds = {chunk.section_kind for chunk in chunks}
    assert NoticeSectionKind.DISCIPLINES in kinds


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("4 DO CONTEÚDO PROGRAMÁTICO", NoticeSectionKind.DISCIPLINES),
        ("5 DO CRONOGRAMA", NoticeSectionKind.SCHEDULE),
        ("2 DAS INSCRIÇÕES", NoticeSectionKind.REGISTRATION),
        ("9 DOS RECURSOS", NoticeSectionKind.APPEALS),
        ("1 DAS DISPOSIÇÕES PRELIMINARES", NoticeSectionKind.GENERAL),
    ],
)
def test_section_detection(heading: str, expected: str) -> None:
    assert detect_section_kind(heading) == expected


def test_empty_document_produces_no_chunks() -> None:
    assert chunk_pages([]) == []


def test_token_estimate_is_monotonic() -> None:
    assert estimate_tokens("a" * 400) > estimate_tokens("a" * 100)
