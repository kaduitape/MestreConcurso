"""Extração de texto de PDF, com detecção de necessidade de OCR.

O edital é conteúdo não confiável: aqui só extraímos e medimos. Nada do que sai
daqui é tratado como instrução — o envelope de documento não confiável é aplicado
mais adiante, na camada de IA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import pymupdf

from app.core.config import settings
from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.models.document import ExtractionMethod

logger = get_logger(__name__)

# Abaixo disso a página é considerada "sem camada de texto" (PDF escaneado).
MIN_CHARS_PER_PAGE = 120
# Abaixo desta fração de páginas com texto, o documento precisa de OCR.
MIN_TEXT_COVERAGE = 0.6

_MULTI_SPACE = re.compile(r"[ \t ]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")
# Hifenização de fim de linha ("adminis-\ntração" -> "administração").
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")


@dataclass(frozen=True, slots=True)
class PageText:
    number: int
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text.strip())

    @property
    def has_text_layer(self) -> bool:
        return self.char_count >= MIN_CHARS_PER_PAGE


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    pages: list[PageText] = field(default_factory=list)
    method: str = ExtractionMethod.TEXT_LAYER
    ocr_pages: list[int] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def char_count(self) -> int:
        return sum(page.char_count for page in self.pages)

    @property
    def text_coverage(self) -> float:
        """Fração de páginas que trouxeram texto aproveitável."""
        if not self.pages:
            return 0.0
        return sum(1 for page in self.pages if page.has_text_layer) / len(self.pages)

    @property
    def needs_ocr(self) -> bool:
        return self.text_coverage < MIN_TEXT_COVERAGE

    @property
    def full_text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)


def normalize_text(raw: str) -> str:
    """Limpeza conservadora: junta hifenização e espaços, preserva quebras de bloco."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _MULTI_SPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


@lru_cache(maxsize=1)
def ocr_available() -> bool:
    """Informa se o OCR pode ser usado neste ambiente (Tesseract instalado)."""
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
    except Exception:
        return False
    return True


def _ocr_page(page: pymupdf.Page) -> str:
    """Rasteriza a página e passa pelo Tesseract (português)."""
    import pytesseract
    from PIL import Image

    pixmap = page.get_pixmap(dpi=220)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    return pytesseract.image_to_string(image, lang="por")


def extract_pdf(content: bytes, *, allow_ocr: bool = True) -> ExtractionResult:
    """Extrai o texto página a página, recorrendo a OCR só onde for necessário."""
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise ValidationError(
            "Não foi possível abrir o PDF enviado.", code="unreadable_pdf"
        ) from exc

    with document:
        if document.page_count > settings.max_pdf_pages:
            raise ValidationError(
                f"O PDF tem {document.page_count} páginas e o limite é {settings.max_pdf_pages}.",
                code="pdf_too_long",
                details={"page_count": document.page_count},
            )
        if document.needs_pass:
            raise ValidationError("O PDF está protegido por senha.", code="encrypted_pdf")

        pages: list[PageText] = []
        ocr_pages: list[int] = []
        can_ocr = allow_ocr and ocr_available()

        for index in range(document.page_count):
            page = document[index]
            number = index + 1
            text = normalize_text(page.get_text("text"))
            if len(text) < MIN_CHARS_PER_PAGE and can_ocr:
                try:
                    text = normalize_text(_ocr_page(page))
                    if text:
                        ocr_pages.append(number)
                except Exception as exc:
                    logger.warning("pdf.ocr_failed", page=number, error=str(exc))
            pages.append(PageText(number=number, text=text))

    method = ExtractionMethod.TEXT_LAYER
    if ocr_pages:
        method = ExtractionMethod.OCR if len(ocr_pages) == len(pages) else ExtractionMethod.MIXED

    result = ExtractionResult(pages=pages, method=method, ocr_pages=ocr_pages)
    logger.info(
        "pdf.extracted",
        pages=result.page_count,
        chars=result.char_count,
        coverage=round(result.text_coverage, 3),
        method=method,
        ocr_pages=len(ocr_pages),
    )
    return result
