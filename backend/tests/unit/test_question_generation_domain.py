"""As conferências que uma questão gerada enfrenta **antes** de existir no banco.

O teste que sustenta esta parte é o da procedência fabricada: uma questão
inédita que se apresenta como "(CESPE/2023)" mentiria para o candidato sobre o
que ele está treinando, e revisão humana por amostragem não pega isso de forma
confiável. Por isso ela morre na origem.

O segundo em importância é o inverso do que o nome "gabarito validado" sugere:
estes testes provam o que o módulo **consegue** conferir, e nenhum deles prova
que o gabarito está certo — porque isso nenhum código confere.
"""

from __future__ import annotations

import dataclasses

from app.domain.question_generation import (
    MAX_ALTERNATIVES,
    MIN_STATEMENT_CHARS,
    DraftAlternative,
    DraftQuestion,
    RejectionReason,
    summarize,
    validate,
)

MATERIAL = (
    "A crase é a contração da preposição A com o artigo feminino A. "
    "Não se usa crase antes de palavra masculina, antes de verbo e antes da "
    "maioria dos pronomes. Diante de nome de lugar, o teste é voltar de."
)

BANCAS = ("Cebraspe", "CESPE", "FGV", "Fundação Getulio Vargas")


def _questao(**troca: object) -> DraftQuestion:
    base = DraftQuestion(
        statement=(
            "Assinale a alternativa que define corretamente o fenômeno da crase "
            "na língua portuguesa."
        ),
        alternatives=(
            DraftAlternative("A", "É a contração de duas preposições iguais.", False, "Não é."),
            DraftAlternative(
                "B",
                "É a contração da preposição A com o artigo feminino A.",
                True,
                "É a definição do material.",
            ),
            DraftAlternative("C", "É o acento usado antes de verbo.", False, "O material nega."),
            DraftAlternative("D", "É obrigatória antes de pronomes.", False, "O material nega."),
        ),
        explanation="A alternativa B repete a definição que o material traz.",
        quote="A crase é a contração da preposição A com o artigo feminino A",
        difficulty="MEDIUM",
    )
    return dataclasses.replace(base, **troca)  # type: ignore[arg-type]


def test_a_well_formed_question_backed_by_the_material_is_accepted() -> None:
    verdict = validate(_questao(), material=MATERIAL, board_names=BANCAS)

    assert verdict.accepted
    assert verdict.rejections == ()
    assert verdict.summary == ""


def test_a_question_that_dresses_up_as_a_board_question_dies_at_origin() -> None:
    """O defeito mais grave possível aqui: questão inédita vestida de oficial."""
    com_banca = _questao(
        statement="(CESPE/2023) Assinale a alternativa que define o fenômeno da crase."
    )

    verdict = validate(com_banca, material=MATERIAL, board_names=BANCAS)

    assert RejectionReason.FABRICATED_PROVENANCE in verdict.rejections
    assert "banca" in verdict.summary


def test_a_statement_opening_with_parentheses_and_a_year_is_rejected() -> None:
    """O formato clássico de atribuição de prova cai sem depender do catálogo.

    Numa instalação nova não há banca cadastrada — e é justamente ali que o
    enunciado com cara de prova passaria sem ninguém notar.
    """
    atribuida = _questao(
        statement="(CESPE/2023) Assinale a alternativa que define o fenômeno da crase."
    )

    verdict = validate(atribuida, material=MATERIAL, board_names=())

    assert RejectionReason.FABRICATED_PROVENANCE in verdict.rejections


def test_a_normative_reference_in_parentheses_keeps_passing() -> None:
    """ "(Lei nº 8.112/1990)" é citação legítima, não procedência inventada."""
    com_lei = _questao(
        statement=(
            "(Lei nº 8.112/1990) Assinale a alternativa que define corretamente "
            "o fenômeno da crase na língua portuguesa."
        )
    )

    verdict = validate(com_lei, material=MATERIAL, board_names=BANCAS)

    assert RejectionReason.FABRICATED_PROVENANCE not in verdict.rejections


def test_the_board_list_comes_from_outside_so_the_rule_does_not_age() -> None:
    """Sem a banca no catálogo, o ano sozinho não condena o enunciado.

    É deliberado: inventar aqui uma lista fixa de bancas faria a regra
    envelhecer no primeiro concurso novo, e barrar todo enunciado com ano
    jogaria fora questão legítima sobre a Constituição de 1988.
    """
    com_banca = _questao(
        statement=(
            "Assinale, como pediu a prova da Cebraspe de 2023, a alternativa que "
            "define corretamente o fenômeno da crase."
        )
    )

    assert validate(com_banca, material=MATERIAL, board_names=()).accepted
    assert not validate(com_banca, material=MATERIAL, board_names=BANCAS).accepted


def test_a_phrase_claiming_a_past_exam_is_enough_by_itself() -> None:
    adaptada = _questao(
        statement=(
            "Questão adaptada de prova anterior: assinale a alternativa que "
            "define o fenômeno da crase."
        )
    )

    verdict = validate(adaptada, material=MATERIAL, board_names=())

    assert RejectionReason.FABRICATED_PROVENANCE in verdict.rejections


def test_the_answer_key_needs_a_literal_quote_from_the_material() -> None:
    inventada = _questao(quote="a crase foi abolida pela reforma ortográfica de 2009")

    verdict = validate(inventada, material=MATERIAL, board_names=BANCAS)

    assert RejectionReason.QUOTE_NOT_IN_MATERIAL in verdict.rejections


def test_a_quote_too_short_does_not_sustain_anything() -> None:
    verdict = validate(_questao(quote="crase"), material=MATERIAL, board_names=BANCAS)

    assert RejectionReason.QUOTE_TOO_SHORT in verdict.rejections
    # Curta demais não é conferida contra o material: seria casar por acaso.
    assert RejectionReason.QUOTE_NOT_IN_MATERIAL not in verdict.rejections


def test_two_answer_keys_or_none_is_rejected() -> None:
    sem_gabarito = _questao(
        alternatives=tuple(
            dataclasses.replace(item, is_correct=False) for item in _questao().alternatives
        )
    )
    duas = _questao(
        alternatives=tuple(
            dataclasses.replace(item, is_correct=True) for item in _questao().alternatives
        )
    )

    assert RejectionReason.NO_SINGLE_ANSWER in validate(sem_gabarito, material=MATERIAL).rejections
    assert RejectionReason.NO_SINGLE_ANSWER in validate(duas, material=MATERIAL).rejections


def test_repeated_or_empty_alternatives_are_rejected() -> None:
    originais = _questao().alternatives
    repetida = _questao(
        alternatives=(
            originais[0],
            originais[1],
            dataclasses.replace(originais[2], content=originais[0].content),
            originais[3],
        )
    )
    vazia = _questao(
        alternatives=(
            originais[0],
            originais[1],
            dataclasses.replace(originais[2], content="   "),
            originais[3],
        )
    )

    assert RejectionReason.ALTERNATIVE_REPEATED in validate(repetida, material=MATERIAL).rejections
    assert RejectionReason.ALTERNATIVE_EMPTY in validate(vazia, material=MATERIAL).rejections


def test_all_or_none_of_the_above_is_rejected() -> None:
    originais = _questao().alternatives
    com_proibida = _questao(
        alternatives=(
            originais[0],
            originais[1],
            originais[2],
            dataclasses.replace(originais[3], content="Nenhuma das anteriores."),
        )
    )

    verdict = validate(com_proibida, material=MATERIAL)

    assert RejectionReason.FORBIDDEN_ALTERNATIVE in verdict.rejections


def test_a_question_needs_exam_shaped_alternatives() -> None:
    originais = _questao().alternatives
    curta = _questao(alternatives=originais[:2])
    longa = _questao(
        alternatives=(
            *originais,
            DraftAlternative("E", "Alternativa extra um.", False, "erra"),
            DraftAlternative("F", "Alternativa extra dois.", False, "erra"),
        )
    )

    assert RejectionReason.ALTERNATIVE_COUNT in validate(curta, material=MATERIAL).rejections
    assert len(longa.alternatives) > MAX_ALTERNATIVES
    assert RejectionReason.ALTERNATIVE_COUNT in validate(longa, material=MATERIAL).rejections


def test_letters_must_be_in_order_without_gaps() -> None:
    originais = _questao().alternatives
    trocada = _questao(
        alternatives=(
            dataclasses.replace(originais[0], letter="B"),
            dataclasses.replace(originais[1], letter="A"),
            originais[2],
            originais[3],
        )
    )

    assert RejectionReason.LETTERS_OUT_OF_ORDER in validate(trocada, material=MATERIAL).rejections


def test_the_wrong_alternatives_must_say_why_they_are_wrong() -> None:
    originais = _questao().alternatives
    sem_motivo = _questao(
        alternatives=(
            dataclasses.replace(originais[0], feedback=None),
            originais[1],
            originais[2],
            originais[3],
        )
    )

    verdict = validate(sem_motivo, material=MATERIAL)

    assert RejectionReason.WRONG_WITHOUT_FEEDBACK in verdict.rejections


def test_a_key_without_justification_is_rejected() -> None:
    verdict = validate(_questao(explanation="   "), material=MATERIAL)

    assert RejectionReason.EXPLANATION_MISSING in verdict.rejections


def test_a_short_answer_in_the_statement_is_not_a_leak() -> None:
    """ "Dez dias" no enunciado e na alternativa é coincidência, não entrega.

    Exigir ausência total do texto da correta descartaria questão legítima de
    alternativa curta — e descarte por coincidência de palavra é pior que não
    checar, porque parece rigor.
    """
    originais = _questao().alternatives
    curta = _questao(
        statement=(
            "Sobre o prazo de dez dias previsto no material, assinale a "
            "alternativa correta quanto à sua contagem."
        ),
        alternatives=(
            originais[0],
            dataclasses.replace(originais[1], content="Dez dias."),
            originais[2],
            originais[3],
        ),
    )

    verdict = validate(curta, material=MATERIAL)

    assert RejectionReason.ANSWER_IN_STATEMENT not in verdict.rejections


def test_a_statement_that_gives_the_answer_away_is_rejected() -> None:
    entregue = _questao(
        statement=(
            "Sabendo que é a contração da preposição a com o artigo feminino a, "
            "assinale a definição correta da crase."
        )
    )

    verdict = validate(entregue, material=MATERIAL)

    assert RejectionReason.ANSWER_IN_STATEMENT in verdict.rejections


def test_a_statement_shorter_than_the_auditor_minimum_is_rejected() -> None:
    curto = _questao(statement="O que é crase?")

    verdict = validate(curto, material=MATERIAL)

    assert len(curto.statement) < MIN_STATEMENT_CHARS
    assert RejectionReason.STATEMENT_TOO_SHORT in verdict.rejections


def test_the_reasons_are_counted_by_kind() -> None:
    """A tela precisa dizer *o que* derrubou, não só quantos caíram."""
    vereditos = [
        validate(_questao(), material=MATERIAL),
        validate(_questao(quote="nada disso está no material aqui"), material=MATERIAL),
        validate(_questao(quote="outra citação que também não existe"), material=MATERIAL),
        validate(_questao(explanation=""), material=MATERIAL),
    ]

    contagem = summarize(vereditos)

    assert contagem[RejectionReason.QUOTE_NOT_IN_MATERIAL] == 2
    assert contagem[RejectionReason.EXPLANATION_MISSING] == 1
    assert len([item for item in vereditos if item.accepted]) == 1


def test_every_rejection_reason_has_a_sentence_for_the_screen() -> None:
    """Motivo sem texto viraria código cru na tela de quem cura."""
    from app.domain.question_generation import REASON_LABEL

    assert {item.value for item in RejectionReason} == set(REASON_LABEL)
    assert all(texto.strip() for texto in REASON_LABEL.values())
