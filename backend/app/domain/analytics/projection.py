"""“Se a prova fosse hoje” — a estimativa mais perigosa do produto.

É a tela que um candidato mais quer ver e a que mais facilmente vira mentira.
Por isso ela obedece a quatro regras duras:

1. **Estima nota, nunca aprovação.** Não há probabilidade de passar, nem
   comparação com nota de corte — a plataforma não tem esse dado oficial, e
   inventá-lo seria o pior tipo de fabricação.
2. **Só estima o que tem amostra.** Disciplina sem respostas suficientes fica de
   fora, e a estimativa declara **qual fatia da prova ela cobre**.
3. **Sai sempre com faixa.** O número central vem acompanhado dos limites de
   Wilson propagados, porque uma nota estimada sem faixa é um chute com aparência
   de medição.
4. **Sem distribuição oficial, não há estimativa.** Se o edital não disse quantas
   questões cada disciplina tem, não há o que projetar.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.analytics.statistics import Confidence, weakest_confidence, wilson

# Amostra mínima por disciplina para ela entrar na estimativa.
MIN_SUBJECT_ATTEMPTS = 20

# Abaixo desta fatia da prova coberta, nenhum total é afirmado.
MIN_EXAM_COVERAGE = 0.50

#: A frase que acompanha a tela. Não é enfeite: é o item 40 do pedido.
DISCLAIMER = (
    "Esta é uma estimativa de acerto sobre o seu próprio histórico, não uma "
    "previsão de resultado. A plataforma não estima chance de aprovação."
)


@dataclass(frozen=True, slots=True)
class SubjectExam:
    """Uma disciplina da prova, como o edital a descreve."""

    subject_id: int | None
    name: str
    questions: int
    weight: float = 1.0
    is_eliminatory: bool = False
    #: Nota mínima exigida na disciplina, quando o edital define uma.
    min_score: float | None = None


@dataclass(frozen=True, slots=True)
class SubjectPerformance:
    subject_id: int | None
    correct: int
    attempts: int


@dataclass(frozen=True, slots=True)
class SubjectProjection:
    subject_id: int | None
    name: str
    questions: int
    weight: float
    is_eliminatory: bool
    #: Nulo quando a disciplina não entrou na conta.
    accuracy: float | None
    low: float | None
    high: float | None
    expected: float | None
    expected_low: float | None
    expected_high: float | None
    sample: int
    included: bool
    confidence: str
    detail: str
    #: Preenchido quando o piso do edital pode não ser alcançado.
    risk_note: str | None = None


@dataclass(frozen=True, slots=True)
class ExamProjection:
    total_questions: int
    #: Questões da prova cobertas por disciplinas com amostra.
    covered_questions: int
    coverage: float
    #: Nulos quando a cobertura é baixa demais para afirmar um total.
    expected: float | None = None
    expected_low: float | None = None
    expected_high: float | None = None
    expected_percent: float | None = None
    subjects: list[SubjectProjection] = field(default_factory=list)
    confidence: str = Confidence.NONE
    disclaimer: str = DISCLAIMER
    #: Motivo pelo qual não há total — ou pelo qual não há estimativa alguma.
    empty_reason: str | None = None

    @property
    def is_reliable(self) -> bool:
        return self.expected is not None


def project(exam: list[SubjectExam], performance: list[SubjectPerformance]) -> ExamProjection:
    """Projeta o acerto na prova a partir do desempenho real por disciplina."""
    total_questions = sum(item.questions for item in exam)
    if not exam or total_questions <= 0:
        return ExamProjection(
            total_questions=0,
            covered_questions=0,
            coverage=0.0,
            empty_reason=(
                "A prova do seu cargo ainda não tem distribuição de questões por "
                "disciplina no catálogo. Sem ela não há o que projetar."
            ),
        )

    by_subject = {item.subject_id: item for item in performance}
    projections: list[SubjectProjection] = []
    covered = 0
    weighted_value = 0.0
    weighted_low = 0.0
    weighted_high = 0.0
    confidences: list[str] = []

    for subject in exam:
        stats = by_subject.get(subject.subject_id)
        attempts = stats.attempts if stats else 0
        included = attempts >= MIN_SUBJECT_ATTEMPTS

        if not included:
            projections.append(
                SubjectProjection(
                    subject_id=subject.subject_id,
                    name=subject.name,
                    questions=subject.questions,
                    weight=subject.weight,
                    is_eliminatory=subject.is_eliminatory,
                    accuracy=None,
                    low=None,
                    high=None,
                    expected=None,
                    expected_low=None,
                    expected_high=None,
                    sample=attempts,
                    included=False,
                    confidence=Confidence.NONE,
                    detail=(
                        f"{attempts} de {MIN_SUBJECT_ATTEMPTS} respostas para esta disciplina "
                        "entrar na estimativa."
                    ),
                )
            )
            continue

        assert stats is not None
        interval = wilson(stats.correct, stats.attempts)
        expected = round(interval.value * subject.questions, 2)
        expected_low = round(interval.low * subject.questions, 2)
        expected_high = round(interval.high * subject.questions, 2)

        risk: str | None = None
        if subject.min_score is not None and expected_low < subject.min_score:
            risk = (
                f"O edital exige {subject.min_score:g} nesta disciplina e o limite inferior "
                f"da sua faixa é {expected_low:g}."
            )
        elif subject.is_eliminatory and interval.low < 0.5:
            risk = (
                "Disciplina eliminatória com faixa larga: o limite inferior está abaixo de "
                "metade das questões."
            )

        covered += subject.questions
        weighted_value += interval.value * subject.questions * subject.weight
        weighted_low += interval.low * subject.questions * subject.weight
        weighted_high += interval.high * subject.questions * subject.weight
        confidences.append(interval.confidence)

        projections.append(
            SubjectProjection(
                subject_id=subject.subject_id,
                name=subject.name,
                questions=subject.questions,
                weight=subject.weight,
                is_eliminatory=subject.is_eliminatory,
                accuracy=interval.value,
                low=interval.low,
                high=interval.high,
                expected=expected,
                expected_low=expected_low,
                expected_high=expected_high,
                sample=stats.attempts,
                included=True,
                confidence=interval.confidence,
                detail=(
                    f"{interval.value * 100:.0f}% em {stats.attempts} respostas · "
                    f"{expected:g} de {subject.questions} questões "
                    f"(faixa {expected_low:g}–{expected_high:g})"
                ),
                risk_note=risk,
            )
        )

    # Disciplina com maior risco primeiro; depois as que ficaram de fora.
    projections.sort(
        key=lambda item: (not item.included, item.risk_note is None, -(item.questions))
    )

    coverage = round(covered / total_questions, 4)
    if coverage < MIN_EXAM_COVERAGE:
        return ExamProjection(
            total_questions=total_questions,
            covered_questions=covered,
            coverage=coverage,
            subjects=projections,
            confidence=Confidence.NONE,
            empty_reason=(
                f"A estimativa cobriria apenas {coverage * 100:.0f}% das questões da prova. "
                f"Abaixo de {MIN_EXAM_COVERAGE * 100:.0f}% nenhum total é afirmado — responda "
                "mais questões das disciplinas listadas para a projeção passar a significar "
                "alguma coisa."
            ),
        )

    weakest = weakest_confidence(confidences)

    return ExamProjection(
        total_questions=total_questions,
        covered_questions=covered,
        coverage=coverage,
        expected=round(weighted_value, 2),
        expected_low=round(weighted_low, 2),
        expected_high=round(weighted_high, 2),
        expected_percent=round(weighted_value / covered, 4) if covered else None,
        subjects=projections,
        confidence=weakest,
    )
