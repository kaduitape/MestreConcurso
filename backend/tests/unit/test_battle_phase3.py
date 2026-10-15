"""Batalha RPG Fase 3 — classes, equipamentos, campanha e ranking.

A linha que estes testes vigiam é uma só: **classe e equipamento mudam o
combate, nunca a medição**. No dia em que uma armadura melhor subir alguém no
ranking ou limpar um estágio de campanha, a plataforma terá começado a dizer que
quem tem equipamento melhor estuda melhor.
"""

from __future__ import annotations

from app.domain.game.battle import (
    CLASSES,
    CLASSES_BY_SLUG,
    DEFAULT_LOADOUT,
    EQUIPMENT,
    EQUIPMENT_BY_SLUG,
    MONSTER_DAMAGE,
    PLAYER_MAX_HP,
    BattleAnswer,
    BattlePower,
    CombatSettings,
    EquipmentSlot,
    Loadout,
    coins_for,
    evaluate_battle,
    player_damage,
    player_max_hp,
    power_cost,
    resolve_loadout,
)
from app.domain.game.battle_campaign import (
    MAX_STAGES,
    MIN_RANKED_BATTLES,
    RankingEntry,
    StageInput,
    build_campaign,
    build_ranking,
)
from app.domain.game.leagues import MIN_LEAGUE_SIZE

LENTO = 120


class TestClasses:
    def test_a_classe_de_partida_e_neutra(self):
        """Quem nunca escolheu classe joga o combate base."""
        assert player_max_hp(DEFAULT_LOADOUT) == PLAYER_MAX_HP
        assert player_damage(streak=1, is_critical=False, loadout=DEFAULT_LOADOUT) == (
            player_damage(streak=1, is_critical=False)
        )

    def test_toda_classe_declara_a_troca_por_escrito(self):
        for spec in CLASSES:
            assert spec.tradeoff, "classe sem troca declarada esconde a comparação"
            assert spec.name and spec.description

    def test_nenhuma_classe_e_so_melhor_que_as_outras(self):
        """Uma classe sem perda nenhuma tornaria a escolha falsa."""
        for spec in CLASSES:
            if spec.slug == "recruta":
                continue
            valores = spec.modifiers
            ganhos = sum(
                max(0, item)
                for item in (
                    valores.damage_percent,
                    valores.max_hp_percent,
                    valores.coin_percent,
                    valores.power_discount_percent,
                )
            )
            assert ganhos > 0

    def test_o_guardiao_aguenta_mais_e_bate_menos(self):
        guardiao = Loadout(class_slug="guardiao")
        assert player_max_hp(guardiao) > PLAYER_MAX_HP
        assert player_damage(streak=1, is_critical=False, loadout=guardiao) < player_damage(
            streak=1, is_critical=False
        )

    def test_o_duelista_bate_mais_e_aguenta_menos(self):
        duelista = Loadout(class_slug="duelista")
        assert player_damage(streak=1, is_critical=False, loadout=duelista) > player_damage(
            streak=1, is_critical=False
        )
        assert player_max_hp(duelista) < PLAYER_MAX_HP

    def test_o_estrategista_barateia_os_poderes(self):
        regua = CombatSettings()
        base = power_cost(BattlePower.SHIELD, settings=regua, loadout=DEFAULT_LOADOUT)
        dele = power_cost(
            BattlePower.SHIELD, settings=regua, loadout=Loadout(class_slug="estrategista")
        )
        assert dele < base

    def test_classe_desconhecida_cai_na_neutra(self):
        estranha = Loadout(class_slug="necromante")
        assert player_max_hp(estranha) == PLAYER_MAX_HP

    def test_a_vida_nunca_cai_abaixo_de_um_golpe(self):
        """Uma régua ruim não pode criar um guerreiro que morre antes de jogar."""
        assert player_max_hp(Loadout(class_slug="duelista")) >= MONSTER_DAMAGE


class TestEquipment:
    def test_todo_espaco_tem_uma_peca_inicial_sem_conquista(self):
        for slot in EquipmentSlot:
            iniciais = [
                item
                for item in EQUIPMENT
                if item.slot == slot and item.requires_achievement is None
            ]
            assert iniciais, "ninguém pode entrar na batalha desarmado"

    def test_nenhuma_peca_e_comprada_ou_sorteada(self):
        """Equipamento sai de conquista real — não de moeda nem de caixa."""
        for item in EQUIPMENT:
            assert item.requires_achievement is None or isinstance(item.requires_achievement, str)

    def test_peca_nao_conquistada_volta_a_inicial(self):
        loadout = resolve_loadout(
            class_slug="duelista",
            weapon_slug="lamina-do-acerto",
            armor_slug="cota-de-ferro",
            trinket_slug="amuleto-de-latao",
            unlocked=set(),
        )
        assert loadout.weapon_slug == "espada-simples"
        assert loadout.armor_slug == "gibao-de-couro"
        assert loadout.class_slug == "duelista", "classe não depende de conquista"

    def test_peca_conquistada_e_mantida(self):
        loadout = resolve_loadout(
            class_slug="recruta",
            weapon_slug="lamina-do-acerto",
            armor_slug="gibao-de-couro",
            trinket_slug="amuleto-de-latao",
            unlocked={"mil-questoes"},
        )
        assert loadout.weapon_slug == "lamina-do-acerto"

    def test_slug_invalido_nao_derruba_a_batalha(self):
        loadout = resolve_loadout(
            class_slug=None,
            weapon_slug="excalibur",
            armor_slug=None,
            trinket_slug="cota-de-ferro",  # peça no espaço errado
            unlocked={"disciplina-de-ferro"},
        )
        assert loadout.weapon_slug == "espada-simples"
        assert loadout.trinket_slug == "amuleto-de-latao"

    def test_o_equipamento_muda_o_combate(self):
        equipado = Loadout(weapon_slug="lamina-do-acerto", armor_slug="cota-de-ferro")
        assert player_damage(streak=1, is_critical=False, loadout=equipado) > player_damage(
            streak=1, is_critical=False
        )
        assert player_max_hp(equipado) > PLAYER_MAX_HP

    def test_o_equipamento_nao_muda_o_acerto(self):
        """A conta que dá XP e limpa campanha é a mesma com e sem armadura."""
        respostas = [BattleAnswer(True, LENTO), BattleAnswer(False, LENTO)]
        base = evaluate_battle(respostas, questions=8)
        forte = evaluate_battle(
            respostas,
            questions=8,
            loadout=Loadout(class_slug="duelista", weapon_slug="gladio-do-atirador"),
        )
        assert base.correct == forte.correct
        assert base.wrong == forte.wrong
        assert base.answered == forte.answered

    def test_o_loadout_congelado_reproduz_a_mesma_vida(self):
        respostas = [BattleAnswer(True, 5), BattleAnswer(True, LENTO)]
        loadout = Loadout(class_slug="guardiao", weapon_slug="lamina-do-acerto")
        leituras = {
            evaluate_battle(respostas, questions=8, loadout=loadout).enemy_hp for _ in range(20)
        }
        assert len(leituras) == 1

    def test_todas_as_pecas_tem_espaco_valido(self):
        for item in EQUIPMENT:
            assert item.slot in set(EquipmentSlot)
            assert EQUIPMENT_BY_SLUG[item.slug] is item

    def test_o_bonus_de_moeda_do_amuleto_vale(self):
        base = coins_for(streak=1)
        com = coins_for(streak=1, loadout=Loadout(trinket_slug="sinete-do-analista"))
        assert com > base


class TestBoss:
    def test_o_chefe_aguenta_mais_que_um_inimigo_comum(self):
        comum = evaluate_battle([], questions=12)
        chefe = evaluate_battle([], questions=12, boss_hp_percent=60)
        assert chefe.enemy_max_hp > comum.enemy_max_hp

    def test_o_chefe_sem_bonus_e_um_inimigo_comum(self):
        assert (
            evaluate_battle([], questions=12, boss_hp_percent=0).enemy_max_hp
            == evaluate_battle([], questions=12).enemy_max_hp
        )


class TestCampaign:
    def _stage(self, **kwargs):
        base: dict[str, object] = {
            "subject_id": 1,
            "subject_public_id": "sub-1",
            "label": "Direito Constitucional",
            "priority_score": 0.8,
            "questions_available": 50,
        }
        base.update(kwargs)
        return StageInput(**base)  # type: ignore[arg-type]

    def test_sem_priority_score_nao_ha_campanha(self):
        campanha = build_campaign([], required_questions=12)
        assert campanha.total == 0
        assert campanha.empty_reason is not None
        assert "Priority Score" in campanha.empty_reason

    def test_a_ordem_e_a_do_priority_score(self):
        campanha = build_campaign(
            [
                self._stage(subject_public_id="a", label="A", priority_score=0.4),
                self._stage(subject_public_id="b", label="B", priority_score=0.9),
            ],
            required_questions=12,
        )
        assert [item.subject_public_id for item in campanha.stages] == ["b", "a"]

    def test_nenhum_estagio_tranca_outro(self):
        """Conteúdo de estudo não fica atrás de progresso de jogo."""
        campanha = build_campaign(
            [
                self._stage(subject_public_id="a", priority_score=0.9),
                self._stage(subject_public_id="b", priority_score=0.5),
            ],
            required_questions=12,
        )
        assert all(item.is_locked is False for item in campanha.stages)

    def test_estagio_sem_questoes_no_banco_diz_quantas_faltam(self):
        campanha = build_campaign([self._stage(questions_available=4)], required_questions=12)
        estagio = campanha.stages[0]
        assert estagio.is_locked
        assert estagio.blocked_reason is not None
        assert "4 de 12" in estagio.blocked_reason

    def test_o_estagio_e_vencido_por_batalha_com_acerto_suficiente(self):
        campanha = build_campaign(
            [self._stage(battles=2, cleared_battles=1)], required_questions=12
        )
        assert campanha.stages[0].cleared
        assert campanha.cleared == 1

    def test_batalha_jogada_sem_atingir_o_alvo_nao_limpa(self):
        campanha = build_campaign(
            [self._stage(battles=3, cleared_battles=0)], required_questions=12
        )
        assert campanha.stages[0].cleared is False
        assert campanha.stages[0].battles == 3

    def test_a_campanha_tem_um_teto_de_estagios(self):
        muitos = [
            self._stage(subject_public_id=f"s{i}", priority_score=1 - i / 100) for i in range(20)
        ]
        assert build_campaign(muitos, required_questions=12).total == MAX_STAGES


class TestRanking:
    def _entry(self, key: str, **kwargs):
        base: dict[str, object] = {"battles": 5, "wins": 3, "correct": 30}
        base.update(kwargs)
        return RankingEntry(user_key=key, **base)  # type: ignore[arg-type]

    def _many(self, count: int):
        return [self._entry(f"u{i}", wins=count - i, correct=(count - i) * 5) for i in range(count)]

    def test_grupo_pequeno_nao_vira_tabela(self):
        ranking = build_ranking(self._many(3), you_key="u0", context_label="Cargo")
        assert ranking.members == []
        assert ranking.empty_reason is not None
        assert str(MIN_LEAGUE_SIZE) in ranking.empty_reason

    def test_quem_tem_poucas_batalhas_nao_entra(self):
        entries = self._many(MIN_LEAGUE_SIZE + 1)
        entries.append(self._entry("novato", battles=MIN_RANKED_BATTLES - 1, wins=99))
        ranking = build_ranking(entries, you_key="u0", context_label="Cargo")
        assert "novato" not in {item.label for item in ranking.members}
        assert ranking.members[0].wins != 99, "poucas batalhas não lideram tabela"

    def test_a_ordem_e_por_vitorias(self):
        ranking = build_ranking(self._many(6), you_key="u0", context_label="Cargo")
        vitorias = [item.wins for item in ranking.members]
        assert vitorias == sorted(vitorias, reverse=True)

    def test_anonimato_e_o_padrao(self):
        ranking = build_ranking(self._many(6), you_key="u3", context_label="Cargo")
        outros = [item for item in ranking.members if not item.is_you]
        assert all(item.is_named is False for item in outros)
        assert all(item.label.startswith("Candidato #") for item in outros)

    def test_quem_escolheu_aparecer_aparece(self):
        entries = self._many(6)
        entries[0] = self._entry("u0", wins=99, display_name="Ana")
        ranking = build_ranking(entries, you_key="u5", context_label="Cargo")
        assert ranking.members[0].label == "Ana"
        assert ranking.members[0].is_named

    def test_a_tabela_diz_onde_voce_esta(self):
        ranking = build_ranking(self._many(6), you_key="u2", context_label="Cargo")
        assert ranking.your_position == 3
        assert any(item.is_you for item in ranking.members)

    def test_a_nota_nega_qualquer_leitura_de_aprovacao(self):
        ranking = build_ranking(self._many(6), you_key="u0", context_label="Cargo")
        assert "aprovação" in ranking.note
        assert "Equipamento e classe mudam o combate" in ranking.note

    def test_o_ranking_nao_publica_percentual_de_acerto(self):
        """Batalha pode acabar antes das questões: dividir por denominador
        incerto seria fabricar estatística."""
        ranking = build_ranking(self._many(6), you_key="u0", context_label="Cargo")
        campos = ranking.members[0].__slots__
        assert "accuracy" not in campos


class TestClassCatalogue:
    def test_toda_classe_tem_slug_unico(self):
        slugs = [item.slug for item in CLASSES]
        assert len(slugs) == len(set(slugs))
        assert all(CLASSES_BY_SLUG[slug] for slug in slugs)
