"""Fase 2 da gamificação: Você vs Banca, Jornada e Mapa do Edital.

O que estes testes protegem é sempre a mesma coisa: nenhuma tela pode afirmar
mais do que a amostra permite, e nenhuma delas pode prometer aprovação.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.domain.game.board_battle import (
    MIN_BOARD_ANSWERS,
    MIN_SUBJECT_ANSWERS,
    AnswerSample,
    build_battle,
)
from app.domain.game.journey import (
    DISCLAIMER,
    JourneyInput,
    MilestoneState,
    build_journey,
)
from app.domain.game.territory import (
    MASTERED_THRESHOLD,
    MIN_ANSWERS,
    MIN_REVIEWS,
    STALE_DAYS,
    WEIGHT_COVERAGE,
    TerritoryInput,
    TerritoryState,
    build_map,
    build_territory,
)

TODAY = date(2026, 3, 16)  # segunda-feira


def _samples(total: int, correct: int, *, subject: str = "Português", day: date = TODAY):
    return [
        AnswerSample(
            subject_id=1,
            subject_name=subject,
            is_correct=index < correct,
            answered_on=day,
        )
        for index in range(total)
    ]


def _battle(samples):
    return build_battle(samples, board_slug="cebraspe", board_name="Cebraspe")


class TestBoardBattle:
    def test_sem_amostra_nao_ha_placar(self):
        battle = _battle(_samples(MIN_BOARD_ANSWERS - 1, 20))

        assert battle.is_sufficient is False
        assert battle.you == 0 and battle.board == 0
        assert battle.is_winning is False
        assert battle.empty_reason is not None
        assert str(MIN_BOARD_ANSWERS) in battle.empty_reason

    def test_placar_soma_cem_pontos(self):
        battle = _battle(_samples(40, 26))

        assert battle.is_sufficient is True
        assert battle.you + battle.board == 100
        assert battle.you == 65
        assert battle.is_winning is True

    def test_banca_ganha_quando_candidato_erra_mais(self):
        battle = _battle(_samples(50, 18))

        assert battle.you == 36
        assert battle.board == 64
        assert battle.is_winning is False

    def test_pontos_da_banca_sao_exatamente_os_erros(self):
        """Nada de adversário simulado: a banca pontua o que o candidato errou."""
        battle = _battle(_samples(80, 50))

        assert battle.correct == 50
        assert battle.answers - battle.correct == 30
        assert battle.board == round(30 / 80 * 100)

    def test_disciplina_sem_amostra_nao_recebe_placar(self):
        samples = _samples(MIN_SUBJECT_ANSWERS, 20, subject="Português")
        samples += _samples(5, 5, subject="Informática")

        battle = _battle(samples)
        by_name = {item.subject_name: item for item in battle.subjects}

        assert by_name["Português"].is_sufficient is True
        fraca = by_name["Informática"]
        assert fraca.is_sufficient is False
        assert fraca.you == 0 and fraca.board == 0
        assert fraca.answers == 5
        assert fraca.insufficient_reason is not None

    def test_disciplinas_insuficientes_ficam_no_fim(self):
        samples = _samples(30, 12, subject="Direito")
        samples += _samples(30, 27, subject="Português")
        samples += _samples(3, 3, subject="RLM")

        battle = _battle(samples)

        assert [item.subject_name for item in battle.subjects] == [
            "Português",
            "Direito",
            "RLM",
        ]

    def test_evolucao_agrupa_por_semana_e_respeita_a_janela(self):
        samples: list[AnswerSample] = []
        for week in range(10):
            day = TODAY - timedelta(weeks=week)
            samples += _samples(6, 3, day=day)

        battle = build_battle(samples, board_slug="fgv", board_name="FGV", weeks=4)

        assert len(battle.evolution) == 4
        weeks = [point.week_start for point in battle.evolution]
        assert weeks == sorted(weeks)
        assert weeks[-1] == TODAY
        assert all(point.answers == 6 for point in battle.evolution)
        assert all(point.accuracy == 0.5 for point in battle.evolution)


class TestJourney:
    def test_sem_plano_nao_inventa_marcos(self):
        journey = build_journey(JourneyInput(has_plan=False, questions_answered=500))

        assert journey.milestones == []
        assert journey.empty_reason is not None
        assert journey.completed == 0

    def test_disclaimer_acompanha_a_jornada(self):
        journey = build_journey(JourneyInput(has_plan=True))

        assert journey.disclaimer == DISCLAIMER
        assert "aprovação" in DISCLAIMER

    def test_nenhum_marco_promete_aprovacao(self):
        journey = build_journey(JourneyInput(has_plan=True, coverage=0.9))
        texto = " ".join(
            f"{item.label} {item.description} {item.detail}" for item in journey.milestones
        ).lower()

        for proibido in ("você vai passar", "será aprovado", "aprovação garantida", "chance de"):
            assert proibido not in texto

    def test_apenas_um_marco_corrente_e_ele_e_o_primeiro_pendente(self):
        journey = build_journey(
            JourneyInput(
                has_plan=True,
                study_sessions=3,
                questions_answered=120,
                coverage=0.10,
                simulations_finished=0,
            )
        )
        current = [item for item in journey.milestones if item.state == MilestoneState.CURRENT]

        assert len(current) == 1
        assert current[0].key == "coverage_25"
        assert journey.current_key == "coverage_25"

    def test_marcos_concluidos_sao_contados(self):
        journey = build_journey(
            JourneyInput(
                has_plan=True,
                study_sessions=10,
                questions_answered=400,
                simulations_finished=2,
                coverage=0.55,
            )
        )
        done = {item.key for item in journey.milestones if item.state == MilestoneState.DONE}

        assert done == {
            "first_study",
            "hundred_questions",
            "coverage_25",
            "first_simulation",
            "coverage_50",
        }
        assert journey.completed == 5
        assert journey.total == len(journey.milestones)

    def test_reta_final_so_abre_com_data_de_prova(self):
        sem_data = build_journey(JourneyInput(has_plan=True))
        marco = next(item for item in sem_data.milestones if item.key == "final_stretch")
        assert marco.current == 0
        assert marco.state != MilestoneState.DONE

        na_reta = build_journey(JourneyInput(has_plan=True, days_until_exam=10))
        marco = next(item for item in na_reta.milestones if item.key == "final_stretch")
        assert marco.current == 20

    def test_ratio_nunca_passa_de_um(self):
        journey = build_journey(
            JourneyInput(has_plan=True, questions_answered=9000, study_sessions=90)
        )

        assert all(0.0 <= item.ratio <= 1.0 for item in journey.milestones)


class TestTerritory:
    def test_sem_estudo_o_territorio_esta_trancado(self):
        territory = build_territory(
            TerritoryInput(subject_key="portugues", subject_name="Português")
        )

        assert territory.state == TerritoryState.LOCKED
        assert territory.mastery == 0.0

    def test_sinal_ausente_e_declarado_e_nao_penaliza(self):
        """Sem questões nem revisões, o domínio é a cobertura — não 40% dela."""
        territory = build_territory(
            TerritoryInput(
                subject_key="portugues",
                subject_name="Português",
                coverage=0.8,
                planned_minutes=600,
                studied_minutes=480,
            )
        )

        assert territory.missing_signals == ["desempenho", "retencao"]
        assert territory.mastery == pytest.approx(0.8)
        assert territory.parts_sum == pytest.approx(0.8 * WEIGHT_COVERAGE)
        indisponivel = [item for item in territory.parts if not item.available]
        assert all(item.value is None and item.points == 0.0 for item in indisponivel)
        assert all(item.detail for item in indisponivel)

    def test_amostra_insuficiente_nao_entra_na_conta(self):
        territory = build_territory(
            TerritoryInput(
                subject_key="rlm",
                subject_name="RLM",
                coverage=0.5,
                studied_minutes=100,
                accuracy=0.95,
                answers=MIN_ANSWERS - 1,
                retention=0.95,
                reviews=MIN_REVIEWS - 1,
            )
        )

        assert territory.missing_signals == ["desempenho", "retencao"]
        assert territory.mastery == pytest.approx(0.5)

    def test_dominio_usa_os_tres_sinais_quando_existem(self):
        territory = build_territory(
            TerritoryInput(
                subject_key="constitucional",
                subject_name="Direito Constitucional",
                coverage=0.9,
                studied_minutes=900,
                accuracy=0.8,
                answers=60,
                retention=0.7,
                reviews=40,
            )
        )

        assert territory.missing_signals == []
        assert territory.mastery == pytest.approx(0.9 * 0.4 + 0.8 * 0.4 + 0.7 * 0.2)
        assert territory.state == TerritoryState.MASTERED

    def test_disciplina_dominada_e_esquecida_pede_revisao(self):
        base = {
            "subject_key": "constitucional",
            "subject_name": "Direito Constitucional",
            "coverage": 1.0,
            "studied_minutes": 900,
            "accuracy": 0.9,
            "answers": 60,
            "retention": 0.9,
            "reviews": 40,
        }

        fresca = build_territory(TerritoryInput(**base, days_since_studied=2))
        fria = build_territory(TerritoryInput(**base, days_since_studied=STALE_DAYS))

        assert fresca.state == TerritoryState.MASTERED
        assert fria.state == TerritoryState.NEEDS_REVIEW
        assert fria.mastery >= MASTERED_THRESHOLD
        assert str(STALE_DAYS) in fria.note

    def test_mapa_coloca_o_territorio_mais_fragil_primeiro(self):
        territories = build_map(
            [
                TerritoryInput(
                    subject_key="dominada",
                    subject_name="Dominada",
                    coverage=1.0,
                    studied_minutes=600,
                ),
                TerritoryInput(subject_key="nova", subject_name="Nova"),
                TerritoryInput(
                    subject_key="andamento",
                    subject_name="Andamento",
                    coverage=0.4,
                    studied_minutes=200,
                ),
                TerritoryInput(
                    subject_key="esfriando",
                    subject_name="Esfriando",
                    coverage=0.9,
                    studied_minutes=500,
                    days_since_studied=STALE_DAYS + 5,
                ),
            ]
        )

        assert [item.subject_key for item in territories] == [
            "esfriando",
            "andamento",
            "nova",
            "dominada",
        ]
