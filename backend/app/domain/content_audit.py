"""O portão de qualidade: regras determinísticas sobre o conteúdo.

**Por que sem IA.** Um auditor que julga por modelo de linguagem não é
auditável: ele não repete o mesmo veredito sobre a mesma questão, não mostra a
conta e cobra token para dizer "parece bom". Aqui cada regra é uma função pura
com um nome, um limiar e uma evidência escrita — dá para discordar dela, e dá
para desligá-la pelo painel.

**Três severidades, e a terceira é a que falta na maioria dos sistemas:**

``BLOCKER``
    Impede a publicação. É defeito objetivo: questão sem gabarito, alternativa
    repetida, tópico fora do edital.

``WARNING``
    Aparece, não impede. É suspeita que precisa de olho humano — duas questões
    muito parecidas podem ser variação legítima.

``NOT_CHECKED``
    **O que não deu para conferir.** Um concurso sem edital analisado não
    permite dizer se o tópico está no programa; silenciar isso faria o laudo
    limpo parecer uma aprovação. Nunca bloqueia, e nunca some da tela.

O veredito é derivado das marcas, nunca acumulado: ``BLOCKED`` se houver
qualquer bloqueio, ``WARNED`` se houver aviso, ``CLEAN`` caso contrário — e
mesmo o limpo carrega quantos itens ficaram sem conferência.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    #: Não é defeito nem suspeita: é a ausência de insumo para julgar.
    NOT_CHECKED = "NOT_CHECKED"


class Verdict(StrEnum):
    CLEAN = "CLEAN"
    WARNED = "WARNED"
    BLOCKED = "BLOCKED"


class TargetKind(StrEnum):
    QUESTION = "QUESTION"
    TRAINING_LESSON = "TRAINING_LESSON"
    MIND_MAP = "MIND_MAP"


class RuleKey(StrEnum):
    ANSWER_KEY_MISSING = "question.answer_key_missing"
    ANSWER_KEY_AMBIGUOUS = "question.answer_key_ambiguous"
    ALTERNATIVE_REPEATED = "question.alternative_repeated"
    ALTERNATIVE_EMPTY = "question.alternative_empty"
    STATEMENT_TOO_SHORT = "question.statement_too_short"
    NEAR_DUPLICATE = "question.near_duplicate"
    TOPIC_OUTSIDE_NOTICE = "content.topic_outside_notice"
    NOT_LINKED_TO_CATALOG = "content.not_linked_to_catalog"
    AI_WITHOUT_HUMAN_REVIEW = "content.ai_without_human_review"
    BODY_EMPTY = "content.body_empty"


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """O padrão que o código traz. A tabela do painel vence este valor."""

    key: str
    label: str
    description: str
    severity: str
    applies_to: tuple[str, ...]
    config: Mapping[str, Any] = field(default_factory=dict)


_TODOS = (TargetKind.QUESTION, TargetKind.TRAINING_LESSON, TargetKind.MIND_MAP)

RULES: tuple[RuleSpec, ...] = (
    RuleSpec(
        RuleKey.ANSWER_KEY_MISSING,
        "Questão sem gabarito",
        "Nenhuma alternativa marcada como correta, ou discursiva sem resposta esperada.",
        Severity.BLOCKER,
        (TargetKind.QUESTION,),
    ),
    RuleSpec(
        RuleKey.ANSWER_KEY_AMBIGUOUS,
        "Mais de um gabarito",
        "Duas ou mais alternativas marcadas como corretas na mesma questão.",
        Severity.BLOCKER,
        (TargetKind.QUESTION,),
    ),
    RuleSpec(
        RuleKey.ALTERNATIVE_REPEATED,
        "Alternativa repetida",
        "Duas alternativas com o mesmo texto — uma delas está sobrando.",
        Severity.BLOCKER,
        (TargetKind.QUESTION,),
    ),
    RuleSpec(
        RuleKey.ALTERNATIVE_EMPTY,
        "Alternativa vazia",
        "Alternativa sem texto.",
        Severity.BLOCKER,
        (TargetKind.QUESTION,),
    ),
    RuleSpec(
        RuleKey.STATEMENT_TOO_SHORT,
        "Enunciado curto demais",
        "Enunciado abaixo do mínimo de caracteres — costuma ser recorte perdido na importação.",
        Severity.WARNING,
        (TargetKind.QUESTION,),
        {"min_chars": 40},
    ),
    RuleSpec(
        RuleKey.NEAR_DUPLICATE,
        "Questão quase igual a outra",
        "Enunciado muito parecido com o de outra questão da mesma disciplina.",
        Severity.WARNING,
        (TargetKind.QUESTION,),
        {"min_score": 0.85, "max_comparisons": 300},
    ),
    RuleSpec(
        RuleKey.TOPIC_OUTSIDE_NOTICE,
        "Tópico fora do edital",
        "O conteúdo está classificado num tópico que o edital analisado não cobra.",
        Severity.BLOCKER,
        _TODOS,
    ),
    RuleSpec(
        RuleKey.NOT_LINKED_TO_CATALOG,
        "Conteúdo sem vínculo",
        "Sem disciplina ou tópico, o conteúdo não chega a quem precisa dele.",
        Severity.WARNING,
        _TODOS,
    ),
    RuleSpec(
        RuleKey.AI_WITHOUT_HUMAN_REVIEW,
        "Gerado por IA sem conferência humana",
        "Conteúdo produzido por IA que nenhuma pessoa revisou antes da publicação.",
        Severity.BLOCKER,
        _TODOS,
    ),
    RuleSpec(
        RuleKey.BODY_EMPTY,
        "Conteúdo vazio",
        "Aula sem cena ou mapa sem painel.",
        Severity.BLOCKER,
        (TargetKind.TRAINING_LESSON, TargetKind.MIND_MAP),
    ),
)

RULE_BY_KEY: Mapping[str, RuleSpec] = {rule.key: rule for rule in RULES}


@dataclass(frozen=True, slots=True)
class RuleSetting:
    """A regra como está configurada agora — vem do banco, não do código."""

    key: str
    is_enabled: bool
    severity: str
    config: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, spec: RuleSpec) -> RuleSetting:
        return cls(key=spec.key, is_enabled=True, severity=spec.severity, config=dict(spec.config))


DEFAULT_SETTINGS: Mapping[str, RuleSetting] = {rule.key: RuleSetting.of(rule) for rule in RULES}


@dataclass(frozen=True, slots=True)
class Finding:
    rule: str
    severity: str
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditableAlternative:
    letter: str
    text: str
    is_correct: bool


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """Outra questão parecida, com a nota que o comparador deu."""

    public_id: str
    score: float


@dataclass(frozen=True, slots=True)
class AuditableQuestion:
    public_id: str
    kind: str
    origin: str
    statement: str
    explanation: str | None
    alternatives: tuple[AuditableAlternative, ...]
    subject_id: int | None
    topic_id: int | None
    generated_by_ai: bool
    human_reviewed: bool
    duplicates: tuple[DuplicateCandidate, ...] = ()
    #: ``None`` quer dizer "não havia edital analisado para comparar".
    topic_in_notice: bool | None = None


@dataclass(frozen=True, slots=True)
class AuditableMaterial:
    public_id: str
    kind: str
    title: str
    #: Cenas da aula ou painéis do mapa.
    body_count: int
    subject_id: int | None
    topic_id: int | None
    generated_by_ai: bool
    human_reviewed: bool
    topic_in_notice: bool | None = None


# --------------------------------------------------------------------------- #
# Execução das regras
# --------------------------------------------------------------------------- #
def _active(settings: Mapping[str, RuleSetting], key: str, target_kind: str) -> RuleSetting | None:
    """A regra configurada, se ela estiver ligada e valer para este tipo."""
    spec = RULE_BY_KEY[key]
    if target_kind not in spec.applies_to:
        return None
    setting = settings.get(key, DEFAULT_SETTINGS[key])
    return setting if setting.is_enabled else None


def _normalized(value: str) -> str:
    return " ".join(value.split()).strip().lower()


def _shared_findings(
    settings: Mapping[str, RuleSetting],
    *,
    target_kind: str,
    subject_id: int | None,
    topic_id: int | None,
    generated_by_ai: bool,
    human_reviewed: bool,
    topic_in_notice: bool | None,
) -> list[Finding]:
    findings: list[Finding] = []

    vinculo = _active(settings, RuleKey.NOT_LINKED_TO_CATALOG, target_kind)
    if vinculo and subject_id is None and topic_id is None:
        findings.append(
            Finding(
                rule=vinculo.key,
                severity=vinculo.severity,
                message="Sem disciplina e sem tópico: este conteúdo não chega a quem estuda.",
            )
        )

    edital = _active(settings, RuleKey.TOPIC_OUTSIDE_NOTICE, target_kind)
    if edital:
        if topic_in_notice is False:
            findings.append(
                Finding(
                    rule=edital.key,
                    severity=edital.severity,
                    message="O tópico não aparece no conteúdo programático do edital analisado.",
                    evidence={"topic_id": topic_id},
                )
            )
        elif topic_in_notice is None:
            # Dizer que não deu para conferir é o ponto: um laudo limpo que
            # escondeu a lacuna vira aprovação que ninguém deu.
            findings.append(
                Finding(
                    rule=edital.key,
                    severity=Severity.NOT_CHECKED,
                    message=(
                        "Não há edital analisado com conteúdo programático para comparar, "
                        "então o tópico não foi conferido."
                    ),
                )
            )

    revisao = _active(settings, RuleKey.AI_WITHOUT_HUMAN_REVIEW, target_kind)
    if revisao and generated_by_ai and not human_reviewed:
        findings.append(
            Finding(
                rule=revisao.key,
                severity=revisao.severity,
                message=(
                    "Conteúdo gerado por IA precisa da conferência de uma pessoa antes de publicar."
                ),
            )
        )

    return findings


def audit_question(
    question: AuditableQuestion, settings: Mapping[str, RuleSetting] | None = None
) -> list[Finding]:
    settings = settings or DEFAULT_SETTINGS
    findings: list[Finding] = []
    discursiva = question.kind == "DISCURSIVE"

    sem_gabarito = _active(settings, RuleKey.ANSWER_KEY_MISSING, TargetKind.QUESTION)
    if sem_gabarito:
        if discursiva:
            if not (question.explanation or "").strip():
                findings.append(
                    Finding(
                        rule=sem_gabarito.key,
                        severity=sem_gabarito.severity,
                        message="Questão discursiva sem resposta esperada escrita.",
                    )
                )
        elif not any(item.is_correct for item in question.alternatives):
            findings.append(
                Finding(
                    rule=sem_gabarito.key,
                    severity=sem_gabarito.severity,
                    message="Nenhuma alternativa está marcada como correta.",
                )
            )

    ambiguo = _active(settings, RuleKey.ANSWER_KEY_AMBIGUOUS, TargetKind.QUESTION)
    corretas = [item.letter for item in question.alternatives if item.is_correct]
    if ambiguo and not discursiva and len(corretas) > 1:
        findings.append(
            Finding(
                rule=ambiguo.key,
                severity=ambiguo.severity,
                message=f"{len(corretas)} alternativas estão marcadas como corretas.",
                evidence={"letters": corretas},
            )
        )

    vazia = _active(settings, RuleKey.ALTERNATIVE_EMPTY, TargetKind.QUESTION)
    if vazia:
        sem_texto = [item.letter for item in question.alternatives if not item.text.strip()]
        if sem_texto:
            findings.append(
                Finding(
                    rule=vazia.key,
                    severity=vazia.severity,
                    message="Há alternativa sem texto.",
                    evidence={"letters": sem_texto},
                )
            )

    repetida = _active(settings, RuleKey.ALTERNATIVE_REPEATED, TargetKind.QUESTION)
    if repetida:
        vistos: dict[str, str] = {}
        repetidas: list[list[str]] = []
        for item in question.alternatives:
            texto = _normalized(item.text)
            if not texto:
                continue
            if texto in vistos:
                repetidas.append([vistos[texto], item.letter])
            else:
                vistos[texto] = item.letter
        if repetidas:
            findings.append(
                Finding(
                    rule=repetida.key,
                    severity=repetida.severity,
                    message="Duas alternativas têm o mesmo texto.",
                    evidence={"pairs": repetidas},
                )
            )

    curto = _active(settings, RuleKey.STATEMENT_TOO_SHORT, TargetKind.QUESTION)
    if curto:
        minimo = int(curto.config.get("min_chars", RULE_BY_KEY[curto.key].config["min_chars"]))
        tamanho = len(_normalized(question.statement))
        if tamanho < minimo:
            findings.append(
                Finding(
                    rule=curto.key,
                    severity=curto.severity,
                    message=(
                        f"O enunciado tem {tamanho} caracteres; o mínimo configurado é {minimo}."
                    ),
                    evidence={"length": tamanho, "min_chars": minimo},
                )
            )

    duplicada = _active(settings, RuleKey.NEAR_DUPLICATE, TargetKind.QUESTION)
    if duplicada:
        limiar = float(
            duplicada.config.get("min_score", RULE_BY_KEY[duplicada.key].config["min_score"])
        )
        parecidas = [item for item in question.duplicates if item.score >= limiar]
        if parecidas:
            findings.append(
                Finding(
                    rule=duplicada.key,
                    severity=duplicada.severity,
                    message="Há questão muito parecida já cadastrada.",
                    evidence={
                        "matches": [
                            {"public_id": item.public_id, "score": round(item.score, 3)}
                            for item in parecidas
                        ],
                        "min_score": limiar,
                    },
                )
            )

    findings.extend(
        _shared_findings(
            settings,
            target_kind=TargetKind.QUESTION,
            subject_id=question.subject_id,
            topic_id=question.topic_id,
            generated_by_ai=question.generated_by_ai,
            human_reviewed=question.human_reviewed,
            topic_in_notice=question.topic_in_notice,
        )
    )
    return findings


def audit_material(
    material: AuditableMaterial, settings: Mapping[str, RuleSetting] | None = None
) -> list[Finding]:
    settings = settings or DEFAULT_SETTINGS
    findings: list[Finding] = []

    vazio = _active(settings, RuleKey.BODY_EMPTY, material.kind)
    if vazio and material.body_count <= 0:
        findings.append(
            Finding(
                rule=vazio.key,
                severity=vazio.severity,
                message=(
                    "Mapa sem painel não vai para quem estuda."
                    if material.kind == TargetKind.MIND_MAP
                    else "Aula sem cena não vai para quem estuda."
                ),
            )
        )

    findings.extend(
        _shared_findings(
            settings,
            target_kind=material.kind,
            subject_id=material.subject_id,
            topic_id=material.topic_id,
            generated_by_ai=material.generated_by_ai,
            human_reviewed=material.human_reviewed,
            topic_in_notice=material.topic_in_notice,
        )
    )
    return findings


def verdict_of(findings: Sequence[Finding]) -> str:
    """O veredito é derivado das marcas, nunca acumulado."""
    if any(item.severity == Severity.BLOCKER for item in findings):
        return Verdict.BLOCKED
    if any(item.severity == Severity.WARNING for item in findings):
        return Verdict.WARNED
    return Verdict.CLEAN


def blockers(findings: Sequence[Finding]) -> list[Finding]:
    return [item for item in findings if item.severity == Severity.BLOCKER]


def not_checked(findings: Sequence[Finding]) -> list[Finding]:
    return [item for item in findings if item.severity == Severity.NOT_CHECKED]
