"""O casamento com o catálogo é sugestão, nunca decisão.

O teste mais importante aqui é o que **recusa**: casar conteúdo com o tópico
errado manda o aluno estudar a coisa errada achando que está no lugar certo.
Não casar é melhor, e precisa continuar sendo um resultado possível.
"""

from __future__ import annotations

import pytest

from app.domain.catalog_match import (
    MIN_SCORE,
    STRONG_SCORE,
    TOPIC_PROBLEM_LABEL,
    CatalogEntry,
    MatchReason,
    TopicLabelProblem,
    clean_topic_label,
    normalize,
    score_pair,
    suggest,
    tokens,
    topic_label_problem,
)

DISCIPLINAS = [
    CatalogEntry(public_id="d1", name="Direito Constitucional"),
    CatalogEntry(public_id="d2", name="Direito Administrativo"),
    CatalogEntry(public_id="d3", name="Língua Portuguesa"),
    CatalogEntry(public_id="d4", name="Raciocínio Lógico"),
    CatalogEntry(public_id="d5", name="Informática"),
]


def test_normalize_removes_accent_case_and_punctuation() -> None:
    assert normalize("Raciocínio Lógico-Matemático!") == "raciocinio logico matematico"
    assert normalize("  Língua   Portuguesa  ") == "lingua portuguesa"
    assert normalize("") == ""


def test_noise_words_do_not_distinguish_a_subject() -> None:
    """ "Noções de Direito Administrativo" é a mesma disciplina."""
    assert tokens("Noções de Direito Administrativo") == tokens("Direito Administrativo")


def test_identical_name_scores_the_maximum() -> None:
    score, reason = score_pair("Língua Portuguesa", "Língua Portuguesa")
    assert score == 1.0
    assert reason == MatchReason.EXACT


def test_same_subject_written_differently_is_still_strong() -> None:
    score, reason = score_pair("Noções de Direito Administrativo", "Direito Administrativo")
    assert score >= STRONG_SCORE
    assert reason == MatchReason.EXACT


def test_two_different_subjects_that_share_a_word_do_not_pass_as_equal() -> None:
    """O caso que justifica o módulo inteiro existir."""
    score, _ = score_pair("Direito Constitucional", "Direito Administrativo")
    assert score < STRONG_SCORE, "nunca pode parecer casamento certo"


def test_unrelated_names_score_zero() -> None:
    score, _ = score_pair("Informática", "Língua Portuguesa")
    assert score == 0.0


def test_suggestion_ranks_the_right_subject_first() -> None:
    resultado = suggest("Direito Administrativo", DISCIPLINAS)
    assert resultado.best is not None
    assert resultado.best.entry.public_id == "d2"
    assert resultado.best.is_strong


def test_suggestion_never_decides() -> None:
    resultado = suggest("Língua Portuguesa", DISCIPLINAS)
    assert resultado.best is not None and resultado.best.score == 1.0
    # Mesmo com nota máxima, o módulo não aplica nada.
    assert resultado.is_decided is False


def test_nothing_close_returns_an_empty_list() -> None:
    """Lista vazia é resposta: o catálogo não tem isso."""
    resultado = suggest("Medicina Veterinária", DISCIPLINAS)
    assert resultado.candidates == []
    assert resultado.best is None


def test_empty_query_returns_nothing_instead_of_everything() -> None:
    assert suggest("", DISCIPLINAS).candidates == []
    assert suggest("   ", DISCIPLINAS).candidates == []


def test_candidates_come_sorted_and_above_the_floor() -> None:
    resultado = suggest("Direito", DISCIPLINAS)
    notas = [item.score for item in resultado.candidates]
    assert notas == sorted(notas, reverse=True)
    assert all(nota >= MIN_SCORE for nota in notas)


def test_a_tie_is_broken_by_name_so_the_order_never_moves() -> None:
    """Duas leituras do mesmo catálogo precisam dar a mesma ordem."""
    empate = [
        CatalogEntry(public_id="b", name="Direito Penal"),
        CatalogEntry(public_id="a", name="Direito Civil"),
    ]
    primeira = [item.entry.public_id for item in suggest("Direito", empate).candidates]
    segunda = [
        item.entry.public_id for item in suggest("Direito", list(reversed(empate))).candidates
    ]
    assert primeira == segunda


def test_containment_is_weaker_than_equality() -> None:
    igual, _ = score_pair("Direito Penal", "Direito Penal")
    contido, motivo = score_pair("Direito Penal", "Direito Penal e Processual Penal")
    assert contido < igual
    assert motivo == MatchReason.CONTAINS


def test_each_candidate_explains_itself() -> None:
    """Quem revisa precisa saber por que aquilo foi sugerido."""
    resultado = suggest("Direito Administrativo", DISCIPLINAS)
    for candidato in resultado.candidates:
        assert candidato.reason_label
        assert candidato.reason_label != candidato.reason


def test_the_list_is_capped() -> None:
    muitos = [CatalogEntry(public_id=str(i), name=f"Direito {i}") for i in range(30)]
    assert len(suggest("Direito", muitos).candidates) <= 5


# --------------------------------------------------------------------------- #
# O que conta como UM assunto
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("rotulo", "nome"),
    [
        ("1 Princípios da administração pública", "Princípios da administração pública"),
        ("1.1 Crimes contra a pessoa", "Crimes contra a pessoa"),
        ("2.3.4 Lei de Execução Penal", "Lei de Execução Penal"),
        ("a) Ortografia oficial", "Ortografia oficial"),
        ("IV - Atos administrativos", "Atos administrativos"),
        ("  Crase.  ", "Crase"),
        ("Crase", "Crase"),
    ],
)
def test_a_numeracao_do_edital_sai_do_nome_do_assunto(rotulo: str, nome: str) -> None:
    """O número é daquele edital; o próximo escreve outro. Não é parte do nome."""
    assert clean_topic_label(rotulo) == nome


def test_numero_que_e_parte_do_nome_fica(rotulo: str = "Lei nº 8.112/1990") -> None:
    assert clean_topic_label(rotulo) == "Lei nº 8.112/1990"
    assert clean_topic_label("Art. 5 da Constituição Federal") == ("Art. 5 da Constituição Federal")


@pytest.mark.parametrize(
    "rotulo",
    [
        "Crase",
        "Emprego do sinal indicativo de crase",
        "Princípios aplicáveis ao direito penal",
        "Lei nº 8.112/1990",
        "Art. 5 da Constituição Federal",
        "Lei 8.666 de 1993 e suas alterações",
        "1 Princípios da administração pública",
    ],
)
def test_rotulo_que_e_um_assunto_passa(rotulo: str) -> None:
    assert topic_label_problem(rotulo) is None


def test_varios_assuntos_numa_linha_nao_e_um_assunto() -> None:
    """A assinatura de uma extração que não dividiu a lista."""
    assert (
        topic_label_problem("1 Compreensão de textos. 2 Ortografia oficial. 3 Crase")
        == TopicLabelProblem.SEVERAL_IN_ONE
    )
    assert (
        topic_label_problem("LÍNGUA PORTUGUESA: 1 Compreensão de textos. 2 Ortografia.")
        == TopicLabelProblem.SEVERAL_IN_ONE
    )


def test_rotulo_curto_ou_longo_demais_nao_e_um_assunto() -> None:
    assert topic_label_problem("1") == TopicLabelProblem.TOO_SHORT
    assert topic_label_problem("a)") == TopicLabelProblem.TOO_SHORT
    assert topic_label_problem("") == TopicLabelProblem.TOO_SHORT
    # Parágrafo inteiro do edital: seria um item de plano que cobre tudo.
    assert topic_label_problem("Direito " * 40) == TopicLabelProblem.TOO_LONG


def test_todo_motivo_de_recusa_tem_texto_para_a_tela() -> None:
    assert set(TOPIC_PROBLEM_LABEL) == {item.value for item in TopicLabelProblem}
    assert all(TOPIC_PROBLEM_LABEL[item].strip() for item in TopicLabelProblem)
