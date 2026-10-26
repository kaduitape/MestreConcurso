"""Diferença entre duas versões de edital.

Dois testes pesam mais que os outros: o que cobra que **nada é apagado** quando
um tópico sai do edital, e o que cobra que a **procedência viaja junto** — data
conferida no PDF e data deduzida pela IA não podem chegar iguais na tela.
"""

from __future__ import annotations

from datetime import date

from app.domain.notice_diff import (
    ChangeKind,
    ChangeScope,
    ContentRef,
    EventEntry,
    FactEntry,
    ImpactAction,
    PositionEntry,
    ProgrammeSnapshot,
    SubjectEntry,
    TopicEntry,
    diff,
    impacts,
    summarize,
)


def _snapshot(**overrides: object) -> ProgrammeSnapshot:
    base: dict[str, object] = {
        "positions": (PositionEntry("Analista Judiciário", "SUPERIOR", 1399478, vacancies=150),),
        "subjects": (SubjectEntry("Português", subject_id=1, weight="2.00", questions_count=20),),
        "topics": (TopicEntry("Crase", "Português", topic_id=10),),
        "events": (
            EventEntry(
                "EXAM", "Prova objetiva", date(2026, 5, 10), None, evidence_level="OFFICIAL"
            ),
        ),
        "facts": (FactEntry("vagas", "Vagas", "30", evidence_level="OFFICIAL"),),
    }
    base.update(overrides)
    return ProgrammeSnapshot(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Nada mudou
# --------------------------------------------------------------------------- #
def test_two_identical_versions_produce_no_change() -> None:
    assert diff(_snapshot(), _snapshot()) == []


def test_a_renamed_subject_linked_to_the_same_catalogue_entry_is_not_a_change() -> None:
    """O edital pode escrever "Língua Portuguesa" onde antes escrevia "Português"."""
    antes = _snapshot(subjects=(SubjectEntry("Português", subject_id=1, weight="2.00"),))
    depois = _snapshot(subjects=(SubjectEntry("Língua Portuguesa", subject_id=1, weight="2.00"),))

    assert [item for item in diff(antes, depois) if item.scope == ChangeScope.SUBJECT] == []


# --------------------------------------------------------------------------- #
# Disciplinas e pesos
# --------------------------------------------------------------------------- #
def test_a_new_subject_is_reported_with_its_weight() -> None:
    depois = _snapshot(
        subjects=(
            SubjectEntry("Português", subject_id=1, weight="2.00", questions_count=20),
            SubjectEntry("Direito Penal", subject_id=2, weight="3.00", questions_count=15),
        )
    )

    mudancas = [item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.SUBJECT]

    assert len(mudancas) == 1
    assert mudancas[0].kind == ChangeKind.ADDED
    assert "peso 3.00" in (mudancas[0].after or "")


def test_a_changed_weight_shows_both_sides() -> None:
    depois = _snapshot(
        subjects=(SubjectEntry("Português", subject_id=1, weight="4.00", questions_count=20),)
    )

    mudanca = next(item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.SUBJECT)

    assert mudanca.kind == ChangeKind.CHANGED
    assert "peso 2.00" in (mudanca.before or "")
    assert "peso 4.00" in (mudanca.after or "")


def test_a_removed_subject_is_reported() -> None:
    mudanca = next(
        item
        for item in diff(_snapshot(), _snapshot(subjects=()))
        if item.scope == ChangeScope.SUBJECT
    )

    assert mudanca.kind == ChangeKind.REMOVED


# --------------------------------------------------------------------------- #
# Datas — onde a retificação dói no candidato
# --------------------------------------------------------------------------- #
def test_a_moved_exam_date_shows_the_old_and_the_new() -> None:
    depois = _snapshot(
        events=(
            EventEntry(
                "EXAM", "Prova objetiva", date(2026, 6, 21), None, evidence_level="OFFICIAL"
            ),
        )
    )

    mudanca = next(item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.EVENT)

    assert mudanca.kind == ChangeKind.CHANGED
    assert mudanca.before == "10/05/2026"
    assert mudanca.after == "21/06/2026"


def test_a_period_is_written_with_both_ends() -> None:
    antes = _snapshot(events=())
    depois = _snapshot(
        events=(
            EventEntry(
                "REGISTRATION_START",
                "Inscrições",
                date(2026, 3, 1),
                date(2026, 3, 20),
                evidence_level="OFFICIAL",
            ),
        )
    )

    mudanca = next(item for item in diff(antes, depois) if item.scope == ChangeScope.EVENT)

    assert mudanca.after == "01/03/2026 a 20/03/2026"


def test_the_evidence_level_travels_with_the_change() -> None:
    """Data conferida no PDF e data deduzida não podem chegar iguais na tela."""
    depois = _snapshot(
        events=(
            EventEntry(
                "EXAM", "Prova objetiva", date(2026, 6, 21), None, evidence_level="INFERRED"
            ),
        )
    )

    mudanca = next(item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.EVENT)

    assert mudanca.evidence_level == "INFERRED"
    assert summarize([mudanca], []).inferred == 1


def test_a_change_confirmed_in_the_document_is_not_counted_as_inferred() -> None:
    depois = _snapshot(
        events=(
            EventEntry(
                "EXAM", "Prova objetiva", date(2026, 6, 21), None, evidence_level="CONFIRMED"
            ),
        )
    )

    mudancas = diff(_snapshot(), depois)

    assert summarize(mudancas, []).inferred == 0


# --------------------------------------------------------------------------- #
# Dados do edital
# --------------------------------------------------------------------------- #
def test_a_changed_fact_shows_both_values() -> None:
    depois = _snapshot(facts=(FactEntry("vagas", "Vagas", "45", evidence_level="OFFICIAL"),))

    mudanca = next(item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.FACT)

    assert (mudanca.before, mudanca.after) == ("30", "45")


# --------------------------------------------------------------------------- #
# Impacto — e a regra de não apagar nada
# --------------------------------------------------------------------------- #
def test_content_of_a_removed_topic_is_orphaned_never_deleted() -> None:
    """O teste que sustenta a fase."""
    mudancas = diff(_snapshot(), _snapshot(topics=()))
    conteudo = {10: [ContentRef("TRAINING_LESSON", "aula-crase", "Crase sem mistério", 10)]}

    achados = impacts(mudancas, conteudo)

    assert len(achados) == 1
    assert achados[0].action == ImpactAction.ORPHANED
    assert achados[0].content is not None
    assert achados[0].content.public_id == "aula-crase"
    assert "quem decide o destino" in achados[0].reason


def test_a_removed_topic_without_content_produces_no_impact() -> None:
    mudancas = diff(_snapshot(), _snapshot(topics=()))

    assert impacts(mudancas, {}) == []


def test_a_new_topic_without_content_is_reported_as_missing() -> None:
    depois = _snapshot(
        topics=(
            TopicEntry("Crase", "Português", topic_id=10),
            TopicEntry("Regência", "Português", topic_id=11),
        )
    )

    achados = impacts(diff(_snapshot(), depois), {})

    assert [item.action for item in achados] == [ImpactAction.MISSING]
    assert achados[0].topic_label == "Regência"


def test_a_new_topic_that_already_has_content_is_not_reported_as_missing() -> None:
    """Reaproveitamento da Fase 4: o tópico é novo no edital, o conteúdo não."""
    depois = _snapshot(
        topics=(
            TopicEntry("Crase", "Português", topic_id=10),
            TopicEntry("Regência", "Português", topic_id=11),
        )
    )
    conteudo = {11: [ContentRef("MIND_MAP", "mapa-regencia", "Regência", 11)]}

    assert impacts(diff(_snapshot(), depois), conteudo) == []


# --------------------------------------------------------------------------- #
# Resumo
# --------------------------------------------------------------------------- #
def test_the_summary_is_derived_from_the_changes() -> None:
    depois = _snapshot(
        subjects=(),
        topics=(TopicEntry("Regência", "Português", topic_id=11),),
        facts=(FactEntry("vagas", "Vagas", "45", evidence_level="OFFICIAL"),),
    )
    mudancas = diff(_snapshot(), depois)

    resumo = summarize(mudancas, impacts(mudancas, {}))

    assert resumo.added == 1  # o tópico novo
    assert resumo.removed == 2  # a disciplina e o tópico antigo
    assert resumo.changed == 1  # o número de vagas
    assert resumo.missing == 1
    assert resumo.orphaned == 0


# --------------------------------------------------------------------------- #
# Cargos
# --------------------------------------------------------------------------- #
def test_a_new_position_is_reported_with_its_numbers() -> None:
    """Cargo novo abre um concurso que ninguém estava acompanhando."""
    depois = _snapshot(
        positions=(
            PositionEntry("Analista Judiciário", "SUPERIOR", 1399478, vacancies=150),
            PositionEntry("Oficial de Justiça", "SUPERIOR", 900000, vacancies=20, cr_vacancies=5),
        )
    )
    mudancas = [item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.POSITION]

    assert len(mudancas) == 1
    assert mudancas[0].kind == ChangeKind.ADDED
    assert mudancas[0].label == "Oficial de Justiça"
    assert "20 vaga(s)" in (mudancas[0].after or "")
    # Cadastro de reserva aparece separado, não somado às vagas imediatas.
    assert "CR 5" in (mudancas[0].after or "")


def test_a_removed_position_says_who_needs_to_know() -> None:
    """Quem escolheu o cargo removido perdeu o concurso: isso tem de aparecer."""
    depois = _snapshot(positions=())
    mudancas = [item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.POSITION]

    assert len(mudancas) == 1
    assert mudancas[0].kind == ChangeKind.REMOVED
    assert mudancas[0].label == "Analista Judiciário"
    assert "quem escolheu este cargo precisa saber" in (mudancas[0].detail or "")


def test_more_vacancies_in_the_same_position_shows_both_sides() -> None:
    depois = _snapshot(
        positions=(PositionEntry("Analista Judiciário", "SUPERIOR", 1399478, vacancies=200),)
    )
    mudancas = [item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.POSITION]

    assert len(mudancas) == 1
    assert mudancas[0].kind == ChangeKind.CHANGED
    assert "150 vaga(s)" in (mudancas[0].before or "")
    assert "200 vaga(s)" in (mudancas[0].after or "")


def test_a_position_renamed_only_in_case_or_accent_is_not_a_change() -> None:
    """Edital reescrevendo o nome não é cargo novo."""
    depois = _snapshot(
        positions=(PositionEntry("ANALISTA JUDICIARIO", "SUPERIOR", 1399478, vacancies=150),)
    )
    assert [item for item in diff(_snapshot(), depois) if item.scope == ChangeScope.POSITION] == []
