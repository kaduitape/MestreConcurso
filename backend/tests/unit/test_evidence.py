"""O validador de prova é o que separa fato de suposição."""

from __future__ import annotations

from app.domain.evidence import ChunkRef, coverage_summary, normalize_for_match, verify_quote
from app.models.notice_analysis import EvidenceLevel

CHUNKS = [
    ChunkRef(
        id=1,
        content="1.3 A remuneração inicial do cargo é de R$ 8.157,00, conforme o Anexo I.",
        page_number=1,
        char_start=1000,
    ),
    ChunkRef(
        id=2,
        content="3.1 A prova objetiva será aplicada no dia 15 de março de 2026.",
        page_number=2,
        char_start=2000,
    ),
]


def test_exact_quote_is_official() -> None:
    match = verify_quote("A remuneração inicial do cargo é de R$ 8.157,00", CHUNKS)

    assert match.level == EvidenceLevel.OFFICIAL
    assert match.is_official is True
    assert match.page_number == 1
    assert match.chunk_id == 1
    assert match.char_start is not None and match.char_start >= 1000


def test_accent_and_spacing_differences_still_match() -> None:
    # O modelo costuma normalizar acento e espaçamento; isso não invalida a prova.
    match = verify_quote("a  remuneracao   inicial do cargo e de R$ 8.157,00", CHUNKS)
    assert match.level == EvidenceLevel.OFFICIAL


def test_invented_quote_is_downgraded_to_inferred() -> None:
    match = verify_quote("O salário inicial é de R$ 12.000,00", CHUNKS)

    assert match.level == EvidenceLevel.INFERRED
    assert match.chunk_id is None
    assert match.page_number is None


def test_missing_quote_is_not_found() -> None:
    assert verify_quote(None, CHUNKS).level == EvidenceLevel.NOT_FOUND
    assert verify_quote("   ", CHUNKS).level == EvidenceLevel.NOT_FOUND


def test_too_short_quote_never_counts_as_proof() -> None:
    # "R$ 8.157" apareceria por acaso; trecho curto não sustenta um fato.
    assert verify_quote("R$ 8.157", CHUNKS).level == EvidenceLevel.INFERRED


def test_normalization_is_case_and_accent_insensitive() -> None:
    assert normalize_for_match("Inscrição  ÚNICA") == "inscricao unica"


def test_coverage_summary_counts_and_ratio() -> None:
    summary = coverage_summary(
        [
            EvidenceLevel.OFFICIAL,
            EvidenceLevel.OFFICIAL,
            EvidenceLevel.CONFIRMED,
            EvidenceLevel.INFERRED,
            EvidenceLevel.NOT_FOUND,
        ]
    )
    assert summary["total"] == 5
    assert summary["official"] == 2
    assert summary["confirmed"] == 1
    assert summary["proven_ratio"] == 0.6


def test_coverage_summary_handles_empty() -> None:
    assert coverage_summary([])["proven_ratio"] == 0.0
