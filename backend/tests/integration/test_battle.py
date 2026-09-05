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
    WEEKDAY_AVAILABILITY,
    RegisteredUser,
    create_admin,
    create_position_with_subjects,
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

    assert {"BATTLE", "BATTLE_BOSS"}.isdisjoint({item["mode"] for item in modes})


# --------------------------------------------------------------------------- #
# Fase 2 — combo, crítico, moedas e poderes
# --------------------------------------------------------------------------- #
async def _use(client: AsyncClient, student: RegisteredUser, run_id: str, power: str) -> Any:
    return await client.post(
        f"/api/v1/game/battle/{run_id}/power",
        headers=student.auth_header,
        json={"power": power},
    )


async def _answer_in(
    client: AsyncClient,
    student: RegisteredUser,
    battle: dict[str, Any],
    *,
    correct: bool,
    seconds: int,
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
            "time_seconds": seconds,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_battle_opens_with_coins_and_the_three_powers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg19@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Poderes")
    student = await create_user(client, emails, email="aluno.rpg19@exemplo.com.br")

    battle = await _start(client, student)

    assert battle["status"]["coins"] == battle["combat"]["starting_coins"]
    assert battle["status"]["coins_earned"] == 0
    assert {item["power"] for item in battle["powers"]} == {"SHIELD", "ELIMINATE", "HINT"}
    for offer in battle["powers"]:
        assert offer["cost"] > 0
        assert offer["label"] and offer["description"]
        assert offer["used"] is False


async def test_a_fast_correct_answer_is_a_critical_and_hits_harder(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg20@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Crítico")
    student = await create_user(client, emails, email="aluno.rpg20@exemplo.com.br")

    battle = await _start(client, student)
    limiar = battle["combat"]["critical_seconds"]

    rapido = await _answer_in(client, student, battle, correct=True, seconds=1)
    assert rapido["is_critical"] is True
    assert rapido["combo"] == 1
    assert rapido["coins"] == battle["combat"]["coins_per_correct"]

    lento = await _answer_in(client, student, rapido["battle"], correct=True, seconds=limiar + 30)
    assert lento["is_critical"] is False
    # O segundo acerto tem combo maior e ainda assim bate menos: o crítico pesa.
    assert lento["damage"] < rapido["damage"]


async def test_the_combo_raises_damage_and_coins(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg21@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Combo")
    student = await create_user(client, emails, email="aluno.rpg21@exemplo.com.br")

    battle = await _start(client, student)
    lento = battle["combat"]["critical_seconds"] + 30

    primeiro = await _answer_in(client, student, battle, correct=True, seconds=lento)
    segundo = await _answer_in(client, student, primeiro["battle"], correct=True, seconds=lento)

    assert segundo["combo"] == 2
    assert segundo["damage"] > primeiro["damage"]
    assert segundo["coins"] > primeiro["coins"]


async def test_a_wrong_answer_resets_the_combo(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg22@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Zera")
    student = await create_user(client, emails, email="aluno.rpg22@exemplo.com.br")

    battle = await _start(client, student)
    acerto = await _answer_in(client, student, battle, correct=True, seconds=5)
    erro = await _answer_in(client, student, acerto["battle"], correct=False, seconds=5)

    assert erro["combo"] == 0
    assert erro["battle"]["status"]["best_combo"] == 1
    assert erro["coins"] == 0, "errar não rende moeda: já custou vida"


async def test_the_shield_absorbs_the_damage_of_the_next_mistake(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg23@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Escudo")
    student = await create_user(client, emails, email="aluno.rpg23@exemplo.com.br")

    battle = await _start(client, student)
    run_id = battle["run"]["public_id"]

    comprado = await _use(client, student, run_id, "SHIELD")
    assert comprado.status_code == 200, comprado.text
    depois = comprado.json()
    assert depois["status"]["coins"] == battle["status"]["coins"] - depois["combat"]["shield_cost"]
    assert next(item for item in depois["powers"] if item["power"] == "SHIELD")["used"] is True

    erro = await _answer_in(client, student, depois, correct=False, seconds=10)

    assert erro["shielded"] is True
    assert erro["damage"] == 0
    assert erro["damage_target"] is None
    assert erro["battle"]["status"]["player_hp"] == erro["battle"]["status"]["player_max_hp"]


async def test_eliminate_removes_one_incorrect_alternative(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg24@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Eliminar")
    student = await create_user(client, emails, email="aluno.rpg24@exemplo.com.br")

    battle = await _start(client, student)
    antes = len(battle["monsters"])

    depois = (await _use(client, student, battle["run"]["public_id"], "ELIMINATE")).json()

    assert len(depois["removed_letters"]) == 1
    removida = depois["removed_letters"][0]
    assert removida != "A", "o poder nunca remove a alternativa correta"
    assert len(depois["monsters"]) == antes - 1
    assert removida not in {item["letter"] for item in depois["monsters"]}


async def test_the_same_power_cannot_be_used_twice_on_a_question(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg25@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Duas vezes")
    student = await create_user(client, emails, email="aluno.rpg25@exemplo.com.br")

    battle = await _start(client, student)
    run_id = battle["run"]["public_id"]

    assert (await _use(client, student, run_id, "ELIMINATE")).status_code == 200
    repetido = await _use(client, student, run_id, "ELIMINATE")

    assert repetido.status_code == 409
    assert repetido.json()["error"]["code"] == "power_used"


async def test_a_power_without_coins_is_refused_with_the_missing_amount(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg26@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Sem moeda")
    student = await create_user(client, emails, email="aluno.rpg26@exemplo.com.br")

    battle = await _start(client, student)
    run_id = battle["run"]["public_id"]

    # O escudo consome quase todo o saldo inicial; o eliminar já não cabe.
    assert (await _use(client, student, run_id, "SHIELD")).status_code == 200
    sem_saldo = await _use(client, student, run_id, "ELIMINATE")

    assert sem_saldo.status_code == 409
    assert sem_saldo.json()["error"]["code"] == "not_enough_coins"
    assert "moeda" in sem_saldo.json()["error"]["message"]


async def test_a_question_without_explanation_has_no_hint_and_charges_nothing(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg27@exemplo.com.br")
    for index in range(10):
        await create_question(
            client,
            admin,
            statement=f"Sem explicação — enunciado {index} com texto suficiente.",
            explanation=None,
            alternatives=[
                {"letter": letter, "content": f"Alternativa {letter}", "is_correct": letter == "A"}
                for letter in ("A", "B", "C", "D")
            ],
        )
    student = await create_user(client, emails, email="aluno.rpg27@exemplo.com.br")

    battle = await _start(client, student)
    resposta = await _use(client, student, battle["run"]["public_id"], "HINT")

    assert resposta.status_code == 409
    assert resposta.json()["error"]["code"] == "no_hint_available"

    saldo = (
        await client.get(
            f"/api/v1/game/battle/{battle['run']['public_id']}", headers=student.auth_header
        )
    ).json()
    assert saldo["status"]["coins"] == battle["status"]["coins"], "não se cobra por nada"


async def test_the_hint_comes_from_content_already_registered(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg28@exemplo.com.br")
    for index in range(10):
        await create_question(
            client,
            admin,
            statement=f"Com explicação — enunciado {index} com texto suficiente.",
            explanation="A competência é privativa da União. O resto do texto não entra na dica.",
        )
    student = await create_user(client, emails, email="aluno.rpg28@exemplo.com.br")

    battle = await _start(client, student)
    depois = (await _use(client, student, battle["run"]["public_id"], "HINT")).json()

    assert depois["hint"] == "A competência é privativa da União."
    assert depois["status"]["coins"] == battle["status"]["coins"] - depois["combat"]["hint_cost"]


async def test_the_balance_is_derived_and_stable_between_reads(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg29@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Saldo")
    student = await create_user(client, emails, email="aluno.rpg29@exemplo.com.br")

    battle = await _start(client, student)
    run_id = battle["run"]["public_id"]
    await _use(client, student, run_id, "ELIMINATE")
    await _answer_in(client, student, battle, correct=True, seconds=3)

    leituras = set()
    for _ in range(3):
        atual = (
            await client.get(f"/api/v1/game/battle/{run_id}", headers=student.auth_header)
        ).json()
        leituras.add((atual["status"]["coins"], atual["status"]["enemy_hp"]))

    assert len(leituras) == 1, "moedas e HP são derivados; ler de novo não muda nada"


async def test_an_unknown_power_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg30@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Poder falso")
    student = await create_user(client, emails, email="aluno.rpg30@exemplo.com.br")

    battle = await _start(client, student)
    resposta = await _use(client, student, battle["run"]["public_id"], "TELETRANSPORTE")

    assert resposta.status_code == 404


async def test_the_combat_rules_are_editable_without_deploy(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg31@exemplo.com.br")
    await _stock(client, admin, total=10, prefix="Régua de combate")
    student = await create_user(client, emails, email="aluno.rpg31@exemplo.com.br")

    alterado = await client.put(
        "/api/v1/admin/game/battle-settings/starting_coins",
        headers=admin.auth_header,
        json={"value": 200},
    )
    assert alterado.status_code == 200, alterado.text

    battle = await _start(client, student)

    assert battle["combat"]["starting_coins"] == 200
    assert battle["status"]["coins"] == 200


# --------------------------------------------------------------------------- #
# Fase 3 — classes, equipamentos, chefes, campanha e ranking
# --------------------------------------------------------------------------- #
async def _armory(client: AsyncClient, student: RegisteredUser) -> dict[str, Any]:
    response = await client.get("/api/v1/game/battle/armory", headers=student.auth_header)
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_armory_opens_with_a_neutral_class_and_starter_gear(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rpg32@exemplo.com.br")

    armory = await _armory(client, student)

    assert armory["loadout"]["class_slug"] == "recruta"
    assert armory["loadout"]["modifiers"]["damage_percent"] == 0
    assert armory["loadout"]["modifiers"]["max_hp_percent"] == 0

    iniciais = [item for item in armory["equipment"] if item["requirement_label"] is None]
    assert {item["slot"] for item in iniciais} == {"WEAPON", "ARMOR", "TRINKET"}
    assert all(item["is_unlocked"] for item in iniciais)


async def test_every_class_is_free_and_declares_its_tradeoff(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Classe é estilo de jogo. Nada de destravar por nível, liga ou pagamento."""
    student = await create_user(client, emails, email="rpg33@exemplo.com.br")

    armory = await _armory(client, student)

    assert len(armory["classes"]) >= 3
    for item in armory["classes"]:
        assert item["tradeoff"], "classe sem troca declarada esconde a comparação"


async def test_locked_equipment_says_which_achievement_unlocks_it(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rpg34@exemplo.com.br")

    armory = await _armory(client, student)
    travadas = [item for item in armory["equipment"] if not item["is_unlocked"]]

    assert travadas, "há peças que se conquistam"
    for item in travadas:
        assert item["requirement_label"], "peça travada sem caminho é armadilha"


async def test_equipping_something_not_earned_is_refused_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rpg35@exemplo.com.br")

    response = await client.put(
        "/api/v1/game/battle/armory",
        headers=student.auth_header,
        json={
            "class_slug": "duelista",
            "weapon_slug": "lamina-do-acerto",
            "armor_slug": "gibao-de-couro",
            "trinket_slug": "amuleto-de-latao",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "equipment_locked"
    assert "conquista" in response.json()["error"]["message"]


async def test_choosing_a_class_changes_the_combat_and_is_remembered(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg36@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Classe")
    student = await create_user(client, emails, email="aluno.rpg36@exemplo.com.br")

    salvo = await client.put(
        "/api/v1/game/battle/armory",
        headers=student.auth_header,
        json={
            "class_slug": "guardiao",
            "weapon_slug": "espada-simples",
            "armor_slug": "gibao-de-couro",
            "trinket_slug": "amuleto-de-latao",
        },
    )
    assert salvo.status_code == 200, salvo.text
    assert salvo.json()["loadout"]["class_slug"] == "guardiao"

    battle = await _start(client, student)

    assert battle["loadout"]["class_slug"] == "guardiao"
    assert battle["status"]["player_max_hp"] > 100, "o Guardião aguenta mais"


async def test_the_loadout_is_frozen_on_the_run(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Trocar de armadura no meio não pode recalcular o dano já causado."""
    admin = await create_admin(client, emails, email="rpg37@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Congelado")
    student = await create_user(client, emails, email="aluno.rpg37@exemplo.com.br")

    battle = await _start(client, student)
    vida_inicial = battle["status"]["player_max_hp"]

    await client.put(
        "/api/v1/game/battle/armory",
        headers=student.auth_header,
        json={
            "class_slug": "guardiao",
            "weapon_slug": "espada-simples",
            "armor_slug": "gibao-de-couro",
            "trinket_slug": "amuleto-de-latao",
        },
    )

    depois = (
        await client.get(
            f"/api/v1/game/battle/{battle['run']['public_id']}", headers=student.auth_header
        )
    ).json()

    assert depois["loadout"]["class_slug"] == "recruta"
    assert depois["status"]["player_max_hp"] == vida_inicial


async def test_the_strategist_pays_less_for_powers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg38@exemplo.com.br")
    await _stock(client, admin, total=12, prefix="Estrategista")
    student = await create_user(client, emails, email="aluno.rpg38@exemplo.com.br")

    comum = await _start(client, student)
    preco_comum = next(item["cost"] for item in comum["powers"] if item["power"] == "SHIELD")
    await client.post(
        f"/api/v1/game/battle/{comum['run']['public_id']}/finish?abandon=true",
        headers=student.auth_header,
    )
    await client.post(
        f"/api/v1/game/challenges/runs/{comum['run']['public_id']}/finish?abandon=true",
        headers=student.auth_header,
    )

    await client.put(
        "/api/v1/game/battle/armory",
        headers=student.auth_header,
        json={
            "class_slug": "estrategista",
            "weapon_slug": "espada-simples",
            "armor_slug": "gibao-de-couro",
            "trinket_slug": "amuleto-de-latao",
        },
    )
    dele = await _start(client, student)
    preco_dele = next(item["cost"] for item in dele["powers"] if item["power"] == "SHIELD")

    assert preco_dele < preco_comum


async def test_a_boss_battle_needs_a_priority_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="rpg39@exemplo.com.br")
    await _stock(client, admin, total=15, prefix="Chefe sem prioridade")
    student = await create_user(client, emails, email="aluno.rpg39@exemplo.com.br")

    response = await client.post("/api/v1/game/battle?boss=true", headers=student.auth_header)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_priority_score"


async def test_without_a_priority_score_there_is_no_campaign_map(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rpg40@exemplo.com.br")

    campaign = (
        await client.get("/api/v1/game/battle/campaign", headers=student.auth_header)
    ).json()

    assert campaign["total"] == 0
    assert campaign["stages"] == []
    assert "Priority Score" in campaign["empty_reason"]


async def test_the_ranking_needs_a_context_and_honors_opting_out(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rpg41@exemplo.com.br")

    sem_cargo = (
        await client.get("/api/v1/game/battle/ranking", headers=student.auth_header)
    ).json()
    assert sem_cargo["members"] == []
    assert "cargo" in sem_cargo["empty_reason"]

    await client.put(
        "/api/v1/game/league/preferences",
        headers=student.auth_header,
        json={"opt_out": True},
    )
    desligado = (
        await client.get("/api/v1/game/battle/ranking", headers=student.auth_header)
    ).json()

    assert desligado["members"] == []
    assert "desligou a comparação" in desligado["empty_reason"]


async def test_the_ranking_never_suggests_approval(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="rpg42@exemplo.com.br")

    ranking = (await client.get("/api/v1/game/battle/ranking", headers=student.auth_header)).json()

    assert "aprovação" in ranking["note"]
    assert "Equipamento e classe mudam o combate" in ranking["note"]


async def _with_priority(
    client: AsyncClient, emails: CapturingDispatcher, *, tag: str
) -> tuple[RegisteredUser, RegisteredUser, dict[str, Any]]:
    """Aluno com plano, Priority Score calculado e banco abastecido no alvo."""
    admin = await create_admin(client, emails, email=f"{tag}@exemplo.com.br")
    position = await create_position_with_subjects(client, admin)
    student = await create_user(client, emails, email=f"aluno.{tag}@exemplo.com.br")

    await client.post(
        "/api/v1/study/plan",
        headers=student.auth_header,
        json={
            "position_public_id": position["public_id"],
            "minutes_by_weekday": WEEKDAY_AVAILABILITY,
        },
    )
    priorities = (
        await client.post("/api/v1/intelligence/priority/recompute", headers=student.auth_header)
    ).json()
    alvo = priorities["items"][0]

    subjects = (
        await client.get("/api/v1/catalog/subjects?page_size=50", headers=admin.auth_header)
    ).json()
    subject = next(item for item in subjects["items"] if item["name"] == alvo["label"])
    for index in range(14):
        await create_question(
            client,
            admin,
            statement=f"Chefe {tag} — enunciado {index} com texto suficiente.",
            subject_public_id=subject["public_id"],
        )
    return admin, student, subject


async def test_the_campaign_map_comes_from_the_real_priority_score(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, subject = await _with_priority(client, emails, tag="rpg43")

    campaign = (
        await client.get("/api/v1/game/battle/campaign", headers=student.auth_header)
    ).json()

    assert campaign["total"] > 0
    assert campaign["empty_reason"] is None
    # A ordem é a do Priority Score, do pior para o menos pior.
    scores = [item["priority_score"] for item in campaign["stages"]]
    assert scores == sorted(scores, reverse=True)
    # Nenhum estágio é trancado por outro: conteúdo não fica atrás de progresso.
    jogaveis = [item for item in campaign["stages"] if not item["is_locked"]]
    assert any(item["subject_public_id"] == subject["public_id"] for item in jogaveis)
    assert campaign["cleared"] == 0


async def test_a_boss_battle_fights_the_weakest_subject_and_hits_harder(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    _, student, subject = await _with_priority(client, emails, tag="rpg44")

    response = await client.post("/api/v1/game/battle?boss=true", headers=student.auth_header)
    assert response.status_code == 201, response.text
    battle = response.json()

    assert battle["is_boss"] is True
    assert battle["run"]["mode"] == "BATTLE_BOSS"
    assert battle["run"]["selection"]["rule"] == "disciplina de maior Priority Score"
    assert battle["run"]["subject_label"] == subject["name"]
    # O chefe aguenta mais que um inimigo comum do mesmo tamanho de rodada.
    assert battle["status"]["enemy_max_hp"] > 12 * 34 * 0.75


async def test_a_campaign_stage_picks_its_own_subject(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Sem isso a campanha só teria um estágio jogável: o primeiro."""
    _, student, subject = await _with_priority(client, emails, tag="rpg45")

    response = await client.post(
        f"/api/v1/game/battle?boss=true&subject={subject['public_id']}",
        headers=student.auth_header,
    )

    assert response.status_code == 201, response.text
    battle = response.json()
    assert battle["run"]["selection"]["rule"] == "estágio de campanha"
    assert battle["run"]["subject_label"] == subject["name"]
