"""As regras do auditor.

O teste mais importante deste arquivo não é o do defeito encontrado — é o do
que **não deu para conferir**. Um laudo limpo que escondeu a lacuna vira uma
aprovação que ninguém deu, e é assim que conteúdo errado chega a quem estuda.
"""

from __future__ import annotations

from app.domain.content_audit import (
    DEFAULT_SETTINGS,
    AuditableAlternative,
    AuditableMaterial,
    AuditableQuestion,
    DuplicateCandidate,
    RuleKey,
    RuleSetting,
    Severity,
    TargetKind,
    Verdict,
    audit_material,
    audit_question,
    blockers,
    not_checked,
    verdict_of,
)


def _alternativas(*marcadas: bool) -> tuple[AuditableAlternative, ...]:
    letras = "ABCDE"
    return tuple(
        AuditableAlternative(letter=letras[i], text=f"Alternativa {letras[i]}", is_correct=marcada)
        for i, marcada in enumerate(marcadas)
    )


def _questao(**overrides: object) -> AuditableQuestion:
    base = {
        "public_id": "q1",
        "kind": "MULTIPLE_CHOICE",
        "origin": "OFFICIAL",
        "statement": "Assinale a alternativa correta sobre o princípio da legalidade na "
        "Administração Pública.",
        "explanation": None,
        "alternatives": _alternativas(True, False, False, False),
        "subject_id": 1,
        "topic_id": 2,
        "generated_by_ai": False,
        "human_reviewed": True,
        "duplicates": (),
        "topic_in_notice": True,
    }
    base.update(overrides)
    return AuditableQuestion(**base)  # type: ignore[arg-type]


def _rules(key: str, **changes: object) -> dict[str, RuleSetting]:
    settings = dict(DEFAULT_SETTINGS)
    atual = settings[key]
    settings[key] = RuleSetting(
        key=atual.key,
        is_enabled=bool(changes.get("is_enabled", atual.is_enabled)),
        severity=str(changes.get("severity", atual.severity)),
        config=dict(changes.get("config", atual.config)),  # type: ignore[arg-type]
    )
    return settings


# --------------------------------------------------------------------------- #
# A questão limpa
# --------------------------------------------------------------------------- #
def test_a_sound_question_passes_without_findings() -> None:
    assert audit_question(_questao()) == []
    assert verdict_of([]) == Verdict.CLEAN


# --------------------------------------------------------------------------- #
# Gabarito
# --------------------------------------------------------------------------- #
def test_a_question_without_an_answer_key_is_blocked() -> None:
    findings = audit_question(_questao(alternatives=_alternativas(False, False, False)))

    assert [item.rule for item in findings] == [RuleKey.ANSWER_KEY_MISSING]
    assert verdict_of(findings) == Verdict.BLOCKED


def test_two_answer_keys_are_blocked_and_the_letters_are_written() -> None:
    findings = audit_question(_questao(alternatives=_alternativas(True, True, False)))

    achado = next(item for item in findings if item.rule == RuleKey.ANSWER_KEY_AMBIGUOUS)
    assert achado.severity == Severity.BLOCKER
    assert achado.evidence["letters"] == ["A", "B"]


def test_a_discursive_question_needs_a_written_answer() -> None:
    sem_resposta = audit_question(_questao(kind="DISCURSIVE", alternatives=(), explanation=None))
    com_resposta = audit_question(
        _questao(kind="DISCURSIVE", alternatives=(), explanation="Espera-se que o candidato…")
    )

    assert [item.rule for item in sem_resposta] == [RuleKey.ANSWER_KEY_MISSING]
    assert com_resposta == []


# --------------------------------------------------------------------------- #
# Alternativas
# --------------------------------------------------------------------------- #
def test_two_alternatives_with_the_same_text_are_blocked() -> None:
    """A letra repetida já é barrada na entrada; o texto repetido não era."""
    alternativas = (
        AuditableAlternative("A", "A lei autoriza", True),
        AuditableAlternative("B", "a   LEI   autoriza ", False),
        AuditableAlternative("C", "A lei proíbe", False),
    )

    findings = audit_question(_questao(alternatives=alternativas))

    achado = next(item for item in findings if item.rule == RuleKey.ALTERNATIVE_REPEATED)
    assert achado.severity == Severity.BLOCKER
    assert achado.evidence["pairs"] == [["A", "B"]]


def test_an_empty_alternative_is_blocked() -> None:
    alternativas = (
        AuditableAlternative("A", "Certa", True),
        AuditableAlternative("B", "   ", False),
    )

    findings = audit_question(_questao(alternatives=alternativas))

    achado = next(item for item in findings if item.rule == RuleKey.ALTERNATIVE_EMPTY)
    assert achado.evidence["letters"] == ["B"]


def test_empty_alternatives_do_not_count_as_repeated() -> None:
    """Duas vazias são um defeito só, e ele já tem nome próprio."""
    alternativas = (
        AuditableAlternative("A", "Certa", True),
        AuditableAlternative("B", "", False),
        AuditableAlternative("C", "  ", False),
    )

    regras = [item.rule for item in audit_question(_questao(alternatives=alternativas))]

    assert RuleKey.ALTERNATIVE_EMPTY in regras
    assert RuleKey.ALTERNATIVE_REPEATED not in regras


# --------------------------------------------------------------------------- #
# Enunciado e duplicata
# --------------------------------------------------------------------------- #
def test_a_short_statement_warns_without_blocking() -> None:
    findings = audit_question(_questao(statement="Qual a capital?"))

    achado = next(item for item in findings if item.rule == RuleKey.STATEMENT_TOO_SHORT)
    assert achado.severity == Severity.WARNING
    assert verdict_of(findings) == Verdict.WARNED


def test_the_short_statement_threshold_comes_from_the_settings() -> None:
    """Limite de regra mora no banco, nunca no código."""
    questao = _questao(statement="Enunciado de tamanho médio aqui.")

    assert (
        audit_question(questao, _rules(RuleKey.STATEMENT_TOO_SHORT, config={"min_chars": 10})) == []
    )
    apertado = audit_question(
        questao, _rules(RuleKey.STATEMENT_TOO_SHORT, config={"min_chars": 500})
    )
    assert [item.rule for item in apertado] == [RuleKey.STATEMENT_TOO_SHORT]


def test_a_near_duplicate_warns_and_names_the_other_question() -> None:
    """Parecida não é igual: pode ser variação legítima, então avisa sem barrar."""
    findings = audit_question(
        _questao(
            duplicates=(DuplicateCandidate("q-antiga", 0.93), DuplicateCandidate("q-outra", 0.42))
        )
    )

    achado = next(item for item in findings if item.rule == RuleKey.NEAR_DUPLICATE)
    assert achado.severity == Severity.WARNING
    assert [match["public_id"] for match in achado.evidence["matches"]] == ["q-antiga"]


# --------------------------------------------------------------------------- #
# O que não deu para conferir
# --------------------------------------------------------------------------- #
def test_without_a_notice_the_topic_is_reported_as_not_checked() -> None:
    """A regra mais importante do auditor: silêncio aqui viraria aprovação."""
    findings = audit_question(_questao(topic_in_notice=None))

    achado = next(item for item in findings if item.rule == RuleKey.TOPIC_OUTSIDE_NOTICE)
    assert achado.severity == Severity.NOT_CHECKED
    assert "não foi conferido" in achado.message
    # Não bloqueia, não vira aviso — e continua à vista.
    assert verdict_of(findings) == Verdict.CLEAN
    assert len(not_checked(findings)) == 1


def test_a_topic_outside_the_notice_is_blocked() -> None:
    findings = audit_question(_questao(topic_in_notice=False))

    achado = next(item for item in findings if item.rule == RuleKey.TOPIC_OUTSIDE_NOTICE)
    assert achado.severity == Severity.BLOCKER
    assert verdict_of(findings) == Verdict.BLOCKED


# --------------------------------------------------------------------------- #
# IA sem conferência
# --------------------------------------------------------------------------- #
def test_ai_content_without_human_review_is_blocked() -> None:
    findings = audit_question(_questao(generated_by_ai=True, human_reviewed=False))

    assert [item.rule for item in blockers(findings)] == [RuleKey.AI_WITHOUT_HUMAN_REVIEW]


def test_ai_content_reviewed_by_a_person_passes() -> None:
    assert audit_question(_questao(generated_by_ai=True, human_reviewed=True)) == []


# --------------------------------------------------------------------------- #
# Material: aula e mapa
# --------------------------------------------------------------------------- #
def _material(**overrides: object) -> AuditableMaterial:
    base = {
        "public_id": "m1",
        "kind": TargetKind.TRAINING_LESSON,
        "title": "Crase sem mistério",
        "body_count": 8,
        "subject_id": 1,
        "topic_id": 2,
        "generated_by_ai": True,
        "human_reviewed": True,
        "topic_in_notice": True,
    }
    base.update(overrides)
    return AuditableMaterial(**base)  # type: ignore[arg-type]


def test_an_empty_lesson_is_blocked() -> None:
    findings = audit_material(_material(body_count=0))

    achado = next(item for item in findings if item.rule == RuleKey.BODY_EMPTY)
    assert "cena" in achado.message


def test_an_empty_mind_map_says_panel_not_scene() -> None:
    findings = audit_material(_material(kind=TargetKind.MIND_MAP, body_count=0))

    achado = next(item for item in findings if item.rule == RuleKey.BODY_EMPTY)
    assert "painel" in achado.message


def test_content_without_any_link_warns() -> None:
    findings = audit_material(_material(subject_id=None, topic_id=None, topic_in_notice=None))

    regras = {item.rule: item.severity for item in findings}
    assert regras[RuleKey.NOT_LINKED_TO_CATALOG] == Severity.WARNING


def test_a_question_rule_does_not_fire_on_a_lesson() -> None:
    """Cada regra diz a que tipo se aplica; aula não tem gabarito."""
    regras = [item.rule for item in audit_material(_material(body_count=0))]

    assert RuleKey.ANSWER_KEY_MISSING not in regras


# --------------------------------------------------------------------------- #
# Configuração
# --------------------------------------------------------------------------- #
def test_a_disabled_rule_stops_firing() -> None:
    quebrada = _questao(alternatives=_alternativas(False, False))

    assert audit_question(quebrada) != []
    assert audit_question(quebrada, _rules(RuleKey.ANSWER_KEY_MISSING, is_enabled=False)) == []


def test_severity_can_be_lowered_without_touching_the_code() -> None:
    quebrada = _questao(alternatives=_alternativas(False, False))

    findings = audit_question(
        quebrada, _rules(RuleKey.ANSWER_KEY_MISSING, severity=Severity.WARNING)
    )

    assert verdict_of(findings) == Verdict.WARNED
    assert blockers(findings) == []
