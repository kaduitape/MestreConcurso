"""Mestre IA: preparo da pergunta, fusão da busca e conferência das citações."""

from __future__ import annotations

from app.domain.tutor import (
    ClaimStatus,
    Intent,
    Passage,
    RawClaim,
    budget_passages,
    detect_intents,
    expand_acronyms,
    fuse,
    lexical_rank,
    normalize,
    prepare,
    reciprocal_rank_fusion,
    verify_answer,
)
from app.domain.tutor.fusion import MIN_TOP_SCORE

TRECHO = (
    "O regime disciplinar diferenciado poderá ser aplicado ao preso provisório, "
    "conforme o artigo 52 da Lei de Execução Penal."
)


def _passage(chunk_id: int, content: str = TRECHO, score: float = 0.8) -> Passage:
    return Passage(
        chunk_id=chunk_id,
        content=content,
        page_number=34,
        char_start=0,
        document_id=1,
        document_title="Edital PCDF 2026",
        score=score,
    )


# --------------------------------------------------------------------------- #
# Preparo da pergunta
# --------------------------------------------------------------------------- #
def test_normalization_removes_accent_case_and_punctuation() -> None:
    assert normalize("  Qual é a REGRA do artigo 52?  ") == "qual e a regra do artigo 52"


def test_known_acronyms_are_expanded_without_losing_the_original() -> None:
    expanded = expand_acronyms(normalize("o que a LEP diz sobre o RDD"))

    assert "lep" in expanded
    assert "lei de execucao penal" in expanded


def test_unknown_acronym_is_left_alone_instead_of_guessed() -> None:
    expanded = expand_acronyms(normalize("o que diz a XYZW sobre isso"))

    assert expanded == "o que diz a xyzw sobre isso"


def test_keywords_drop_stopwords_and_keep_order() -> None:
    prepared = prepare("Qual é o prazo de inscrição no edital?")

    assert "prazo" in prepared.keywords
    assert "inscricao" in prepared.keywords
    assert "qual" not in prepared.keywords


def test_intent_routing_is_rule_based() -> None:
    assert detect_intents(normalize("como está meu desempenho em penal?")) == [Intent.PERFORMANCE]
    assert Intent.PRIORITY in detect_intents(normalize("o que estudar agora?"))
    assert Intent.BOARD in detect_intents(normalize("como a banca CESPE cobra isso?"))
    assert Intent.NOTICE in detect_intents(normalize("qual a data da prova no edital?"))


def test_question_without_trigger_is_treated_as_concept() -> None:
    prepared = prepare("explique a diferença entre dolo eventual e culpa consciente")

    assert prepared.intents == []
    assert prepared.primary_intent == Intent.CONCEPT


# --------------------------------------------------------------------------- #
# Fusão e porta de corte
# --------------------------------------------------------------------------- #
def test_rrf_rewards_agreement_between_the_two_lists() -> None:
    scores = reciprocal_rank_fusion([[10, 20, 30], [20, 10, 40]])

    # 20 aparece em 1º e 2º; 10 em 2º e 1º — empatam acima dos demais.
    assert scores[20] == scores[10]
    assert scores[20] > scores[30]
    assert scores[20] > scores[40]


def test_lexical_rank_counts_terms_present_in_the_passage() -> None:
    order = lexical_rank(
        ["regime", "disciplinar"],
        [_passage(1), _passage(2, content="Texto sobre inscrição e taxa."), _passage(3)],
    )

    assert 2 not in order
    assert set(order) == {1, 3}


def test_no_result_at_all_is_a_declared_refusal() -> None:
    outcome = fuse(dense=[], lexical_order=[])

    assert outcome.has_base is False
    assert outcome.blocked_reason is not None
    assert "não localizei" in outcome.blocked_reason.lower()


def test_weak_similarity_refuses_instead_of_answering() -> None:
    outcome = fuse(dense=[_passage(1, score=MIN_TOP_SCORE - 0.01)], lexical_order=[1])

    assert outcome.has_base is False
    assert outcome.blocked_reason is not None
    assert "segurança" in outcome.blocked_reason


def test_good_similarity_produces_ordered_passages() -> None:
    outcome = fuse(
        dense=[_passage(1, score=0.9), _passage(2, score=0.7), _passage(3, score=0.6)],
        lexical_order=[2, 1],
    )

    assert outcome.has_base is True
    assert outcome.top_score == 0.9
    assert [item.chunk_id for item in outcome.passages][:2] == [1, 2]


def test_budget_never_cuts_a_passage_in_half() -> None:
    passages = [_passage(1, content="a" * 100), _passage(2, content="b" * 100)]
    selected = budget_passages(passages, max_chars=150)

    assert [item.chunk_id for item in selected] == [1]
    assert selected[0].content == "a" * 100


def test_budget_keeps_at_least_one_passage_even_if_it_is_long() -> None:
    selected = budget_passages([_passage(1, content="a" * 500)], max_chars=100)

    assert len(selected) == 1


# --------------------------------------------------------------------------- #
# Conferência das citações
# --------------------------------------------------------------------------- #
def test_literal_quote_is_confirmed_with_page_and_document() -> None:
    answer = verify_answer(
        [
            RawClaim(
                text="O RDD pode ser aplicado ao preso provisório.",
                quote="poderá ser aplicado ao preso provisório",
            )
        ],
        [_passage(7)],
    )

    claim = answer.claims[0]
    assert claim.status == ClaimStatus.CITED
    assert claim.chunk_id == 7
    assert claim.page_number == 34
    assert claim.document_title == "Edital PCDF 2026"
    assert answer.is_refusal is False


def test_quote_that_does_not_exist_is_marked_unsourced_not_deleted() -> None:
    answer = verify_answer(
        [
            RawClaim(text="Fato com origem.", quote="conforme o artigo 52 da Lei de Execução"),
            RawClaim(text="Fato inventado.", quote="o prazo de recurso é de trinta dias úteis"),
        ],
        [_passage(7)],
    )

    assert answer.claims[0].status == ClaimStatus.CITED
    inventado = answer.claims[1]
    assert inventado.status == ClaimStatus.UNSOURCED
    assert inventado.note is not None
    # A afirmação continua visível, marcada — não some sem o candidato saber.
    assert inventado.text == "Fato inventado."


def test_short_quote_does_not_count_as_proof() -> None:
    answer = verify_answer([RawClaim(text="Afirmação factual.", quote="artigo 52")], [_passage(7)])

    assert answer.claims[0].status == ClaimStatus.UNSOURCED
    assert "citação" in (answer.claims[0].note or "")


def test_answer_with_no_sustained_fact_becomes_a_refusal() -> None:
    answer = verify_answer(
        [
            RawClaim(text="Primeiro invento.", quote="texto que nao existe no documento algum"),
            RawClaim(text="Segundo invento.", quote="outro texto igualmente inexistente aqui"),
        ],
        [_passage(7)],
    )

    assert answer.is_refusal is True
    assert answer.refusal_reason is not None
    assert "sem origem" in answer.refusal_reason


def test_statistics_and_guidance_do_not_need_a_quote() -> None:
    answer = verify_answer(
        [
            RawClaim(text="Você acertou 62% em Direito Penal.", kind="STATISTIC"),
            RawClaim(text="Resolva 20 questões deste assunto hoje.", kind="GUIDANCE"),
        ],
        [_passage(7)],
    )

    assert [claim.status for claim in answer.claims] == [
        ClaimStatus.COMPUTED,
        ClaimStatus.COMPUTED,
    ]
    assert answer.is_refusal is False
    assert answer.coverage()["facts"] == 0


def test_coverage_reports_how_much_of_the_answer_has_a_source() -> None:
    answer = verify_answer(
        [
            RawClaim(text="Com origem.", quote="conforme o artigo 52 da Lei de Execução"),
            RawClaim(text="Sem origem.", quote="frase que nao aparece em lugar nenhum aqui"),
            RawClaim(text="Estude isso hoje.", kind="GUIDANCE"),
        ],
        [_passage(7)],
    )
    coverage = answer.coverage()

    assert coverage["claims"] == 3
    assert coverage["facts"] == 2
    assert coverage["resolved"] == 1
    assert coverage["ratio"] == 0.5


def test_retrieval_refusal_short_circuits_the_verification() -> None:
    answer = verify_answer([], [], refusal="Não localizei isso na sua base.")

    assert answer.is_refusal is True
    assert answer.claims == []
