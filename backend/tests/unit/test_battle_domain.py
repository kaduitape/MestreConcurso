"""Batalha RPG — escolha de layout, combate derivado e bestiário estável.

O que estes testes protegem é a prioridade declarada no pedido: **legibilidade
da questão acima da sensação de jogo**. Se a régua do layout falhar, o texto da
alternativa some embaixo de um monstro — e aí o RPG atrapalhou o estudo.
"""

from __future__ import annotations

from app.domain.game.battle import (
    BESTIARY,
    MONSTER_DAMAGE,
    PLAYER_DAMAGE,
    PLAYER_MAX_HP,
    BattleAnswer,
    BattleLayout,
    LayoutSettings,
    Viewport,
    enemy_max_hp,
    evaluate_battle,
    monsters_for,
    select_battle_layout,
    species_for,
)

CURTAS = ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador"]
LONGAS = [
    "Legislar sobre direito tributário, financeiro, penitenciário e econômico.",
    "Legislar sobre organização administrativa, servidores públicos e regime jurídico.",
    "Legislar sobre direito civil, comercial, penal, processual e eleitoral.",
    "Legislar sobre educação, cultura, ciência, tecnologia e comunicação.",
]


class TestLayoutSelection:
    def test_alternativas_curtas_vao_para_a_arena(self):
        decision = select_battle_layout(CURTAS)

        assert decision.layout == BattleLayout.MONSTER_ARENA
        assert decision.is_arena is True
        assert decision.max_length == len("Rio de Janeiro")

    def test_alternativas_longas_vao_para_o_layout_compacto(self):
        decision = select_battle_layout(LONGAS)

        assert decision.layout == BattleLayout.COMPACT_ANSWER
        assert "caracteres" in decision.reason

    def test_a_decisao_explica_o_motivo(self):
        """Nada de caixa-preta: a escolha diz em que régua bateu."""
        for options in (CURTAS, LONGAS):
            assert select_battle_layout(options).reason

    def test_uma_alternativa_longa_sozinha_ja_derruba_a_arena(self):
        misturado = [*CURTAS[:3], "Brasília, por força do artigo 18 da Constituição Federal"]

        assert select_battle_layout(misturado).layout == BattleLayout.COMPACT_ANSWER

    def test_a_media_alta_derruba_a_arena_mesmo_sem_gigante(self):
        settings = LayoutSettings(short_answer_max=60, short_average_max=20)
        options = ["Texto com trinta e cinco caracteres."] * 4

        decision = select_battle_layout(options, settings=settings)

        assert decision.layout == BattleLayout.COMPACT_ANSWER
        assert "média" in decision.reason

    def test_o_mesmo_conjunto_pode_mudar_de_layout_por_viewport(self):
        """Item 4: no celular há menos espaço horizontal."""
        # Curtas, com uma de 31 caracteres: cabe embaixo do monstro no desktop,
        # não cabe na largura do celular.
        medias = ["Sim", "Não", "Talvez", "Competência privativa da União."]

        desktop = select_battle_layout(medias, viewport=Viewport.DESKTOP)
        mobile = select_battle_layout(medias, viewport=Viewport.MOBILE)

        assert desktop.layout == BattleLayout.MONSTER_ARENA
        assert mobile.layout == BattleLayout.COMPACT_ANSWER
        assert Viewport.MOBILE in mobile.reason

    def test_o_tablet_tem_regua_propria(self):
        settings = LayoutSettings()

        assert settings.answer_max_for(Viewport.TABLET) < settings.answer_max_for(Viewport.DESKTOP)
        assert settings.answer_max_for(Viewport.MOBILE) < settings.answer_max_for(Viewport.TABLET)

    def test_muitas_alternativas_nao_cabem_na_arena(self):
        decision = select_battle_layout(["Sim", "Não", "Talvez", "Nunca", "Sempre", "Ora"])

        assert decision.layout == BattleLayout.COMPACT_ANSWER
        assert "alternativas" in decision.reason

    def test_o_numero_de_linhas_estimadas_conta(self):
        """Texto que quebraria em três linhas empurra o enunciado da tela."""
        settings = LayoutSettings(chars_per_line_desktop=10, max_lines_for_arena=2)

        decision = select_battle_layout(["Vinte e cinco caracteres!"], settings=settings)

        assert decision.estimated_lines == 3
        assert decision.layout == BattleLayout.COMPACT_ANSWER
        assert "linhas" in decision.reason

    def test_os_limiares_sao_configuraveis(self):
        """Item 3: os valores não podem ficar rígidos no código."""
        apertado = LayoutSettings(short_answer_max=5, short_average_max=5)

        assert select_battle_layout(CURTAS).layout == BattleLayout.MONSTER_ARENA
        assert select_battle_layout(CURTAS, settings=apertado).layout == BattleLayout.COMPACT_ANSWER

    def test_sem_alternativas_nao_quebra(self):
        decision = select_battle_layout([])

        assert decision.options == 0
        assert decision.layout == BattleLayout.MONSTER_ARENA


class TestCombat:
    def test_o_hp_do_inimigo_acompanha_o_tamanho_da_rodada(self):
        assert enemy_max_hp(4) == 3 * PLAYER_DAMAGE
        assert enemy_max_hp(8) == 6 * PLAYER_DAMAGE
        assert enemy_max_hp(1) >= PLAYER_DAMAGE

    def test_o_estado_e_derivado_das_respostas(self):
        status = evaluate_battle([BattleAnswer(True), BattleAnswer(False)], questions=8)

        assert status.correct == 1
        assert status.wrong == 1
        assert status.enemy_hp == enemy_max_hp(8) - PLAYER_DAMAGE
        assert status.player_hp == PLAYER_MAX_HP - MONSTER_DAMAGE

    def test_acertar_derruba_o_inimigo(self):
        status = evaluate_battle([BattleAnswer(True)] * 3, questions=4)

        assert status.enemy_hp == 0
        assert status.victory is True
        assert status.is_over is True
        assert status.outcome_reason == "O inimigo caiu."

    def test_errar_demais_derruba_o_guerreiro(self):
        status = evaluate_battle([BattleAnswer(False)] * 5, questions=10)

        assert status.player_hp == 0
        assert status.defeat is True
        assert status.victory is False
        assert "não aguentou" in (status.outcome_reason or "")

    def test_o_hp_nunca_fica_negativo(self):
        status = evaluate_battle([BattleAnswer(False)] * 20, questions=20)

        assert status.player_hp == 0
        assert status.enemy_hp >= 0

    def test_acabar_as_questoes_com_o_inimigo_vivo_nao_e_vitoria(self):
        status = evaluate_battle(
            [BattleAnswer(True), BattleAnswer(False), BattleAnswer(False)], questions=3
        )

        assert status.is_over is True
        assert status.victory is False
        assert status.defeat is False
        assert "continua de pé" in (status.outcome_reason or "")

    def test_a_batalha_em_andamento_nao_declara_desfecho(self):
        status = evaluate_battle([BattleAnswer(True)], questions=8)

        assert status.is_over is False
        assert status.outcome_reason is None

    def test_as_proporcoes_de_hp_ficam_entre_zero_e_um(self):
        status = evaluate_battle([BattleAnswer(True), BattleAnswer(False)], questions=8)

        assert 0.0 <= status.player_hp_ratio <= 1.0
        assert 0.0 <= status.enemy_hp_ratio <= 1.0

    def test_o_erro_custa_menos_que_o_acerto_rende(self):
        """A batalha é consequência do estudo, não punição por errar."""
        assert MONSTER_DAMAGE < PLAYER_DAMAGE


class TestBestiary:
    def test_a_especie_e_estavel_para_a_mesma_rodada(self):
        assert species_for("run-abc") == species_for("run-abc")

    def test_rodadas_diferentes_podem_ter_inimigos_diferentes(self):
        especies = {species_for(f"run-{index}").slug for index in range(40)}

        assert len(especies) > 1, "o sorteio não pode ficar preso a um monstro só"

    def test_todo_monstro_tem_forma_e_cores_declaradas(self):
        for especie in BESTIARY:
            assert especie.shape
            assert especie.color_token
            assert especie.accent_token
            assert especie.name != especie.slug

    def test_cada_alternativa_recebe_um_monstro(self):
        inimigo = species_for("run-1")
        monstros = monsters_for("q-1", ["A", "B", "C", "D"], enemy=inimigo)

        assert [item.letter for item in monstros] == ["A", "B", "C", "D"]
        assert all(item.species == inimigo.slug for item in monstros)

    def test_os_monstros_sao_estaveis_entre_leituras(self):
        """Sortear a cada render trocaria a cara do inimigo no meio da batalha."""
        inimigo = species_for("run-1")
        primeira = monsters_for("q-1", ["A", "B", "C"], enemy=inimigo)
        segunda = monsters_for("q-1", ["A", "B", "C"], enemy=inimigo)

        assert [item.variant for item in primeira] == [item.variant for item in segunda]

    def test_questoes_diferentes_variam_a_silhueta(self):
        inimigo = species_for("run-1")
        variantes = {
            tuple(item.variant for item in monsters_for(f"q-{index}", ["A", "B"], enemy=inimigo))
            for index in range(20)
        }

        assert len(variantes) > 1
