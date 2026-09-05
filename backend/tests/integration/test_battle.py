"""Batalha RPG ponta a ponta.

A batalha é uma rodada de desafio com outra apresentação. Estes testes cobram
justamente isso: que ela **reusa** a mecânica existente (respostas reais,
estatísticas, XP, limite de plano) e acrescenta só o combate — cujo estado é
derivado das respostas, nunca acumulado.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    create_admin,
    create_question,
    create_user,
)


async def _stock(client: AsyncClient, admin: RegisteredUser, *, total: int, prefix: str) -> None:
    for index in range(total):
        await create_question(
            client, admin, statement=f"{prefix} — enunciado {index} com texto suficiente."
        )


async def _long_stock(client: AsyncClient, admin: RegisteredUser, *, total: int) -> None:
    """Questões com alternativas longas, para exercitar o layout compacto."""
    longa = (
        "Legislar privativamente sobre direito tributário, financeiro, "
        "penitenciário, econômico e urbanístico, conforme a Constituição."
    )
    for index in range(total):
        await client.post(
            "/api/v1/admin/questions",
            headers=admin.auth_header,
            json={
                "statement": f"Competência privativa — enunciado {index} com texto suficiente.",
                "difficulty": "MEDIUM",
                "alternatives": [
                    {
                        "letter": letter,
                        "content": f"{longa} Variação {letter}.",
                        "is_correct": letter == "A",
                        "feedback": f"Comentário da alternativa {letter}.",
                    }
                    for letter in ("A", "B", "C", "D")
                ],
            },
        )


async def _start(client: AsyncClient, student: RegisteredUser, **params: Any) -> dict[str, Any]:
    query = "&".join(f"{key}={value}" for key, value in params.items())
    response = await client.post(
        f"/api/v1/game/battle{'?' + query if query else ''}", headers=student.auth_header
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _answer(
    client: AsyncClient, student: RegisteredUser, battle: dict[str, Any], *, correct: bool
) -> dict[str, Any]:
    question = battle["run"]["question"]
    letter = (
        "A"
        if correct
        else next(item["letter"] for item in question["alternatives"] if item["letter"] != "A")
    )
    response = await client.post(
        f"/api/v1/game/battle/{battle['run']['public_id']}/answer",
        headers=student.auth_header,
        json={
            "question_public_id": question["public_id"],
            "letter": letter,
            "time_seconds": 20,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Largada
# --------------------------------------------------------------------------- #
async def test_the_battle_reuses_the_challenge_run(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg1@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Batalha")
    student = await create_user(client, emails, email="aluno.rpg1@exemplo.com.br")

    battle = await _start(client, student)

    assert battle["run"]["mode"] == "BATTLE"
    assert battle["run"]["mode_name"] == "Batalha RPG"
    assert battle["run"]["question"] is not None
    # A rodada aparece no mesmo lugar das outras: nada foi recriado em paralelo.
    current = (
        await client.get("/api/v1/game/challenges/current", headers=student.auth_header)
    ).json()
    assert current["public_id"] == battle["run"]["public_id"]


async def test_without_enough_questions_the_battle_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg2@exemplo.com.br")
    await _stock(client, admin, total=3, prefix="Banco curto")
    student = await create_user(client, emails, email="aluno.rpg2@exemplo.com.br")

    response = await client.post("/api/v1/game/battle", headers=student.auth_header)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "not_enough_questions"


async def test_the_battle_counts_against_the_plan_limit(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O limite de desafios do plano já vale aqui — nada foi contornado."""
    admin = await create_admin(client, emails, email="rpg3@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Limite")
    student = await create_user(client, emails, email="aluno.rpg3@exemplo.com.br")

    await client.put(
        "/api/v1/admin/billing/plans/gratuito",
        headers=admin.auth_header,
        json={
            "entitlements": [
                {"feature": "challenges", "is_enabled": True, "limit_value": 1, "period": "DAY"}
            ]
        },
    )
    battle = await _start(client, student)
    await client.post(
        f"/api/v1/game/challenges/runs/{battle['run']['public_id']}/finish?abandon=true",
        headers=student.auth_header,
    )

    blocked = await client.post("/api/v1/game/battle", headers=student.auth_header)

    assert blocked.status_code == 402
    assert blocked.json()["error"]["code"] == "quota_exceeded"


# --------------------------------------------------------------------------- #
# Combate
# --------------------------------------------------------------------------- #
async def test_the_battle_starts_with_both_sides_at_full_health(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg4@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Vida cheia")
    student = await create_user(client, emails, email="aluno.rpg4@exemplo.com.br")

    status = (await _start(client, student))["status"]

    assert status["player_hp"] == status["player_max_hp"] == 100
    assert status["enemy_hp"] == status["enemy_max_hp"]
    assert status["enemy_max_hp"] > 0
    assert status["is_over"] is False
    assert status["outcome_reason"] is None


async def test_hitting_the_right_answer_damages_the_enemy(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg5@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Acerto")
    student = await create_user(client, emails, email="aluno.rpg5@exemplo.com.br")

    battle = await _start(client, student)
    antes = battle["status"]["enemy_hp"]
    result = await _answer(client, student, battle, correct=True)

    assert result["is_correct"] is True
    assert result["damage_target"] == "enemy"
    assert result["damage"] > 0
    assert result["battle"]["status"]["enemy_hp"] == antes - result["damage"]
    assert result["battle"]["status"]["player_hp"] == 100, "acertar não custa vida"


async def test_missing_lets_the_correct_answers_monster_strike_back(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Item 11: quem ataca é o monstro da alternativa correta."""
    admin = await create_admin(client, emails, email="rpg6@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Erro")
    student = await create_user(client, emails, email="aluno.rpg6@exemplo.com.br")

    battle = await _start(client, student)
    result = await _answer(client, student, battle, correct=False)

    assert result["is_correct"] is False
    assert result["damage_target"] == "player"
    assert result["correct_letter"] == "A", "a tela precisa saber qual monstro ataca"
    assert result["battle"]["status"]["player_hp"] == 100 - result["damage"]
    assert result["battle"]["status"]["enemy_hp"] == battle["status"]["enemy_hp"]


async def test_the_state_is_derived_from_the_answers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Reler a batalha não muda nada: o HP sai das respostas, não de um contador."""
    admin = await create_admin(client, emails, email="rpg7@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Derivado")
    student = await create_user(client, emails, email="aluno.rpg7@exemplo.com.br")

    battle = await _start(client, student)
    result = await _answer(client, student, battle, correct=True)
    depois = result["battle"]["status"]

    for _ in range(3):
        releitura = (
            await client.get(
                f"/api/v1/game/battle/{battle['run']['public_id']}",
                headers=student.auth_header,
            )
        ).json()
        assert releitura["status"]["enemy_hp"] == depois["enemy_hp"]
        assert releitura["status"]["player_hp"] == depois["player_hp"]


async def test_victory_when_the_enemy_falls(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg8@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Vitória")
    student = await create_user(client, emails, email="aluno.rpg8@exemplo.com.br")

    battle = await _start(client, student)
    status = battle["status"]
    while not status["is_over"]:
        result = await _answer(client, student, battle, correct=True)
        battle = result["battle"]
        status = battle["status"]

    assert status["victory"] is True
    assert status["enemy_hp"] == 0
    assert status["outcome_reason"] == "O inimigo caiu."


async def test_defeat_when_the_warrior_falls(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg9@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Derrota")
    student = await create_user(client, emails, email="aluno.rpg9@exemplo.com.br")

    battle = await _start(client, student)
    status = battle["status"]
    while not status["is_over"]:
        result = await _answer(client, student, battle, correct=False)
        battle = result["battle"]
        status = battle["status"]

    assert status["defeat"] is True
    assert status["player_hp"] == 0
    assert "não aguentou" in status["outcome_reason"]


async def test_the_answers_feed_the_real_statistics(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Resposta de batalha é resposta de verdade: conta no perfil como as outras."""
    admin = await create_admin(client, emails, email="rpg10@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Estatística")
    student = await create_user(client, emails, email="aluno.rpg10@exemplo.com.br")

    battle = await _start(client, student)
    for _ in range(2):
        battle = (await _answer(client, student, battle, correct=True))["battle"]

    profile = (await client.get("/api/v1/game/profile", headers=student.auth_header)).json()
    assert profile["metrics"]["questions_answered"] == 2


# --------------------------------------------------------------------------- #
# Monstros e layout
# --------------------------------------------------------------------------- #
async def test_every_alternative_gets_a_monster(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg11@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Monstros")
    student = await create_user(client, emails, email="aluno.rpg11@exemplo.com.br")

    battle = await _start(client, student)
    letras = [item["letter"] for item in battle["run"]["question"]["alternatives"]]

    assert [item["letter"] for item in battle["monsters"]] == letras
    assert battle["enemy_species"]
    assert battle["enemy_name"]
    for monstro in battle["monsters"]:
        assert monstro["shape"], "a silhueta precisa estar declarada"
        assert monstro["color_token"]


async def test_the_enemy_is_stable_across_readings(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Sortear a cada leitura trocaria a cara do inimigo no meio da batalha."""
    admin = await create_admin(client, emails, email="rpg12@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Estável")
    student = await create_user(client, emails, email="aluno.rpg12@exemplo.com.br")

    battle = await _start(client, student)
    releitura = (
        await client.get(
            f"/api/v1/game/battle/{battle['run']['public_id']}", headers=student.auth_header
        )
    ).json()

    assert releitura["enemy_species"] == battle["enemy_species"]
    assert [item["variant"] for item in releitura["monsters"]] == [
        item["variant"] for item in battle["monsters"]
    ]


async def test_short_answers_get_the_arena(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg13@exemplo.com.br")
    for index in range(10):
        await client.post(
            "/api/v1/admin/questions",
            headers=admin.auth_header,
            json={
                "statement": f"Qual é a capital do Brasil? Enunciado {index} completo.",
                "difficulty": "MEDIUM",
                "alternatives": [
                    {"letter": "A", "content": "Brasília", "is_correct": True},
                    {"letter": "B", "content": "São Paulo", "is_correct": False},
                    {"letter": "C", "content": "Salvador", "is_correct": False},
                    {"letter": "D", "content": "Recife", "is_correct": False},
                ],
            },
        )
    student = await create_user(client, emails, email="aluno.rpg13@exemplo.com.br")

    battle = await _start(client, student)

    assert battle["layout"] == "monster-arena"
    assert battle["layout_reason"]


async def test_long_answers_get_the_compact_layout(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg14@exemplo.com.br")
    await _long_stock(client, admin, total=10)
    student = await create_user(client, emails, email="aluno.rpg14@exemplo.com.br")

    battle = await _start(client, student)

    assert battle["layout"] == "compact-answer"
    assert "caracteres" in battle["layout_reason"]


async def test_the_same_question_can_change_layout_on_mobile(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Item 4: no celular há menos espaço horizontal."""
    admin = await create_admin(client, emails, email="rpg15@exemplo.com.br")
    for index in range(10):
        await client.post(
            "/api/v1/admin/questions",
            headers=admin.auth_header,
            json={
                "statement": f"Competência — enunciado {index} com texto suficiente.",
                "difficulty": "MEDIUM",
                "alternatives": [
                    {
                        "letter": "A",
                        "content": "Competência privativa da União.",
                        "is_correct": True,
                    },
                    {"letter": "B", "content": "Sim", "is_correct": False},
                    {"letter": "C", "content": "Não", "is_correct": False},
                    {"letter": "D", "content": "Talvez", "is_correct": False},
                ],
            },
        )
    student = await create_user(client, emails, email="aluno.rpg15@exemplo.com.br")

    desktop = await _start(client, student, viewport="desktop")
    mobile = (
        await client.get(
            f"/api/v1/game/battle/{desktop['run']['public_id']}?viewport=mobile",
            headers=student.auth_header,
        )
    ).json()

    assert desktop["layout"] == "monster-arena"
    assert mobile["layout"] == "compact-answer"


# --------------------------------------------------------------------------- #
# Réguas administráveis
# --------------------------------------------------------------------------- #
async def test_the_layout_thresholds_come_from_the_database(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Item 3: os valores não podem ficar rígidos no código."""
    admin = await create_admin(client, emails, email="rpg16@exemplo.com.br")
    for index in range(10):
        await client.post(
            "/api/v1/admin/questions",
            headers=admin.auth_header,
            json={
                "statement": f"Capital — enunciado {index} com texto suficiente.",
                "difficulty": "MEDIUM",
                "alternatives": [
                    {"letter": "A", "content": "Brasília", "is_correct": True},
                    {"letter": "B", "content": "São Paulo", "is_correct": False},
                    {"letter": "C", "content": "Salvador", "is_correct": False},
                    {"letter": "D", "content": "Recife", "is_correct": False},
                ],
            },
        )
    student = await create_user(client, emails, email="aluno.rpg16@exemplo.com.br")

    antes = await _start(client, student)
    assert antes["layout"] == "monster-arena"

    settings = (
        await client.get("/api/v1/admin/game/battle-settings", headers=admin.auth_header)
    ).json()
    assert {item["key"] for item in settings} >= {"short_answer_max", "mobile_short_answer_max"}
    for item in settings:
        assert item["label"], "cada régua explica o que faz"

    updated = await client.put(
        "/api/v1/admin/game/battle-settings/short_answer_max",
        headers=admin.auth_header,
        json={"value": 5},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["value"] == 5

    depois = (
        await client.get(
            f"/api/v1/game/battle/{antes['run']['public_id']}", headers=student.auth_header
        )
    ).json()

    assert depois["layout"] == "compact-answer", "a régua nova vale sem deploy"
    assert depois["settings"]["short_answer_max"] == 5


async def test_an_unknown_setting_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg17@exemplo.com.br")

    response = await client.put(
        "/api/v1/admin/game/battle-settings/regua_inexistente",
        headers=admin.auth_header,
        json={"value": 10},
    )

    assert response.status_code == 404


async def test_the_battle_is_not_offered_as_a_challenge_card(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A Batalha tem tela própria: um cartão em Desafios a abriria na
    apresentação errada, com a mecânica certa."""
    student = await create_user(client, emails, email="rpg18@exemplo.com.br")

    modes = (await client.get("/api/v1/game/challenges/modes", headers=student.auth_header)).json()

    assert "BATTLE" not in {item["mode"] for item in modes}
