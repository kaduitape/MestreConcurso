"""A aula-modelo precisa ser uma aula de verdade.

Ela vai publicada para quem estuda no primeiro seed, então aqui se cobra o que
ninguém veria quebrado só olhando a tela: que o roteiro passa pela mesma
validação das aulas geradas, que a pergunta tem resposta dentro da lista, e que
cada termo marcado como conceito existe literalmente no texto da cena — um
destaque que aponta para o vazio não acende nada no player.
"""

from __future__ import annotations

import copy

from app.domain.training.example import (
    EXAMPLE_PUBLIC_ID,
    EXAMPLE_SCRIPT,
    EXAMPLE_TITLE,
)
from app.domain.training.narration import SceneKind, split_segments
from app.services.training import _validate_script

SCENES = EXAMPLE_SCRIPT["scenes"]


def test_the_example_passes_the_same_validation_as_a_generated_script() -> None:
    validated = _validate_script(copy.deepcopy(EXAMPLE_SCRIPT))
    assert len(validated["scenes"]) == len(SCENES)
    assert validated["objectives"], "uma aula sem objetivo declarado não é aula"


def test_the_public_id_fits_the_column() -> None:
    # A coluna aceita 26 caracteres. Um identificador maior quebraria o seed
    # direto no banco, longe de qualquer teste de tela.
    assert len(EXAMPLE_PUBLIC_ID) <= 26
    assert EXAMPLE_TITLE


def test_every_scene_declares_what_the_player_reads() -> None:
    for scene in SCENES:
        assert scene["type"] in set(SceneKind), scene["type"]
        assert scene["narration"].strip(), scene["id"]
        # O player lê `dialogue`; a narração fala `narration`. Divergir os dois
        # faria a voz dizer uma coisa e a tela mostrar outra.
        assert scene["dialogue"] == scene["narration"], scene["id"]
        assert scene["duration"] > 0


def test_the_scene_order_is_the_one_the_lesson_promises() -> None:
    kinds = [scene["type"] for scene in SCENES]
    assert kinds[0] == SceneKind.INTRO
    assert kinds[-1] == SceneKind.CLOSING
    assert SceneKind.QUESTION in kinds
    assert SceneKind.EXAMPLE in kinds
    assert [scene["id"] for scene in SCENES] == list(range(1, len(SCENES) + 1))


def test_the_highlighted_terms_exist_in_the_scene_text() -> None:
    """Conceito marcado que não está no texto não acende nada.

    A comparação ignora caixa porque é assim que o player procura o termo —
    o teste espelha o destaque de verdade, não uma regra mais dura que ele.
    """
    for scene in SCENES:
        texto = scene["dialogue"].lower()
        for term in scene["keywords"] + scene["emphasis"]:
            assert term.lower() in texto, f"cena {scene['id']}: {term!r}"


def test_the_question_has_an_answer_inside_the_list() -> None:
    question = next(scene for scene in SCENES if scene["type"] == SceneKind.QUESTION)
    options = question["options"]
    assert len(options) == 4
    assert 0 <= question["correct_option"] < len(options)
    assert len(set(options)) == len(options), "alternativa repetida não mede nada"
    # E o retorno explica a escolha, em vez de só dizer "correto".
    assert len(question["feedback"]) > 120


def test_the_narration_breaks_into_segments_the_player_can_follow() -> None:
    """Nenhum pedaço do texto se perde na quebra em trechos de áudio."""
    for scene in SCENES:
        segments = split_segments(scene["narration"])
        assert segments, scene["id"]
        for segment in segments:
            assert segment in scene["narration"], scene["id"]
        # Cena longa demais num trecho só voltaria a soar como bloco lido.
        assert max(len(segment) for segment in segments) <= 180, scene["id"]
