"""Mapa de incidência, DNA da banca e Priority Score."""

from __future__ import annotations

from httpx import AsyncClient

from app.domain.intelligence.incidence import MIN_BOARD_QUESTIONS
from tests.conftest import CapturingDispatcher
from tests.factories import (
    WEEKDAY_AVAILABILITY,
    RegisteredUser,
    create_admin,
    create_position_with_subjects,
    create_question,
    create_subject,
    create_user,
    question_payload,
)


async def _fill_bank(
    client: AsyncClient,
    admin: RegisteredUser,
    *,
    subject_public_id: str,
    board_slug: str,
    count: int,
    prefix: str,
    year: int = 2024,
    difficulty: str = "MEDIUM",
) -> None:
    """Importa um lote de questões da banca — a amostra do mapa de incidência."""
    lote = [
        question_payload(
            statement=f"{prefix} — enunciado número {index} sobre o conteúdo cobrado",
            difficulty=difficulty,
            year=year,
        )
        for index in range(count)
    ]
    response = await client.post(
        "/api/v1/admin/questions/import",
        headers=admin.auth_header,
        json={
            "questions": lote,
            "subject_public_id": subject_public_id,
            "board_slug": board_slug,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == count


async def test_incidence_map_is_empty_until_there_is_sample(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel1@exemplo.com.br")
    subject = await create_subject(client, admin)
    await create_question(client, admin, statement="Questão isolada sobre direito penal geral")
    student = await create_user(client, emails, email="aluno.intel1@exemplo.com.br")

    from tests.factories import create_board

    board = await create_board(client, admin)
    await _fill_bank(
        client,
        admin,
        subject_public_id=subject["public_id"],
        board_slug=board["slug"],
        count=MIN_BOARD_QUESTIONS - 5,
        prefix="Amostra curta",
    )

    recomputed = await client.post(
        f"/api/v1/admin/intelligence/recompute?board={board['slug']}", headers=admin.auth_header
    )
    assert recomputed.status_code == 200, recomputed.text
    result = recomputed.json()[0]
    assert result["incidence_rows"] == 0
    assert result["incidence_blocked"] is not None
    assert str(MIN_BOARD_QUESTIONS) in result["incidence_blocked"]

    response = await client.get(
        f"/api/v1/intelligence/incidence/{board['slug']}", headers=student.auth_header
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == []
    # A tela recebe o motivo, não um vazio silencioso.
    assert body["empty_reason"]


async def test_incidence_map_reports_shares_with_their_sample(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel2@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.intel2@exemplo.com.br")

    from tests.factories import create_board

    board = await create_board(client, admin)
    penal = await create_subject(client, admin, name="Direito Penal")
    portugues = await create_subject(client, admin, name="Português")

    await _fill_bank(
        client,
        admin,
        subject_public_id=penal["public_id"],
        board_slug=board["slug"],
        count=30,
        prefix="Direito Penal",
    )
    await _fill_bank(
        client,
        admin,
        subject_public_id=portugues["public_id"],
        board_slug=board["slug"],
        count=10,
        prefix="Português",
    )

    await client.post(
        f"/api/v1/admin/intelligence/recompute?board={board['slug']}", headers=admin.auth_header
    )

    response = await client.get(
        f"/api/v1/intelligence/incidence/{board['slug']}", headers=student.auth_header
    )
    body = response.json()
    assert body["board_questions_count"] == 40
    assert body["empty_reason"] is None

    rows = {row["subject_name"]: row for row in body["rows"]}
    assert rows["Direito Penal"]["incidence_pct"] == 0.75
    assert rows["Direito Penal"]["questions_count"] == 30
    assert rows["Português"]["incidence_pct"] == 0.25
    # Um ano só na amostra: não se afirma tendência.
    assert rows["Direito Penal"]["trend"] is None


async def test_board_dna_is_computed_from_the_question_bank(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel3@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.intel3@exemplo.com.br")

    from tests.factories import create_board

    board = await create_board(client, admin)
    subject = await create_subject(client, admin)
    await _fill_bank(
        client,
        admin,
        subject_public_id=subject["public_id"],
        board_slug=board["slug"],
        count=30,
        prefix="Difíceis",
        difficulty="HARD",
    )
    await _fill_bank(
        client,
        admin,
        subject_public_id=subject["public_id"],
        board_slug=board["slug"],
        count=10,
        prefix="Fáceis",
        difficulty="EASY",
    )

    await client.post(
        f"/api/v1/admin/intelligence/recompute?board={board['slug']}", headers=admin.auth_header
    )

    response = await client.get(
        f"/api/v1/intelligence/board-dna/{board['slug']}", headers=student.auth_header
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["empty_reason"] is None

    metrics = {item["metric_slug"]: item for item in body["metrics"]}
    assert metrics["difficulty_mix"]["detail"] == {"EASY": 0.25, "HARD": 0.75}
    # A amostra viaja junto com o número.
    assert metrics["difficulty_mix"]["sample_questions"] == 40
    assert metrics["question_kind_mix"]["detail"] == {"MULTIPLE_CHOICE": 1.0}


async def test_priority_without_plan_explains_instead_of_returning_zero(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.intel4@exemplo.com.br")

    response = await client.post(
        "/api/v1/intelligence/priority/recompute", headers=student.auth_header
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["items"] == []
    assert any("plano" in note for note in body["notes"])


async def test_priority_contributions_sum_to_the_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel5@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.intel5@exemplo.com.br")

    created = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    assert created.status_code == 201, created.text

    response = await client.post(
        "/api/v1/intelligence/priority/recompute", headers=student.auth_header
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 3

    for item in body["items"]:
        assert sum(part["points"] for part in item["contributions"]) == item["score"]
        assert all(part["detail"] for part in item["contributions"])
        # Sem questões respondidas nem incidência, os sinais ausentes são declarados.
        assert "seu_desempenho" in item["missing_signals"]
        assert item["coverage"] < 1.0

    # A lista sai ordenada pela urgência.
    scores = [item["score"] for item in body["items"]]
    assert scores == sorted(scores, reverse=True)

    stored = await client.get("/api/v1/intelligence/priority", headers=student.auth_header)
    assert stored.status_code == 200
    assert len(stored.json()["items"]) == 3


async def test_priority_uses_performance_once_there_are_answers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel6@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.intel6@exemplo.com.br")

    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )

    # A disciplina do plano precisa existir no banco de questões para o vínculo.
    subjects = await client.get(
        "/api/v1/admin/catalog/subjects?page=1&page_size=50", headers=admin.auth_header
    )
    penal = next(item for item in subjects.json()["items"] if item["name"] == "Direito Penal")

    for index in range(6):
        question = await create_question(
            client,
            admin,
            statement=f"Questão {index} de direito penal para medir desempenho real",
            subject_public_id=penal["public_id"],
        )
        wrong = next(item["letter"] for item in question["alternatives"] if not item["is_correct"])
        answered = await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": wrong},
        )
        assert answered.status_code == 200, answered.text

    response = await client.post(
        "/api/v1/intelligence/priority/recompute", headers=student.auth_header
    )
    items = {item["label"]: item for item in response.json()["items"]}
    penal_item = items["Direito Penal"]

    performance = next(
        part for part in penal_item["contributions"] if part["key"] == "seu_desempenho"
    )
    assert performance["points"] > 0
    assert "0,0% de acerto em 6 respostas" in performance["detail"]
    assert "seu_desempenho" not in penal_item["missing_signals"]
    assert sum(part["points"] for part in penal_item["contributions"]) == penal_item["score"]

    # Errando tudo em Direito Penal, ela sobe acima das demais.
    assert penal_item["score"] == max(item["score"] for item in items.values())


async def test_recompute_requires_permission(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.intel7@exemplo.com.br")
    response = await client.post(
        "/api/v1/admin/intelligence/recompute", headers=student.auth_header
    )
    assert response.status_code == 403


async def test_plan_regeneration_leans_on_the_priority_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel8@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.intel8@exemplo.com.br")

    baseline = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    assert baseline.status_code == 201, baseline.text
    before = {item["name"]: item for item in baseline.json()["shares"]}
    # Sem Priority Score, o plano é a linha de base do edital e diz isso.
    assert "prioridade_por_desempenho" not in before["Informática"]["breakdown"]

    subjects = await client.get(
        "/api/v1/admin/catalog/subjects?page=1&page_size=50", headers=admin.auth_header
    )
    informatica = next(item for item in subjects.json()["items"] if item["name"] == "Informática")

    # Erra tudo em Informática: a disciplina mais fraca do edital sobe na prioridade.
    for index in range(8):
        question = await create_question(
            client,
            admin,
            statement=f"Questão {index} de informática que o candidato erra sistematicamente",
            subject_public_id=informatica["public_id"],
        )
        wrong = next(item["letter"] for item in question["alternatives"] if not item["is_correct"])
        await client.post(
            f"/api/v1/questions/{question['public_id']}/answer",
            headers=student.auth_header,
            json={"letter": wrong},
        )

    await client.post("/api/v1/intelligence/priority/recompute", headers=student.auth_header)

    regenerated = await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    assert regenerated.status_code == 201, regenerated.text
    after = {item["name"]: item for item in regenerated.json()["shares"]}

    assert after["Informática"]["minutes"] > before["Informática"]["minutes"]
    breakdown = after["Informática"]["breakdown"]
    assert breakdown["prioridade_por_desempenho"] > 0
    assert breakdown["ajuste_de_tempo"] > 0
    # O peso do edital continua mandando: o ajuste inclina, não vira a mesa.
    assert after["Direito Penal"]["minutes"] > after["Informática"]["minutes"]


async def test_adaptive_simulation_needs_the_priority_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="intel9@exemplo.com.br")
    subject = await create_subject(client, admin)
    for index in range(6):
        await create_question(
            client,
            admin,
            statement=f"Questão {index} disponível para o simulado adaptativo",
            subject_public_id=subject["public_id"],
        )
    student = await create_user(client, emails, email="aluno.intel9@exemplo.com.br")

    refused = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "ADAPTIVE", "questions_count": 5},
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "no_questions_available"
    assert "Priority Score" in refused.json()["error"]["message"]
