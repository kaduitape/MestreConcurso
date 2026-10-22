"""Árvore de conhecimento — o estado de cada ramo do edital.

Três testes pesam mais que os outros: o que cobra que **tópico sem vínculo não
entra na média da disciplina** (somar zero puxaria a disciplina para baixo como
se o candidato tivesse errado algo que ninguém mediu), o que cobra que **sem
amostra não há porcentagem**, e o que cobra que a **lacuna da plataforma não
aparece como tarefa do candidato** na ordem de atenção.
"""

from __future__ import annotations

from app.domain.game.knowledge_tree import (
    MIN_ANSWERS,
    Evidence,
    NodeState,
    SubjectInput,
    TopicInput,
    attention_order,
    build,
    summarize,
)


def _topic(**overrides: object) -> TopicInput:
    base: dict[str, object] = {
        "label": "Crase",
        "order": 0,
        "topic_id": 10,
        "evidence": Evidence(questions_available=30),
    }
    base.update(overrides)
    return TopicInput(**base)  # type: ignore[arg-type]


def _subject(**overrides: object) -> SubjectInput:
    base: dict[str, object] = {
        "label": "Língua Portuguesa",
        "order": 0,
        "subject_id": 1,
        "topics": (_topic(),),
    }
    base.update(overrides)
    return SubjectInput(**base)  # type: ignore[arg-type]


def _medido(answers: int, correct: int, **extra: object) -> Evidence:
    dados: dict[str, object] = {
        "answers": answers,
        "correct": correct,
        "questions_available": 50,
    }
    dados.update(extra)
    return Evidence(**dados)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Estados de um tópico
# --------------------------------------------------------------------------- #
def test_a_topic_the_platform_has_no_material_for_says_so() -> None:
    arvore = build([_subject(topics=(_topic(evidence=Evidence()),))])

    no = arvore[0].topics[0]
    assert no.state is NodeState.NO_MATERIAL
    assert "ainda não tem questão nem material" in no.reason


def test_a_topic_with_material_and_no_activity_is_not_started() -> None:
    arvore = build([_subject()])

    assert arvore[0].topics[0].state is NodeState.NOT_STARTED


def test_without_enough_answers_there_is_no_accuracy_only_what_is_missing() -> None:
    """O teste que pesa: taxa sobre três questões oscila 33 pontos por resposta."""
    arvore = build([_subject(topics=(_topic(evidence=_medido(3, 3)),))])

    no = arvore[0].topics[0]
    assert no.state is NodeState.IN_PROGRESS
    assert no.accuracy is None
    assert f"faltam {MIN_ANSWERS - 3}" in no.reason


def test_with_enough_answers_the_accuracy_appears_with_the_sample_size() -> None:
    arvore = build([_subject(topics=(_topic(evidence=_medido(20, 12)),))])

    no = arvore[0].topics[0]
    assert no.state is NodeState.MEASURED
    assert no.accuracy == 0.6
    assert "60% de acerto em 20 respostas" in no.reason


def test_high_accuracy_with_sample_is_mastered() -> None:
    arvore = build([_subject(topics=(_topic(evidence=_medido(20, 16, days_since_activity=2)),))])

    assert arvore[0].topics[0].state is NodeState.MASTERED


def test_a_mastered_topic_going_cold_asks_for_review() -> None:
    arvore = build([_subject(topics=(_topic(evidence=_medido(20, 18, days_since_activity=40)),))])

    no = arvore[0].topics[0]
    assert no.state is NodeState.NEEDS_REVIEW
    assert "40 dias sem nenhuma atividade" in no.reason


# --------------------------------------------------------------------------- #
# Tópico sem vínculo
# --------------------------------------------------------------------------- #
def test_an_unlinked_topic_is_declared_not_hidden() -> None:
    arvore = build([_subject(topics=(_topic(topic_id=None, evidence=Evidence()),))])

    no = arvore[0].topics[0]
    assert no.state is NodeState.NOT_LINKED
    assert "não foi vinculado ao catálogo" in no.reason


def test_an_unlinked_topic_does_not_enter_the_subject_average() -> None:
    """O teste que pesa mais.

    Somar um tópico não medido como zero acerto faria a disciplina parecer pior
    do que o candidato — atribuindo a ele uma falha que é de cadastro.
    """
    disciplina = _subject(
        topics=(
            _topic(label="Crase", evidence=_medido(20, 18, days_since_activity=1)),
            _topic(label="Regência", order=1, topic_id=None, evidence=Evidence()),
        )
    )
    arvore = build([disciplina])

    assert arvore[0].evidence.answers == 20
    assert arvore[0].accuracy == 0.9
    assert arvore[0].state is NodeState.MASTERED


# --------------------------------------------------------------------------- #
# A disciplina é a soma dos tópicos
# --------------------------------------------------------------------------- #
def test_the_subject_has_no_measurement_of_its_own() -> None:
    disciplina = _subject(
        topics=(
            _topic(label="Crase", evidence=_medido(10, 8, days_since_activity=3)),
            _topic(label="Vírgula", order=1, evidence=_medido(10, 4, days_since_activity=9)),
        )
    )
    arvore = build([disciplina])

    # 20 respostas somadas, 12 acertos: 60%. Nenhum dos dois tópicos tinha
    # amostra para exibir taxa; a disciplina tem.
    assert arvore[0].evidence.answers == 20
    assert arvore[0].accuracy == 0.6
    assert [item.accuracy for item in arvore[0].topics] == [None, None]
    # A atividade mais recente entre os filhos é a que vale.
    assert arvore[0].evidence.days_since_activity == 3


def test_the_tree_keeps_the_order_the_notice_wrote() -> None:
    arvore = build(
        [
            SubjectInput(label="Direito", order=1, topics=()),
            SubjectInput(label="Português", order=0, topics=()),
        ]
    )

    assert [item.label for item in arvore] == ["Português", "Direito"]


def test_no_state_locks_content() -> None:
    """Nenhum estado da árvore tranca matéria — nem existe um para isso."""
    assert "LOCKED" not in {item.value for item in NodeState}


# --------------------------------------------------------------------------- #
# Resumo e ordem de atenção
# --------------------------------------------------------------------------- #
def test_the_summary_keeps_platform_gaps_apart_from_performance() -> None:
    arvore = build(
        [
            _subject(
                topics=(
                    _topic(label="Crase", evidence=_medido(20, 18, days_since_activity=1)),
                    _topic(label="Vírgula", order=1, evidence=_medido(20, 8)),
                    _topic(label="Regência", order=2, topic_id=None, evidence=Evidence()),
                    _topic(label="Fonologia", order=3, evidence=Evidence()),
                )
            )
        ]
    )
    resumo = summarize(arvore)

    assert resumo.topics == 4
    assert resumo.measured == 2
    assert resumo.mastered == 1
    assert resumo.not_linked == 1
    assert resumo.no_material == 1
    # Dois dos quatro tópicos a plataforma não consegue medir.
    assert resumo.measurable == 2


def test_attention_puts_review_first_then_the_worst_accuracy() -> None:
    arvore = build(
        [
            _subject(
                topics=(
                    _topic(label="Ruim", evidence=_medido(20, 8)),
                    _topic(label="Pior", order=1, evidence=_medido(20, 4)),
                    _topic(
                        label="Esfriou",
                        order=2,
                        evidence=_medido(20, 19, days_since_activity=60),
                    ),
                    _topic(label="Começando", order=3, evidence=_medido(4, 2)),
                )
            )
        ]
    )

    assert [item.label for item in attention_order(arvore)] == [
        "Esfriou",
        "Pior",
        "Ruim",
        "Começando",
    ]


def test_platform_gaps_never_appear_as_the_candidates_next_task() -> None:
    """O terceiro teste que pesa.

    Tópico sem vínculo e tópico sem material são providência de quem cadastra
    conteúdo. Colocá-los na fila de atenção do candidato cobraria dele um
    trabalho que não é dele.
    """
    arvore = build(
        [
            _subject(
                topics=(
                    _topic(label="Sem vínculo", topic_id=None, evidence=Evidence()),
                    _topic(label="Sem material", order=1, evidence=Evidence()),
                )
            )
        ]
    )

    assert attention_order(arvore) == []
