"""Narração das aulas — como o roteiro vira voz.

A leitura de um sintetizador de navegador é plana porque ele recebe um bloco de
texto e nada mais. Aqui o roteiro é quebrado em **trechos** e cada trecho leva
uma **direção de cena**: o texto que diz como ler, não o que ler.

Tudo o que a direção usa já estava no roteiro — o tipo da cena, a emoção do
personagem, as palavras em destaque. Nada é inventado sobre o conteúdo; o que se
acrescenta é entonação, que é forma, não informação.

A quebra em trechos tem uma segunda função, menos óbvia: ela permite acender no
texto exatamente a frase que está tocando. Um bloco único só daria para estimar
onde a voz está, e destaque que erra o lugar atrapalha mais do que ajuda.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum

#: Abaixo disto não vale a pena um arquivo próprio: a pausa entre dois trechos
#: ficaria mais longa que o trecho.
MIN_SEGMENT_CHARS = 24

#: Acima disto a frase é partida de novo, na vírgula mais próxima do meio.
#:
#: 180 caracteres são uns doze segundos de fala. Além disso o destaque fica
#: parado tempo demais numa frase só, e a leitura volta a soar como um bloco —
#: que é exatamente o que a quebra existe para evitar.
MAX_SEGMENT_CHARS = 180


class SceneKind(StrEnum):
    """Os tipos de cena que o roteiro produz."""

    INTRO = "intro"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    QUESTION = "question"
    SUMMARY = "summary"
    CLOSING = "closing"


#: Como ler cada tipo de cena. A frase é dita ao modelo de voz, em português,
#: porque é assim que ele entende direção.
SCENE_DIRECTION: dict[str, str] = {
    SceneKind.INTRO: (
        "Abertura: convide o ouvinte para a missão, com energia contida e um "
        "leve ar de mistério, como quem abre um portão antigo."
    ),
    SceneKind.EXPLANATION: (
        "Explicação: ritmo pausado e seguro, de mestre que ensina. Separe as "
        "ideias com respiros curtos."
    ),
    SceneKind.EXAMPLE: (
        "Exemplo: tom mais leve e concreto, quase coloquial, como quem mostra a coisa na mão."
    ),
    SceneKind.QUESTION: (
        "Desafio: proponha a pergunta e suspenda a voz no fim, deixando o "
        "silêncio pesar antes da resposta."
    ),
    SceneKind.SUMMARY: (
        "Fechamento de ideia: voz firme e conclusiva, marcando o que precisa ficar na memória."
    ),
    SceneKind.CLOSING: (
        "Despedida: tom caloroso e encorajador, sem pressa, como quem entrega "
        "uma espada ao aprendiz."
    ),
}

#: A emoção vem do próprio roteiro (``character.emotion``).
EMOTION_DIRECTION: dict[str, str] = {
    "confident": "Confiante, sem arrogância.",
    "serious": "Sério e grave.",
    "encouraging": "Encorajador, próximo.",
    "curious": "Curioso, como quem convida a pensar junto.",
    "warning": "De alerta, atenção redobrada na voz.",
    "happy": "Satisfeito, com um sorriso audível.",
}

#: A moldura que dá o sotaque da plataforma. Medieval no porte, não na fantasia:
#: um mestre de armas que ensina português, não um bardo de taverna.
BASE_DIRECTION = (
    "Você é {character}, mestre de uma ordem antiga que ensina para concurso "
    "público. Fale português do Brasil com dicção clara e nobre, voz madura e "
    "grave, ritmo de quem conta uma história — nunca de locutor de propaganda "
    "nem de leitor automático. Sem sotaque estrangeiro e sem arcaísmo forçado: "
    "o conteúdo é técnico e precisa ser entendido de primeira."
)


@dataclass(frozen=True, slots=True)
class NarrationSegment:
    """Um trecho de fala, com a direção de como lê-lo."""

    index: int
    text: str
    direction: str
    #: Identifica o conteúdo + a voz + o modelo. Texto igual, áudio reusado.
    checksum: str
    #: Posição do trecho dentro do texto da cena, para acender a frase certa.
    offset: int
    length: int


@dataclass(frozen=True, slots=True)
class SceneNarration:
    scene_id: int
    text: str
    segments: list[NarrationSegment] = field(default_factory=list)


def _sentences(text: str) -> list[str]:
    """Divide em frases pela pontuação, preservando o sinal que as fecha."""
    parts = re.split(r"(?<=[.!?…:])\s+", text.strip())
    return [part.strip() for part in parts if part.strip()]


def _split_long(sentence: str) -> list[str]:
    """Parte uma frase comprida na vírgula mais próxima do meio."""
    if len(sentence) <= MAX_SEGMENT_CHARS:
        return [sentence]

    middle = len(sentence) // 2
    commas = [match.start() for match in re.finditer(r",", sentence)]
    if not commas:
        return [sentence]

    cut = min(commas, key=lambda position: abs(position - middle))
    head, tail = sentence[: cut + 1].strip(), sentence[cut + 1 :].strip()
    if not head or not tail:
        return [sentence]
    return _split_long(head) + _split_long(tail)


def split_segments(text: str) -> list[str]:
    """Quebra o texto em trechos de leitura.

    Frases muito curtas são coladas na seguinte: um "Pois bem." sozinho vira um
    arquivo de áudio cuja pausa de carregamento dura mais que a própria palavra.
    """
    pieces: list[str] = []
    for sentence in _sentences(text):
        pieces.extend(_split_long(sentence))

    merged: list[str] = []
    for piece in pieces:
        if merged and len(merged[-1]) < MIN_SEGMENT_CHARS:
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return merged


def build_direction(
    *,
    character: str,
    scene_type: str,
    emotion: str | None,
    emphasis: list[str],
    is_first: bool,
    is_last: bool,
) -> str:
    """Monta a direção de cena a partir do que o roteiro já declarava."""
    parts = [BASE_DIRECTION.format(character=character or "o Mestre")]

    direction = SCENE_DIRECTION.get(scene_type)
    if direction:
        parts.append(direction)

    mood = EMOTION_DIRECTION.get((emotion or "").lower())
    if mood:
        parts.append(mood)

    # As palavras em destaque são as que o roteiro marcou para fixar. Pedir
    # ênfase nelas é usar o roteiro, não adivinhar o que importa.
    marked = [item.strip() for item in emphasis if item and item.strip()][:6]
    if marked:
        termos = ", ".join(f"'{item}'" for item in marked)
        parts.append(
            f"Dê peso e uma pausa curta antes de: {termos}. São os termos que "
            "precisam ficar na memória."
        )

    if is_first:
        parts.append("Este é o primeiro trecho da cena: entre com presença.")
    if is_last:
        parts.append("Este é o último trecho da cena: feche a frase, não a deixe no ar.")

    return " ".join(parts)


def checksum_of(*, text: str, direction: str, voice: str, model: str) -> str:
    """Identidade do áudio.

    Entra tudo o que muda o som: o texto, a direção, a voz e o modelo. Assim
    reescrever uma vírgula gera áudio novo, e reabrir a mesma aula não gera
    nada — o token é pago uma vez.
    """
    payload = "\u001f".join([text, direction, voice, model])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def narrate_scene(
    scene: dict[str, object],
    *,
    character: str,
    voice: str,
    model: str,
) -> SceneNarration:
    """Transforma uma cena do roteiro nos trechos que serão falados."""
    raw_id = scene.get("id")
    scene_id = int(raw_id) if isinstance(raw_id, int | str) and str(raw_id).isdigit() else 0
    raw = str(scene.get("narration") or scene.get("dialogue") or "").strip()
    if not raw:
        return SceneNarration(scene_id=scene_id, text="")

    scene_type = str(scene.get("type") or SceneKind.EXPLANATION).lower()
    character_data = scene.get("character")
    emotion = str(character_data.get("emotion") or "") if isinstance(character_data, dict) else ""
    emphasis_raw = scene.get("emphasis")
    emphasis = [str(item) for item in emphasis_raw] if isinstance(emphasis_raw, list) else []

    pieces = split_segments(raw)
    segments: list[NarrationSegment] = []
    cursor = 0
    for position, piece in enumerate(pieces):
        offset = raw.find(piece, cursor)
        if offset < 0:
            # O trecho foi recomposto (frases curtas coladas): a posição exata
            # se perde, e preferimos não acender nada a acender o lugar errado.
            offset = cursor
        cursor = offset + len(piece)

        direction = build_direction(
            character=character,
            scene_type=scene_type,
            emotion=emotion,
            emphasis=emphasis,
            is_first=position == 0,
            is_last=position == len(pieces) - 1,
        )
        segments.append(
            NarrationSegment(
                index=position,
                text=piece,
                direction=direction,
                checksum=checksum_of(text=piece, direction=direction, voice=voice, model=model),
                offset=offset,
                length=len(piece),
            )
        )

    return SceneNarration(scene_id=scene_id, text=raw, segments=segments)


def narrate_script(
    script: dict[str, object],
    *,
    character: str,
    voice: str,
    model: str,
) -> list[SceneNarration]:
    """A aula inteira, cena a cena. Cenas sem fala saem da lista."""
    scenes_raw = script.get("scenes")
    scenes = scenes_raw if isinstance(scenes_raw, list) else []
    narrated = [
        narrate_scene(scene, character=character, voice=voice, model=model)
        for scene in scenes
        if isinstance(scene, dict)
    ]
    return [item for item in narrated if item.segments]
