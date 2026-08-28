"""Fase 3 da gamificação: desafios, temporadas e ligas.

O que os testes protegem aqui: o placar de um desafio sai de resposta real (e
resposta instantânea não pontua), a temporada não sorteia prêmio, e a liga não
transforma um grupo de três pessoas em tabela de classificação.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.game.challenges import (
    BOSS_TARGET_ACCURACY,
    MAX_COMBO_MULTIPLIER,
    MIN_SECONDS_PER_ANSWER,
    MODES_BY_KEY,
    ChallengeMode,
    RunAnswer,
    combo_multiplier,
    evaluate_run,
    score_run,
)
from app.domain.game.leagues import (
    DIVISION_SIZE,
    MIN_LEAGUE_SIZE,
    LeagueEntry,
    build_league,
)
from app.domain.game.seasons import (
    MIN_QUALIFIED_DAYS,
    REWARDS,
    SHIELD_POSITIONS,
    SeasonStanding,
    SeasonWindow,
    rewards_for,
)


def _answers(correct: int, wrong: int = 0, *, seconds: int = 20) -> list[RunAnswer]:
    return [RunAnswer(True, seconds) for _ in range(correct)] + [
        RunAnswer(False, seconds) for _ in range(wrong)
    ]


class TestCombo:
    def test_sem_sequencia_o_multiplicador_e_neutro(self):
        assert combo_multiplier(0) == 1.0
        assert combo_multiplier(1) == 1.0

    def test_cresce_dez_por_cento_por_acerto_encadeado(self):
        assert combo_multiplier(2) == 1.1
        assert combo_multiplier(6) == 1.5

    def test_o_multiplicador_tem_teto(self):
        assert combo_multiplier(50) == MAX_COMBO_MULTIPLIER

    def test_erro_zera_a_sequencia_mas_guarda_o_recorde(self):
        spec = MODES_BY_KEY[ChallengeMode.COMBO]
        state = evaluate_run(spec, _answers(6) + _answers(0, 1), elapsed_seconds=200)

        assert state.combo == 0
        assert state.best_combo == 6
        assert state.multiplier == 1.0

    def test_resposta_instantanea_nao_alimenta_combo(self):
        """Chutar rápido não é sequência de acerto."""
        spec = MODES_BY_KEY[ChallengeMode.COMBO]
        rapidas = [RunAnswer(True, MIN_SECONDS_PER_ANSWER - 1) for _ in range(8)]
        state = evaluate_run(spec, rapidas, elapsed_seconds=10)

        assert state.correct == 8, "a resposta aconteceu e continua registrada"
        assert state.best_combo == 0, "mas não conta para o combo"
        assert state.multiplier == 1.0


class TestSurvival:
    def test_a_rodada_acaba_no_terceiro_erro(self):
        spec = MODES_BY_KEY[ChallengeMode.SURVIVAL]
        state = evaluate_run(spec, _answers(9, 3), elapsed_seconds=400)

        assert state.lives_left == 0
        assert state.is_over is True
        assert "erros" in (state.over_reason or "")

    def test_com_vidas_restantes_a_rodada_segue(self):
        spec = MODES_BY_KEY[ChallengeMode.SURVIVAL]
        state = evaluate_run(spec, _answers(9, 2), elapsed_seconds=400)

        assert state.lives_left == 1
        assert state.is_over is False
        assert state.over_reason is None

    def test_a_pontuacao_e_o_numero_de_acertos(self):
        spec = MODES_BY_KEY[ChallengeMode.SURVIVAL]
        state = evaluate_run(spec, _answers(14, 3), elapsed_seconds=600)
        result = score_run(spec, state)

        assert result.score == 14
        assert result.achieved is False, "morreu com três erros"
        assert "14" in result.headline


class TestTimeAttack:
    def test_o_relogio_encerra_a_rodada(self):
        spec = MODES_BY_KEY[ChallengeMode.TIME_ATTACK]
        state = evaluate_run(spec, _answers(6, 2), elapsed_seconds=spec.time_limit_seconds or 0)

        assert state.seconds_left == 0
        assert state.is_over is True
        assert state.over_reason == "O tempo acabou."

    def test_tempo_restante_nunca_fica_negativo(self):
        spec = MODES_BY_KEY[ChallengeMode.TIME_ATTACK]
        state = evaluate_run(spec, _answers(3), elapsed_seconds=99_999)

        assert state.seconds_left == 0


class TestBoss:
    def test_vence_quem_alcanca_o_alvo_declarado(self):
        spec = MODES_BY_KEY[ChallengeMode.BOSS]
        state = evaluate_run(spec, _answers(12, 3), elapsed_seconds=600)
        result = score_run(spec, state)

        assert state.accuracy == pytest.approx(0.8)
        assert state.accuracy >= BOSS_TARGET_ACCURACY
        assert result.achieved is True

    def test_rodada_incompleta_nao_derruba_o_boss(self):
        """Acertar 5 de 5 e parar não é vencer um desafio de 15 questões."""
        spec = MODES_BY_KEY[ChallengeMode.BOSS]
        state = evaluate_run(spec, _answers(5), elapsed_seconds=200)
        result = score_run(spec, state)

        assert result.achieved is False

    def test_sem_resposta_nao_ha_taxa_de_acerto(self):
        spec = MODES_BY_KEY[ChallengeMode.BOSS]
        state = evaluate_run(spec, [], elapsed_seconds=0)

        assert state.accuracy is None, "zero de zero não é zero por cento"
        assert score_run(spec, state).xp == 0


class TestScore:
    def test_o_xp_e_proporcional_ao_que_foi_respondido(self):
        spec = MODES_BY_KEY[ChallengeMode.TIME_ATTACK]
        metade = score_run(spec, evaluate_run(spec, _answers(10), elapsed_seconds=300))
        tudo = score_run(spec, evaluate_run(spec, _answers(20), elapsed_seconds=500))

        assert metade.xp == spec.base_xp // 2
        assert tudo.xp == spec.base_xp

    def test_a_conta_do_xp_fica_aberta(self):
        spec = MODES_BY_KEY[ChallengeMode.COMBO]
        result = score_run(spec, evaluate_run(spec, _answers(10), elapsed_seconds=300))
        rotulos = [line.label for line in result.breakdown]

        assert "XP base do modo" in rotulos
        assert "Proporção respondida" in rotulos
        assert "XP da rodada" in rotulos
        assert str(result.xp) in [line.value for line in result.breakdown]


class TestSeasons:
    def test_a_janela_sabe_onde_esta(self):
        window = SeasonWindow("Temporada 1", date(2026, 3, 1), date(2026, 4, 25))

        assert window.total_days() == 56
        assert window.contains(date(2026, 3, 15)) is True
        assert window.contains(date(2026, 5, 1)) is False
        assert window.days_left(date(2026, 4, 20)) == 5
        assert window.progress(date(2026, 2, 1)) == 0.0
        assert window.progress(date(2026, 4, 25)) == 1.0

    def test_todo_premio_declara_utilidade_e_criterio(self):
        for reward in REWARDS:
            assert reward.utility, "prêmio sem utilidade declarada não entra"
            assert reward.criterion

    def test_o_premio_sai_de_criterio_verificavel_nunca_de_sorteio(self):
        campeao = rewards_for(
            SeasonStanding(seasonal_xp=4200, qualified_days=30, position=1, participants=40)
        )
        meio = rewards_for(
            SeasonStanding(seasonal_xp=900, qualified_days=12, position=18, participants=40)
        )

        assert [item.slug for item in campeao.rewards] == ["escudo-extra", "selo-temporada"]
        assert [item.slug for item in meio.rewards] == ["selo-temporada"]
        # O que não veio aparece com o critério à vista, em vez de sumir.
        assert [item.slug for item in meio.missed] == ["escudo-extra"]

    def test_participacao_curta_nao_rende_selo(self):
        outcome = rewards_for(
            SeasonStanding(qualified_days=MIN_QUALIFIED_DAYS - 1, position=9, participants=20)
        )

        assert outcome.rewards == []
        assert len(outcome.missed) == 2

    def test_o_escudo_vai_para_o_topo_da_divisao(self):
        dentro = rewards_for(SeasonStanding(qualified_days=30, position=SHIELD_POSITIONS))
        fora = rewards_for(SeasonStanding(qualified_days=30, position=SHIELD_POSITIONS + 1))

        assert any(item.slug == "escudo-extra" for item in dentro.rewards)
        assert all(item.slug != "escudo-extra" for item in fora.rewards)

    def test_a_temporada_declara_que_mede_esforco_e_nao_dominio(self):
        outcome = rewards_for(SeasonStanding())
        assert "esforço" in outcome.note
        assert "rank" in outcome.note


class TestLeagues:
    def test_grupo_pequeno_nao_vira_tabela(self):
        entries = [LeagueEntry(f"u{i}", 100) for i in range(MIN_LEAGUE_SIZE - 1)]
        league = build_league(entries, you_key="u0", context_label="PCDF · Agente")

        assert league.members == []
        assert league.your_position is None
        assert str(MIN_LEAGUE_SIZE) in (league.empty_reason or "")

    def test_quem_saiu_da_comparacao_nao_recebe_tabela(self):
        entries = [LeagueEntry(f"u{i}", 100 - i) for i in range(10)]
        league = build_league(entries, you_key="fora", context_label="PCDF · Agente")

        assert league.members == []
        assert "opcional" in (league.empty_reason or "")

    def test_anonimato_e_o_padrao(self):
        entries = [LeagueEntry(f"u{i}", 100 - i) for i in range(8)]
        entries[2] = LeagueEntry("u2", 98, display_name="Marina S.")
        league = build_league(entries, you_key="u0", context_label="PCDF · Agente")

        nomeados = [item for item in league.members if item.is_named]
        assert [item.label for item in nomeados] == ["Marina S."]
        assert all(
            item.label.startswith("Candidato #") for item in league.members if not item.is_named
        )

    def test_a_divisao_e_a_fatia_onde_o_candidato_esta(self):
        entries = [LeagueEntry(f"u{i}", 1000 - i) for i in range(70)]
        league = build_league(entries, you_key="u40", context_label="PCDF · Agente")

        assert league.participants == 70
        assert league.division_index == 1
        assert league.division_label == "Divisão 2"
        assert len(league.members) == DIVISION_SIZE
        assert league.your_position == 41
        assert league.your_division_position == 11
        assert any(item.is_you for item in league.members)

    def test_a_ordem_e_deterministica_em_caso_de_empate(self):
        empatados = [LeagueEntry(f"u{i}", 500, active_days=10) for i in range(6)]
        primeira = build_league(empatados, you_key="u0", context_label="X")
        segunda = build_league(list(reversed(empatados)), you_key="u0", context_label="X")

        assert [item.label for item in primeira.members] == [item.label for item in segunda.members]

    def test_a_liga_declara_que_compara_esforco_e_e_opcional(self):
        entries = [LeagueEntry(f"u{i}", 100 - i) for i in range(8)]
        league = build_league(entries, you_key="u0", context_label="PCDF · Agente")

        assert "esforço" in league.note
        assert "sair dela não afeta" in league.note
