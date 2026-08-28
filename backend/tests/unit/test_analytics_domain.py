"""Fase 9: estatística, Mestre Score, projeção, caminho e painéis.

O critério de aceite da fase é duro e específico: **todo gráfico tem uma decisão
associada e todo intervalo é visível**. Os testes abaixo cobram exatamente isso,
além da regra que sustenta o Mestre Score: XP não entra, e o número vem com faixa.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import date

import pytest

from app.domain.analytics.dashboards import (
    DayEffort,
    SubjectCoverage,
    WeeklyAttempts,
    accuracy_evolution,
    consistency,
    coverage_by_subject,
    retention,
)
from app.domain.analytics.master_score import (
    MIN_ATTEMPTS,
    MIN_REVIEWS,
    SCALE,
    MasterScoreInput,
    band_for,
    compute,
)
from app.domain.analytics.path import (
    STRONG_ACCURACY,
    ActionKind,
    build,
)
from app.domain.analytics.projection import (
    MIN_EXAM_COVERAGE,
    MIN_SUBJECT_ATTEMPTS,
    SubjectExam,
    SubjectPerformance,
    project,
)
from app.domain.analytics.statistics import (
    SAMPLE_HIGH,
    SAMPLE_LOW,
    Component,
    Confidence,
    combine,
    confidence_for,
    largest_remainder,
    wilson,
)


class TestWilson:
    def test_valores_conhecidos(self):
        """Confere contra o intervalo de Wilson publicado para 70/100."""
        interval = wilson(70, 100)

        assert interval.value == 0.7
        assert interval.low == pytest.approx(0.6042, abs=1e-3)
        assert interval.high == pytest.approx(0.7811, abs=1e-3)

    def test_sem_amostra_a_faixa_e_tudo(self):
        """Zero de zero não é zero por cento: é não saber."""
        interval = wilson(0, 0)

        assert interval.low == 0.0
        assert interval.high == 1.0
        assert interval.confidence == Confidence.NONE

    def test_uma_resposta_certa_nao_vira_dominio(self):
        interval = wilson(1, 1)

        assert interval.value == 1.0
        assert interval.low < 0.3, "uma resposta não sustenta afirmar domínio"

    def test_a_faixa_nunca_sai_de_zero_e_um(self):
        for successes, total in ((0, 3), (3, 3), (1, 2), (99, 100)):
            interval = wilson(successes, total)
            assert 0.0 <= interval.low <= interval.high <= 1.0

    def test_mais_amostra_estreita_a_faixa(self):
        estreita = wilson(700, 1000)
        larga = wilson(7, 10)

        assert estreita.width < larga.width

    def test_a_confianca_sobe_com_a_amostra(self):
        assert confidence_for(0) == Confidence.NONE
        assert confidence_for(SAMPLE_LOW - 1) == Confidence.LOW
        assert confidence_for(SAMPLE_LOW) == Confidence.MEDIUM
        assert confidence_for(SAMPLE_HIGH) == Confidence.HIGH


class TestCombine:
    def _component(self, key: str, weight: float, successes: int, total: int) -> Component:
        interval = wilson(successes, total) if total else None
        return Component(
            key=key,
            label=key,
            weight=weight,
            interval=interval,
            available=total > 0,
            detail="",
        )

    def test_sinal_ausente_reescala_em_vez_de_penalizar(self):
        composite = combine(
            [
                self._component("a", 0.5, 80, 100),
                self._component("b", 0.5, 0, 0),
            ]
        )

        assert composite.available_weight == 0.5
        assert composite.value == pytest.approx(0.8, abs=0.01)
        assert composite.missing == ["b"]

    def test_a_confianca_do_composto_e_a_do_sinal_mais_fragil(self):
        composite = combine(
            [
                self._component("solida", 0.5, 400, 500),
                self._component("fraca", 0.5, 4, 5),
            ]
        )

        assert composite.confidence == Confidence.LOW

    def test_sem_sinal_algum_nao_ha_composto(self):
        composite = combine([self._component("a", 1.0, 0, 0)])

        assert composite.available_weight == 0.0
        assert composite.confidence == Confidence.NONE
        assert composite.high == 1.0


class TestLargestRemainder:
    def test_as_parcelas_somam_o_total_exibido(self):
        parts = largest_remainder([0.333, 0.333, 0.334], total=1000)

        assert sum(parts) == 1000

    def test_lista_vazia_nao_quebra(self):
        assert largest_remainder([], total=100) == []


class TestMasterScore:
    def test_xp_nao_existe_na_entrada_do_calculo(self):
        """A separação é estrutural: não há campo de XP para preencher."""
        campos = {item.name for item in fields(MasterScoreInput)}

        assert not any("xp" in item for item in campos)
        assert not any("level" in item for item in campos)

    def test_candidato_novo_nao_recebe_nota_zero(self):
        score = compute(MasterScoreInput())

        assert score.value == 0
        assert score.empty_reason is not None
        assert score.confidence == Confidence.NONE
        assert len(score.missing_signals) == 5
        for component in score.components:
            assert component.available is False
            assert component.detail, "cada sinal diz quanto falta"

    def test_as_parcelas_somam_exatamente_o_score(self):
        score = compute(
            MasterScoreInput(
                correct=210,
                attempts=300,
                recalled=80,
                reviews=100,
                coverage=0.46,
                planned_minutes=6000,
                has_plan=True,
                simulation_correct=45,
                simulation_questions=60,
                active_days=14,
            )
        )

        assert score.components_sum == score.value
        assert 0 < score.value <= SCALE

    def test_o_score_sai_sempre_com_faixa(self):
        score = compute(MasterScoreInput(correct=21, attempts=30))

        assert score.low < score.value < score.high
        assert "Wilson" in score.interval_note
        assert "não é probabilidade de aprovação" in score.interval_note

    def test_amostra_insuficiente_nao_entra_e_e_declarada(self):
        score = compute(
            MasterScoreInput(
                correct=MIN_ATTEMPTS - 2,
                attempts=MIN_ATTEMPTS - 1,
                recalled=MIN_REVIEWS - 2,
                reviews=MIN_REVIEWS - 1,
            )
        )

        assert score.value == 0
        assert "acerto" in score.missing_signals
        assert "retencao" in score.missing_signals

    def test_o_peso_disponivel_e_declarado_quando_falta_sinal(self):
        score = compute(MasterScoreInput(correct=210, attempts=300))

        assert score.available_weight == pytest.approx(0.30)
        assert score.value > 0, "um sinal sozinho ainda produz score, reescalado"
        assert score.confidence != Confidence.NONE

    def test_o_score_pode_cair(self):
        antes = compute(MasterScoreInput(correct=280, attempts=300))
        depois = compute(MasterScoreInput(correct=280, attempts=400))

        assert depois.value < antes.value, "errar mais derruba o número"

    def test_as_faixas_de_leitura_cobrem_toda_a_escala(self):
        for value in (0, 249, 250, 640, 999, 1000):
            band, note = band_for(value)
            assert band and note


class TestProjection:
    def _exam(self) -> list[SubjectExam]:
        return [
            SubjectExam(1, "Português", 20),
            SubjectExam(2, "Direito Penal", 30, weight=2.0, is_eliminatory=True, min_score=15),
            SubjectExam(3, "Informática", 10),
        ]

    def test_sem_distribuicao_oficial_nao_ha_projecao(self):
        result = project([], [SubjectPerformance(1, 10, 20)])

        assert result.expected is None
        assert result.is_reliable is False
        assert "distribuição de questões" in (result.empty_reason or "")

    def test_a_tela_declara_que_nao_estima_aprovacao(self):
        result = project(self._exam(), [SubjectPerformance(1, 14, 20)])

        assert "não estima chance de aprovação" in result.disclaimer

    def test_disciplina_sem_amostra_fica_de_fora_com_o_motivo(self):
        result = project(
            self._exam(),
            [
                SubjectPerformance(1, 70, 100),
                SubjectPerformance(2, 40, 80),
                SubjectPerformance(3, 2, 5),
            ],
        )
        informatica = next(item for item in result.subjects if item.name == "Informática")

        assert informatica.included is False
        assert informatica.expected is None
        assert str(MIN_SUBJECT_ATTEMPTS) in informatica.detail

    def test_a_cobertura_da_estimativa_e_declarada(self):
        result = project(
            self._exam(),
            [SubjectPerformance(1, 70, 100), SubjectPerformance(2, 40, 80)],
        )

        assert result.covered_questions == 50
        assert result.total_questions == 60
        assert result.coverage == pytest.approx(0.8333, abs=1e-3)

    def test_cobertura_baixa_nao_afirma_total(self):
        result = project(self._exam(), [SubjectPerformance(1, 14, 20)])

        assert result.expected is None
        assert result.is_reliable is False
        assert f"{MIN_EXAM_COVERAGE * 100:.0f}%" in (result.empty_reason or "")
        assert result.subjects, "as disciplinas continuam listadas"

    def test_a_estimativa_sai_com_faixa(self):
        result = project(
            self._exam(),
            [SubjectPerformance(1, 70, 100), SubjectPerformance(2, 40, 80)],
        )

        assert result.expected_low is not None
        assert result.expected_low < result.expected < result.expected_high

    def test_o_piso_do_edital_vira_alerta_quando_a_faixa_nao_o_alcanca(self):
        result = project(
            self._exam(),
            [SubjectPerformance(1, 70, 100), SubjectPerformance(2, 40, 80)],
        )
        penal = next(item for item in result.subjects if item.name == "Direito Penal")

        assert penal.risk_note is not None
        assert "15" in penal.risk_note
        assert result.subjects[0].name == "Direito Penal", "o risco vem primeiro"


class TestPath:
    def _projections(self):
        return project(
            [
                SubjectExam(1, "Português", 20),
                SubjectExam(2, "Direito Penal", 30, weight=2.0),
                SubjectExam(3, "Informática", 10),
            ],
            [
                SubjectPerformance(1, 90, 100),
                SubjectPerformance(2, 40, 80),
                SubjectPerformance(3, 2, 5),
            ],
        ).subjects

    def test_sem_projecao_nao_ha_caminho(self):
        path = build([])

        assert path.steps == []
        assert path.empty_reason is not None

    def test_todo_passo_carrega_o_numero_que_o_gerou(self):
        path = build(self._projections())

        assert path.steps
        for step in path.steps:
            assert step.evidence, "recomendação sem número é palpite"
            assert step.action

    def test_disciplina_sem_amostra_vira_acao_de_medir(self):
        path = build(self._projections())
        passo = next(item for item in path.steps if item.subject_name == "Informática")

        assert passo.kind == ActionKind.MEASURE
        assert passo.questions_at_stake == 0.0
        assert "15 questões" in passo.action

    def test_disciplina_consolidada_vira_manutencao(self):
        path = build(self._projections())
        passo = next(item for item in path.steps if item.subject_name == "Português")

        assert STRONG_ACCURACY <= 0.9, "o teste supõe 90% acima do limiar"
        assert passo.kind == ActionKind.MAINTAIN

    def test_a_ordem_segue_o_que_coloca_mais_questoes_em_jogo(self):
        path = build(self._projections())

        assert path.steps[0].subject_name == "Direito Penal"
        assert path.steps[0].kind == ActionKind.IMPROVE
        assert path.steps[0].questions_at_stake == pytest.approx(30.0)

    def test_o_caminho_nao_promete_aprovacao(self):
        path = build(self._projections())
        texto = " ".join(
            [path.disclaimer, *(f"{item.action} {item.evidence}" for item in path.steps)]
        ).lower()

        for proibido in ("você será aprovado", "garante aprovação", "chance de passar"):
            assert proibido not in texto
        assert "não é garantia" in path.disclaimer


class TestDashboards:
    def test_todo_grafico_carrega_uma_decisao(self):
        """É o critério de aceite da fase, cobrado inclusive nos casos vazios."""
        charts = [
            accuracy_evolution([]),
            coverage_by_subject([]),
            consistency([]),
            retention([]),
            accuracy_evolution(
                [
                    WeeklyAttempts(date(2026, 3, 2), 30, 50),
                    WeeklyAttempts(date(2026, 3, 9), 40, 50),
                ]
            ),
            coverage_by_subject([SubjectCoverage("Português", 300, 600)]),
            consistency([DayEffort(date(2026, 3, 2), 90, True)]),
        ]

        for chart in charts:
            assert chart.decision, f"{chart.key} não declara para que serve"
            assert chart.title
            assert chart.unit

    def test_grafico_vazio_explica_a_ausencia_em_vez_de_desenhar_zeros(self):
        chart = accuracy_evolution([WeeklyAttempts(date(2026, 3, 2), 3, 5)])

        assert chart.points == []
        assert chart.empty_reason is not None

    def test_cada_ponto_de_proporcao_traz_faixa_e_amostra(self):
        chart = accuracy_evolution(
            [
                WeeklyAttempts(date(2026, 3, 2), 3, 5),
                WeeklyAttempts(date(2026, 3, 9), 240, 300),
            ]
        )

        for point in chart.points:
            assert point.low is not None and point.high is not None
            assert point.low <= point.value <= point.high
            assert point.sample > 0

        # Amostra pequena produz faixa larga — e é isso que a tela deve mostrar.
        assert (chart.points[0].high - chart.points[0].low) > (
            chart.points[1].high - chart.points[1].low
        )

    def test_os_pontos_saem_em_ordem_cronologica(self):
        chart = accuracy_evolution(
            [
                WeeklyAttempts(date(2026, 3, 16), 10, 20),
                WeeklyAttempts(date(2026, 3, 2), 10, 20),
                WeeklyAttempts(date(2026, 3, 9), 10, 20),
            ]
        )
        dias = [point.day for point in chart.points]

        assert dias == sorted(dias)

    def test_cobertura_declara_que_nao_e_dominio(self):
        chart = coverage_by_subject([SubjectCoverage("Português", 300, 600)])

        assert chart.points[0].value == 0.5
        assert "não é domínio" in chart.note
