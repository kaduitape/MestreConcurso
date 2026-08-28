"""Gamificação: XP com razão, antiabuso, missões de sinal real e conquistas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    WEEKDAY_AVAILABILITY,
    RegisteredUser,
    create_admin,
    create_position_with_subjects,
    create_question,
    create_subject,
    create_user,
)


async def _answer(
    client: AsyncClient, user: RegisteredUser, question: dict[str, Any], *, correct: bool
) -> None:
    letter = next(
        item["letter"] for item in question["alternatives"] if item["is_correct"] is correct
    )
    response = await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=user.auth_header,
        json={"letter": letter, "time_seconds": 30},
    )
    assert response.status_code == 200, response.text


async def _finish_session(client: AsyncClient, user: RegisteredUser, *, minutes: int) -> None:
    """Abre, envelhece e encerra uma sessão de estudo com o foco desejado."""
    started = await client.post("/api/v1/study/sessions", headers=user.auth_header, json={})
    assert started.status_code == 201, started.text
    public_id = started.json()["public_id"]

    from sqlalchemy import select

    from app.db.session import get_session_factory
    from app.models.study import StudySession

    factory = get_session_factory()
    async with factory() as session:
        record = (
            await session.execute(select(StudySession).where(StudySession.public_id == public_id))
        ).scalar_one()
        record.started_at = datetime.now(UTC) - timedelta(minutes=minutes)
        await session.commit()

    finished = await client.post(
        f"/api/v1/study/sessions/{public_id}/finish", headers=user.auth_header, json={}
    )
    assert finished.status_code == 200, finished.text


# --------------------------------------------------------------------------- #
# Perfil
# --------------------------------------------------------------------------- #
async def test_new_candidate_starts_at_iron_because_there_is_nothing_to_measure(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game1@exemplo.com.br")

    response = await client.get("/api/v1/game/profile", headers=student.auth_header)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["level"]["level"] == 1
    assert body["level"]["xp_total"] == 0
    assert body["rank"]["slug"] == "FERRO"
    assert body["rank"]["score"] == 0
    # Os cinco sinais são declarados como ausentes, não como zero de desempenho.
    assert len(body["rank"]["missing_signals"]) == 5
    assert body["rank"]["coverage"] == 0
    for component in body["rank"]["components"]:
        assert component["available"] is False
        assert component["detail"]

    # O Mestre Score não é inventado: o lugar dele é declarado.
    assert body["master_score"] is None
    assert "Fase 9" in body["master_score_note"]


async def test_rank_components_sum_exactly_to_the_displayed_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game2@exemplo.com.br")
    subject = await create_subject(client, admin)
    for index in range(40):
        question = await create_question(
            client,
            admin,
            statement=f"Questão {index} para formar amostra de desempenho real",
            subject_public_id=subject["public_id"],
        )
        await _answer(client, admin, question, correct=index % 4 != 0)

    body = (await client.get("/api/v1/game/profile", headers=admin.auth_header)).json()
    rank = body["rank"]

    assert round(sum(item["points"] for item in rank["components"]), 4) == rank["score"]
    acerto = next(item for item in rank["components"] if item["key"] == "acerto")
    assert acerto["available"] is True
    assert acerto["points"] > 0
    assert "respostas" in acerto["detail"]


# --------------------------------------------------------------------------- #
# XP e razão contábil
# --------------------------------------------------------------------------- #
async def test_study_session_generates_a_ledger_entry_with_its_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game3@exemplo.com.br")
    await _finish_session(client, student, minutes=30)

    history = await client.get("/api/v1/game/xp/history", headers=student.auth_header)
    assert history.status_code == 200, history.text
    items = history.json()["items"]

    assert len(items) == 1
    entry = items[0]
    assert entry["event_kind"] == "STUDY_SESSION"
    assert entry["amount"] == 100
    assert "minutos de estudo com foco" in entry["reason"]
    assert entry["capped"] is False

    profile = (await client.get("/api/v1/game/profile", headers=student.auth_header)).json()
    # O saldo do perfil é a soma do razão.
    assert profile["level"]["xp_total"] == 100
    assert profile["xp_today"] == 100


async def test_very_short_session_earns_nothing_and_leaves_no_entry(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game4@exemplo.com.br")
    await _finish_session(client, student, minutes=2)

    history = await client.get("/api/v1/game/xp/history", headers=student.auth_header)
    assert history.json()["total"] == 0

    profile = (await client.get("/api/v1/game/profile", headers=student.auth_header)).json()
    assert profile["level"]["xp_total"] == 0


async def test_the_same_question_does_not_score_twice_in_a_day(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game5@exemplo.com.br")
    question = await create_question(
        client, admin, statement="Questão respondida duas vezes no mesmo dia"
    )

    await _answer(client, admin, question, correct=True)
    await _answer(client, admin, question, correct=True)

    history = await client.get("/api/v1/game/xp/history", headers=admin.auth_header)
    entries = [
        item for item in history.json()["items"] if item["event_kind"] == "QUESTIONS_ANSWERED"
    ]
    assert len(entries) == 1


async def test_an_answer_given_too_fast_does_not_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game6@exemplo.com.br")
    question = await create_question(client, admin, statement="Questão respondida sem ler")
    letter = next(item["letter"] for item in question["alternatives"] if item["is_correct"])

    await client.post(
        f"/api/v1/questions/{question['public_id']}/answer",
        headers=admin.auth_header,
        json={"letter": letter, "time_seconds": 1},
    )

    history = await client.get("/api/v1/game/xp/history", headers=admin.auth_header)
    assert history.json()["total"] == 0


async def test_daily_cap_is_recorded_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game7@exemplo.com.br")

    # O teto de estudo é 400 XP; cinco sessões de 30 min valeriam 500.
    for _ in range(5):
        await _finish_session(client, student, minutes=30)

    history = await client.get("/api/v1/game/xp/history", headers=student.auth_header)
    items = history.json()["items"]
    total = sum(item["amount"] for item in items)

    assert total == 400
    capped = [item for item in items if item["capped"]]
    assert capped, "o corte precisa virar linha, não sumir em silêncio"
    assert "teto diário" in capped[0]["cap_reason"]
    assert "continua contando" in capped[0]["cap_reason"]


async def test_simulation_finish_scores_once(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game8@exemplo.com.br")
    subject = await create_subject(client, admin)
    for index in range(12):
        await create_question(
            client,
            admin,
            statement=f"Questão {index} disponível para o simulado pontuado",
            subject_public_id=subject["public_id"],
        )

    created = await client.post(
        "/api/v1/simulations",
        headers=admin.auth_header,
        json={"kind": "CUSTOM", "questions_count": 12, "subject_public_id": subject["public_id"]},
    )
    assert created.status_code == 201, created.text
    started = await client.post(
        f"/api/v1/simulations/{created.json()['public_id']}/start", headers=admin.auth_header
    )
    attempt = started.json()["attempt"]["public_id"]

    finished = await client.post(
        f"/api/v1/simulations/attempts/{attempt}/finish", headers=admin.auth_header
    )
    assert finished.status_code == 200, finished.text
    # Encerrar de novo é idempotente e não repontua.
    await client.post(f"/api/v1/simulations/attempts/{attempt}/finish", headers=admin.auth_header)

    history = await client.get("/api/v1/game/xp/history", headers=admin.auth_header)
    entries = [
        item for item in history.json()["items"] if item["event_kind"] == "SIMULATION_FINISHED"
    ]
    assert len(entries) == 1
    assert entries[0]["amount"] == 300


# --------------------------------------------------------------------------- #
# Missões
# --------------------------------------------------------------------------- #
async def test_without_a_plan_no_mission_is_invented(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game9@exemplo.com.br")

    body = (await client.get("/api/v1/game/missions/today", headers=student.auth_header)).json()

    assert body["missions"] == []
    assert body["has_plan"] is False
    assert "Monte o seu plano" in body["empty_reason"]
    assert "missão inventada" in body["empty_reason"]


async def test_missions_are_born_from_real_signals_and_carry_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game10@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.game10@exemplo.com.br")

    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    await client.post("/api/v1/intelligence/priority/recompute", headers=student.auth_header)

    body = (await client.get("/api/v1/game/missions/today", headers=student.auth_header)).json()

    assert body["has_plan"] is True
    assert body["missions"], "com plano ativo, o dia precisa ter missão"
    for mission in body["missions"]:
        assert mission["rationale"], "toda missão carrega o número que a gerou"
        assert mission["xp_reward"] > 0
        assert mission["estimated_minutes"] > 0
        assert mission["status"] == "PENDING"

    # A disciplina de maior Priority Score vira missão, com o score citado.
    subject_mission = next(
        (item for item in body["missions"] if item["kind"] == "STUDY_SUBJECT"), None
    )
    assert subject_mission is not None
    assert "Priority Score" in subject_mission["rationale"]


async def test_mission_progress_comes_from_real_activity_and_can_be_claimed(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game11@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email="aluno.game11@exemplo.com.br")

    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    await client.post("/api/v1/intelligence/priority/recompute", headers=student.auth_header)

    board = (await client.get("/api/v1/game/missions/today", headers=student.auth_header)).json()
    mission = next(item for item in board["missions"] if item["kind"] == "STUDY_SUBJECT")

    # Resgatar antes de cumprir é recusado com o progresso real.
    early = await client.post(
        f"/api/v1/game/missions/{mission['public_id']}/claim", headers=student.auth_header
    )
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "mission_not_complete"

    await _finish_session(client, student, minutes=35)

    updated = (await client.get("/api/v1/game/missions/today", headers=student.auth_header)).json()
    done = next(item for item in updated["missions"] if item["kind"] == "STUDY_SUBJECT")
    assert done["current_value"] >= done["target_value"]
    assert done["status"] == "DONE"

    claimed = await client.post(
        f"/api/v1/game/missions/{done['public_id']}/claim", headers=student.auth_header
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["xp_awarded"] > 0

    # Resgatar duas vezes não repete o ganho.
    again = await client.post(
        f"/api/v1/game/missions/{done['public_id']}/claim", headers=student.auth_header
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "mission_already_claimed"


# --------------------------------------------------------------------------- #
# Sequência
# --------------------------------------------------------------------------- #
async def test_useful_study_starts_the_streak(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game12@exemplo.com.br")

    before = (await client.get("/api/v1/game/streak", headers=student.auth_header)).json()
    assert before["current"] == 0
    assert "começam a sua sequência" in before["message"]

    await _finish_session(client, student, minutes=25)

    after = (await client.get("/api/v1/game/streak", headers=student.auth_header)).json()
    assert after["current"] == 1
    assert after["shields_left"] == 2
    assert len(after["history"]) == 14


async def test_a_short_session_does_not_qualify_the_day(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game13@exemplo.com.br")
    await _finish_session(client, student, minutes=8)

    body = (await client.get("/api/v1/game/streak", headers=student.auth_header)).json()
    assert body["current"] == 0


async def test_streak_message_never_threatens(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game14@exemplo.com.br")
    body = (await client.get("/api/v1/game/streak", headers=student.auth_header)).json()

    for word in ("perdeu", "cuidado", "atenção", "não perca"):
        assert word not in body["message"].lower()


# --------------------------------------------------------------------------- #
# Conquistas
# --------------------------------------------------------------------------- #
async def test_secret_achievements_are_not_revealed_before_unlocking(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game15@exemplo.com.br")

    body = (await client.get("/api/v1/game/achievements", headers=student.auth_header)).json()

    assert body["secret_count"] > 0
    assert body["secret_unlocked"] == 0
    # A lista informa que existem secretas, sem revelar quais.
    assert all(item["is_secret"] is False for item in body["items"])


async def test_achievement_unlocks_on_the_real_metric_and_grants_xp_once(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game16@exemplo.com.br")
    await _finish_session(client, student, minutes=30)

    from app.services.game_engine import GameEngine

    async def unlock() -> list[str]:
        from sqlalchemy import select

        from app.db.session import get_session_factory
        from app.models.user import User

        factory = get_session_factory()
        async with factory() as session:
            user = (
                await session.execute(select(User).where(User.email == student.email))
            ).scalar_one()
            granted = await GameEngine(session).check_achievements(user)
            return [item.slug for item in granted]

    first = await unlock()
    assert "primeiro-estudo" in first

    # Repetir a verificação não concede de novo.
    assert await unlock() == []

    body = (await client.get("/api/v1/game/achievements", headers=student.auth_header)).json()
    primeiro = next(item for item in body["items"] if item["slug"] == "primeiro-estudo")
    assert primeiro["unlocked"] is True
    assert primeiro["unlocked_at"] is not None

    history = await client.get("/api/v1/game/xp/history", headers=student.auth_header)
    unlocked_entries = [
        item for item in history.json()["items"] if item["event_kind"] == "ACHIEVEMENT_UNLOCKED"
    ]
    assert len(unlocked_entries) == 1
    assert unlocked_entries[0]["amount"] == 50


async def test_progress_is_shown_for_visible_achievements(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game17@exemplo.com.br")
    for index in range(5):
        question = await create_question(
            client, admin, statement=f"Questão {index} contando para a conquista de volume"
        )
        await _answer(client, admin, question, correct=True)

    body = (await client.get("/api/v1/game/achievements", headers=admin.auth_header)).json()
    cem = next(item for item in body["items"] if item["slug"] == "cem-questoes")

    assert cem["current"] == 5
    assert cem["threshold"] == 100
    assert cem["ratio"] == 0.05
    assert cem["unlocked"] is False


# --------------------------------------------------------------------------- #
# Painel de regras
# --------------------------------------------------------------------------- #
async def test_rules_can_be_changed_without_deploy(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game18@exemplo.com.br")

    listed = await client.get("/api/v1/admin/game/rules", headers=admin.auth_header)
    assert listed.status_code == 200, listed.text
    keys = {item["key"] for item in listed.json()}
    assert "STUDY_SESSION" in keys

    updated = await client.put(
        "/api/v1/admin/game/rules/STUDY_SESSION",
        headers=admin.auth_header,
        json={"xp_value": 250},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["xp_value"] == 250

    student = await create_user(client, emails, email="aluno.game18@exemplo.com.br")
    await _finish_session(client, student, minutes=30)

    history = await client.get("/api/v1/game/xp/history", headers=student.auth_header)
    assert history.json()["items"][0]["amount"] == 250


async def test_a_disabled_rule_stops_scoring(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="game19@exemplo.com.br")
    await client.get("/api/v1/admin/game/rules", headers=admin.auth_header)
    await client.put(
        "/api/v1/admin/game/rules/STUDY_SESSION",
        headers=admin.auth_header,
        json={"is_enabled": False},
    )

    student = await create_user(client, emails, email="aluno.game19@exemplo.com.br")
    await _finish_session(client, student, minutes=30)

    history = await client.get("/api/v1/game/xp/history", headers=student.auth_header)
    assert history.json()["total"] == 0


async def test_candidate_cannot_edit_the_rules(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="game20@exemplo.com.br")
    response = await client.get("/api/v1/admin/game/rules", headers=student.auth_header)
    assert response.status_code == 403
