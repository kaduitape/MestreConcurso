"""Narração do Estúdio — como o roteiro vira voz.

O que estes testes protegem é a fronteira: a IA escolhe **entonação**, nunca
informação. O texto falado é exatamente o que o roteiro aprovado trazia, e a
direção de cena é montada a partir dos campos que o roteiro já declarava.
"""

from __future__ import annotations

from app.domain.training.narration import (
    MAX_SEGMENT_CHARS,
    MIN_SEGMENT_CHARS,
    build_direction,
    checksum_of,
    narrate_scene,
    narrate_script,
    split_segments,
)

CENA = {
    "id": 1,
    "type": "explanation",
    "narration": (
        "Saudações, aprendizes! Hoje vamos desvendar o mistério da crase. "
        "A crase é a fusão da preposição 'a' com o artigo definido 'a'."
    ),
    "emphasis": ["crase", "preposição", "artigo definido"],
    "character": {"emotion": "confident"},
}


class TestSegments:
    def test_o_texto_e_quebrado_em_frases(self):
        trechos = split_segments(CENA["narration"])
        assert len(trechos) == 2
        assert trechos[0].startswith("Saudações")
        assert trechos[1].startswith("A crase")

    def test_nada_do_texto_se_perde_na_quebra(self):
        original = "".join(CENA["narration"].split())
        recomposto = "".join("".join(split_segments(CENA["narration"])).split())
        assert recomposto == original

    def test_frase_curta_demais_gruda_na_seguinte(self):
        """Um trecho de duas palavras viraria um arquivo cuja pausa de
        carregamento dura mais que a própria palavra."""
        trechos = split_segments("Pois bem. Agora vamos ao que realmente importa nesta aula.")
        assert len(trechos) == 1

    def test_frase_comprida_e_partida_na_virgula(self):
        longa = (
            "A crase ocorre diante de palavras femininas determinadas por artigo, "
            "diante de locuções adverbiais, prepositivas e conjuntivas femininas, "
            "diante dos pronomes demonstrativos aquele, aquela e aquilo, "
            "e também nas locuções que pedem artigo definido feminino antes do termo."
        )
        assert len(longa) > MAX_SEGMENT_CHARS
        trechos = split_segments(longa)
        assert len(trechos) > 1
        assert all(len(item) <= MAX_SEGMENT_CHARS for item in trechos)

    def test_texto_vazio_nao_vira_trecho(self):
        assert split_segments("   ") == []

    def test_o_minimo_e_menor_que_o_maximo(self):
        assert MIN_SEGMENT_CHARS < MAX_SEGMENT_CHARS


class TestDirection:
    def _direcao(self, **kwargs):
        base = {
            "character": "Mestre Arcanus",
            "scene_type": "explanation",
            "emotion": "confident",
            "emphasis": [],
            "is_first": False,
            "is_last": False,
        }
        base.update(kwargs)
        return build_direction(**base)  # type: ignore[arg-type]

    def test_a_direcao_nomeia_o_personagem_do_roteiro(self):
        assert "Mestre Arcanus" in self._direcao()

    def test_cada_tipo_de_cena_pede_uma_leitura_diferente(self):
        intro = self._direcao(scene_type="intro")
        pergunta = self._direcao(scene_type="question")
        assert intro != pergunta

    def test_a_emocao_do_roteiro_entra_na_direcao(self):
        assert self._direcao(emotion="warning") != self._direcao(emotion="happy")

    def test_os_termos_em_destaque_viram_enfase(self):
        direcao = self._direcao(emphasis=["crase", "preposição"])
        assert "'crase'" in direcao
        assert "'preposição'" in direcao

    def test_destaque_vazio_nao_vira_pedido_em_branco(self):
        assert "peso e uma pausa" not in self._direcao(emphasis=["", "   "])

    def test_o_primeiro_e_o_ultimo_trecho_sao_lidos_diferente(self):
        assert self._direcao(is_first=True) != self._direcao(is_last=True)

    def test_a_direcao_pede_dicacao_clara_antes_de_fantasia(self):
        """A regra de ouro vale aqui também: é plataforma de concurso."""
        direcao = self._direcao()
        assert "arcaísmo forçado" in direcao
        assert "entendido de primeira" in direcao


class TestChecksum:
    def test_o_mesmo_trecho_na_mesma_voz_tem_a_mesma_identidade(self):
        a = checksum_of(text="oi", direction="d", voice="onyx", model="tts")
        b = checksum_of(text="oi", direction="d", voice="onyx", model="tts")
        assert a == b

    def test_mudar_o_texto_muda_o_audio(self):
        a = checksum_of(text="oi", direction="d", voice="onyx", model="tts")
        b = checksum_of(text="oi.", direction="d", voice="onyx", model="tts")
        assert a != b

    def test_mudar_a_voz_muda_o_audio(self):
        a = checksum_of(text="oi", direction="d", voice="onyx", model="tts")
        b = checksum_of(text="oi", direction="d", voice="fable", model="tts")
        assert a != b

    def test_mudar_a_direcao_muda_o_audio(self):
        """A direção muda o som, então precisa mudar a identidade."""
        a = checksum_of(text="oi", direction="sério", voice="onyx", model="tts")
        b = checksum_of(text="oi", direction="alegre", voice="onyx", model="tts")
        assert a != b


class TestScene:
    def _narrada(self, scene=None):
        return narrate_scene(
            scene or CENA, character="Mestre Arcanus", voice="onyx", model="gpt-4o-mini-tts"
        )

    def test_a_cena_vira_trechos_com_direcao(self):
        narrada = self._narrada()
        assert narrada.scene_id == 1
        assert len(narrada.segments) == 2
        assert all(item.direction for item in narrada.segments)

    def test_o_texto_falado_e_o_texto_do_roteiro(self):
        """A IA recebe o que a pessoa aprovou — ela não reescreve conteúdo."""
        narrada = self._narrada()
        falado = " ".join(item.text for item in narrada.segments)
        assert "".join(falado.split()) == "".join(CENA["narration"].split())

    def test_o_deslocamento_aponta_para_o_texto_da_cena(self):
        narrada = self._narrada()
        for segmento in narrada.segments:
            recorte = narrada.text[segmento.offset : segmento.offset + segmento.length]
            assert recorte == segmento.text

    def test_cena_sem_fala_nao_vira_narracao(self):
        assert self._narrada({"id": 9, "narration": "", "dialogue": ""}).segments == []

    def test_o_dialogo_serve_quando_nao_ha_narracao(self):
        narrada = self._narrada({"id": 2, "dialogue": "Vamos começar a jornada agora mesmo."})
        assert narrada.segments
        assert "jornada" in narrada.segments[0].text


class TestScript:
    def test_o_roteiro_inteiro_vira_cenas_narradas(self):
        script = {
            "scenes": [
                CENA,
                {"id": 2, "type": "question", "narration": "Qual alternativa está correta?"},
                {"id": 3, "type": "closing", "narration": ""},
            ]
        }
        cenas = narrate_script(
            script, character="Mestre Arcanus", voice="onyx", model="gpt-4o-mini-tts"
        )
        assert [item.scene_id for item in cenas] == [1, 2]

    def test_roteiro_sem_cenas_nao_quebra(self):
        assert narrate_script({}, character="M", voice="onyx", model="tts") == []

    def test_cena_que_nao_e_objeto_e_ignorada(self):
        script = {"scenes": ["lixo", None, CENA]}
        cenas = narrate_script(script, character="M", voice="onyx", model="tts")
        assert len(cenas) == 1
