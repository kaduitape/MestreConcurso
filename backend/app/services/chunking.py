"""Divisão do edital em trechos indexáveis, preservando página e posição.

A quebra segue a estrutura do documento (itens numerados, artigos, anexos) antes de
respeitar o tamanho alvo: um trecho que atravessa duas seções perde valor como prova.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.notice_analysis import NoticeSectionKind
from app.services.pdf_extractor import PageText

TARGET_TOKENS = 700
OVERLAP_TOKENS = 120
MIN_CHUNK_TOKENS = 60
CHARS_PER_TOKEN = 4  # aproximação para orçamento; o uso real vem do provedor

# Cabeçalhos típicos de edital brasileiro. Itens numerados comuns ("1.2 O candidato…")
# NÃO são cabeçalho: só entram os títulos de seção, em caixa alta e curtos.
_NUMBERED_TITLE = re.compile(r"^\s*(\d{1,2}(?:\.\d{1,2}){0,2})[\.\)]?\s+(\S.{2,110})$")
_NAMED_TITLE = (
    re.compile(r"^\s*(ANEXO\s+[IVXLC0-9]+)\s*[-–—:]?\s*(.{0,110})$", re.IGNORECASE),
    re.compile(r"^\s*(CAP[ÍI]TULO\s+[IVXLC0-9]+)\s*[-–—:]?\s*(.{0,110})$", re.IGNORECASE),
    re.compile(r"^\s*(SE[ÇC][ÃA]O\s+[IVXLC0-9]+)\s*[-–—:]?\s*(.{0,110})$", re.IGNORECASE),
    re.compile(r"^\s*(Art\.\s*\d+[ºo]?)\s*[-–—.]?\s*(.{0,110})$", re.IGNORECASE),
)
MIN_UPPERCASE_RATIO = 0.7

_SECTION_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        NoticeSectionKind.DISCIPLINES,
        (
            "conteúdo programático",
            "conteudo programatico",
            "objetos de avaliação",
            "programa das disciplinas",
        ),
    ),
    (NoticeSectionKind.SCHEDULE, ("cronograma", "calendário", "calendario")),
    (NoticeSectionKind.REGISTRATION, ("inscrição", "inscricao", "inscrições", "taxa")),
    (NoticeSectionKind.POSITIONS, ("cargo", "vagas", "remuneração", "remuneracao")),
    (NoticeSectionKind.EXAM_RULES, ("prova objetiva", "prova discursiva", "das provas")),
    (NoticeSectionKind.ELIMINATION, ("eliminado", "eliminatóri", "eliminatori")),
    (NoticeSectionKind.PHYSICAL_TEST, ("teste de aptidão física", "taf")),
    (NoticeSectionKind.APPEALS, ("recurso", "recursos")),
)


def estimate_tokens(text: str) -> int:
    """Estimativa de tokens por caracteres. Usada só para dimensionar trechos."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def detect_section_kind(heading: str) -> str:
    lowered = heading.lower()
    for kind, hints in _SECTION_HINTS:
        if any(hint in lowered for hint in hints):
            return kind
    return NoticeSectionKind.GENERAL


@dataclass(frozen=True, slots=True)
class Chunk:
    index: int
    content: str
    page_number: int
    page_end: int
    char_start: int
    char_end: int
    heading_path: str | None
    section_kind: str

    @property
    def token_count(self) -> int:
        return estimate_tokens(self.content)


@dataclass(slots=True)
class _Block:
    """Parágrafo ou item, já ancorado em página e posição absoluta."""

    text: str
    page: int
    char_start: int
    char_end: int
    heading: str | None = None


def _uppercase_ratio(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def _match_heading(line: str) -> str | None:
    """Devolve o título quando a linha é cabeçalho de seção, não item de texto."""
    for pattern in _NAMED_TITLE:
        match = pattern.match(line)
        if match:
            return " ".join(part for part in match.groups() if part).strip()[:200] or None

    match = _NUMBERED_TITLE.match(line)
    if match:
        title = match.group(2).strip()
        # Título de seção vem em caixa alta e sem ponto final; item de texto, não.
        if _uppercase_ratio(title) >= MIN_UPPERCASE_RATIO and not title.endswith("."):
            return f"{match.group(1)} {title}"[:200]
    return None


def _build_blocks(pages: list[PageText]) -> tuple[list[_Block], str]:
    """Concatena as páginas mantendo o deslocamento absoluto de cada bloco."""
    blocks: list[_Block] = []
    buffer: list[str] = []
    offset = 0
    current_heading: str | None = None

    for page in pages:
        for line in page.text.split("\n"):
            stripped = line.strip()
            start = offset
            offset += len(line) + 1
            buffer.append(line)
            if not stripped:
                continue

            heading = _match_heading(stripped)
            if heading:
                current_heading = heading
            blocks.append(
                _Block(
                    text=stripped,
                    page=page.number,
                    char_start=start,
                    char_end=start + len(line),
                    heading=current_heading,
                )
            )
        buffer.append("")
        offset += 1

    return blocks, "\n".join(buffer)


def chunk_pages(
    pages: list[PageText],
    *,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[Chunk]:
    """Gera os trechos indexáveis do documento."""
    blocks, _ = _build_blocks(pages)
    if not blocks:
        return []

    chunks: list[Chunk] = []
    current: list[_Block] = []
    current_tokens = 0

    def flush() -> None:
        nonlocal current, current_tokens
        if not current:
            return
        content = "\n".join(block.text for block in current).strip()
        if not content:
            current = []
            current_tokens = 0
            return

        # Prioriza um cabeçalho que comece dentro do trecho; senão, herda o vigente.
        heading = next(
            (
                block.heading
                for block in reversed(current)
                if block.heading and _match_heading(block.text)
            ),
            current[0].heading,
        )
        chunks.append(
            Chunk(
                index=len(chunks),
                content=content,
                page_number=current[0].page,
                page_end=current[-1].page,
                char_start=current[0].char_start,
                char_end=current[-1].char_end,
                heading_path=heading,
                section_kind=detect_section_kind(heading or content[:160]),
            )
        )
        # Sobreposição: os últimos blocos entram no próximo trecho para não cortar contexto.
        overlap: list[_Block] = []
        tokens = 0
        for block in reversed(current):
            block_tokens = estimate_tokens(block.text)
            if tokens + block_tokens > overlap_tokens:
                break
            overlap.insert(0, block)
            tokens += block_tokens
        current = overlap
        current_tokens = tokens

    for block in blocks:
        block_tokens = estimate_tokens(block.text)
        starts_section = block.heading is not None and _match_heading(block.text) is not None

        if (
            current and starts_section and current_tokens >= MIN_CHUNK_TOKENS
        ) or current_tokens + block_tokens > target_tokens:
            flush()

        current.append(block)
        current_tokens += block_tokens

    # Último bloco: descarta a sobreposição residual para não duplicar conteúdo.
    if current:
        content = "\n".join(block.text for block in current).strip()
        already_covered = bool(chunks) and content and content in chunks[-1].content
        if not already_covered:
            flush()

    return chunks
