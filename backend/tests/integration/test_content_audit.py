"""O auditor de conteúdo, ponta a ponta.

Dois testes aqui valem mais que os outros:

* **o laudo sobrevive à recusa** — a transação de quem tentou publicar é
  desfeita, e o laudo que explica a recusa não pode ir embora junto;
* **o laudo diz o que não deu para conferir** — laudo limpo que escondeu a
  lacuna vira uma aprovação que ninguém deu.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin, create_user, question_payload

ENUNCIADO = (
    "Sobre o princípio da legalidade na Administração Pública, assinale a alternativa correta "
    "segundo a Constituição Federal."
)


def _com_alternativas_repetidas(statement: str) -> dict[str, Any]:
    payload = question_payload(statement=statement)
    payload["alternatives"][1]["content"] = payload["alternatives"][0]["content"]
    return payload


async def _laudos(
    client: AsyncClient, admin: RegisteredUser, **params: str
) -> list[dict[str, Any]]:
    consulta = "&".join(f"{chave}={valor}" for chave, valor in params.items())
    resposta = await client.get(
        f"/api/v1/admin/content-audit?{consulta}", headers=admin.auth_header
    )
    assert resposta.status_code == 200, resposta.text
    return list(resposta.json()["items"])


# --------------------------------------------------------------------------- #
# O portão
# --------------------------------------------------------------------------- #
async def test_a_question_with_repeated_alternatives_is_not_created_published(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A letra repetida já era barrada; o texto repetido passava direto."""
    admin = await create_admin(client, emails, email="aud1@exemplo.com.br")

    resposta = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json=_com_alternativas_repetidas(ENUNCIADO),
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["error"]["code"] == "content_audit_blocked"
    assert "mesmo texto" in resposta.json()["error"]["message"]


async def test_the_same_question_can_be_saved_as_a_draft(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O portão é de publicação, não de rascunho: trabalho em andamento não é barrado."""
    admin = await create_admin(client, emails, email="aud2@exemplo.com.br")
    payload = _com_alternativas_repetidas(ENUNCIADO)
    payload["status"] = "DRAFT"

    resposta = await client.post("/api/v1/admin/questions", headers=admin.auth_header, json=payload)

    assert resposta.status_code == 201, resposta.text


async def test_a_sound_question_goes_through(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="aud3@exemplo.com.br")

    resposta = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json=question_payload(statement=ENUNCIADO),
    )

    assert resposta.status_code == 201, resposta.text


async def test_publishing_a_broken_draft_is_refused_and_the_report_survives(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O teste que paga esta fase.

    A recusa desfaz a transação de quem publicou. Se o laudo morasse nela, o
    histórico perderia exatamente as linhas que explicam as recusas.
    """
    admin = await create_admin(client, emails, email="aud4@exemplo.com.br")
    payload = _com_alternativas_repetidas(ENUNCIADO)
    payload["status"] = "DRAFT"
    criada = await client.post("/api/v1/admin/questions", headers=admin.auth_header, json=payload)
    public_id = criada.json()["public_id"]

    publicar = await client.patch(
        f"/api/v1/admin/questions/{public_id}",
        headers=admin.auth_header,
        json={"status": "PUBLISHED"},
    )

    assert publicar.status_code == 409, publicar.text
    assert publicar.json()["error"]["code"] == "content_audit_blocked"

    # A questão continua rascunho…
    atual = await client.get(f"/api/v1/admin/questions/{public_id}", headers=admin.auth_header)
    assert atual.json()["status"] == "DRAFT"

    # …e o laudo que explica a recusa continua lá.
    laudos = await _laudos(client, admin, target_public_id=public_id)
    assert len(laudos) == 1, "o laudo da recusa precisa sobreviver ao rollback"
    assert laudos[0]["verdict"] == "BLOCKED"
    assert laudos[0]["blocked_publication"] is True
    assert any(item["rule"] == "question.alternative_repeated" for item in laudos[0]["findings"])


# --------------------------------------------------------------------------- #
# O que não deu para conferir
# --------------------------------------------------------------------------- #
async def test_the_report_says_the_topic_was_not_checked(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="aud5@exemplo.com.br")
    criada = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json=question_payload(statement=ENUNCIADO),
    )
    public_id = criada.json()["public_id"]

    laudo = await client.post(
        "/api/v1/admin/content-audit/run",
        headers=admin.auth_header,
        json={"target_kind": "QUESTION", "target_public_id": public_id},
    )

    assert laudo.status_code == 200, laudo.text
    corpo = laudo.json()
    nao_conferido = [item for item in corpo["findings"] if item["severity"] == "NOT_CHECKED"]
    assert nao_conferido, "sem edital, o tópico não foi conferido — e isso precisa aparecer"
    assert "não foi conferido" in nao_conferido[0]["message"]
    assert corpo["summary"]["not_checked"] == len(nao_conferido)


async def test_the_report_declares_how_far_it_looked(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """ "Nada encontrado" sem alcance declarado é garantia que o auditor não deu."""
    admin = await create_admin(client, emails, email="aud6@exemplo.com.br")
    criada = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json=question_payload(statement=ENUNCIADO),
    )

    laudo = await client.post(
        "/api/v1/admin/content-audit/run",
        headers=admin.auth_header,
        json={"target_kind": "QUESTION", "target_public_id": criada.json()["public_id"]},
    )

    assert "compared_questions" in laudo.json()["summary"]


# --------------------------------------------------------------------------- #
# Histórico de correções
# --------------------------------------------------------------------------- #
async def test_the_history_shows_the_defect_disappearing(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O histórico de correções é a sequência de laudos do mesmo conteúdo."""
    admin = await create_admin(client, emails, email="aud7@exemplo.com.br")
    criada = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json={
            "statement": ENUNCIADO,
            "kind": "DISCURSIVE",
            "alternatives": [],
            "status": "DRAFT",
        },
    )
    assert criada.status_code == 201, criada.text
    public_id = criada.json()["public_id"]

    antes = await client.post(
        "/api/v1/admin/content-audit/run",
        headers=admin.auth_header,
        json={"target_kind": "QUESTION", "target_public_id": public_id},
    )
    assert antes.json()["verdict"] == "BLOCKED"
    assert any(item["rule"] == "question.answer_key_missing" for item in antes.json()["findings"])

    corrigir = await client.patch(
        f"/api/v1/admin/questions/{public_id}",
        headers=admin.auth_header,
        json={"explanation": "Espera-se que o candidato discorra sobre o princípio."},
    )
    assert corrigir.status_code == 200, corrigir.text

    depois = await client.post(
        "/api/v1/admin/content-audit/run",
        headers=admin.auth_header,
        json={"target_kind": "QUESTION", "target_public_id": public_id},
    )

    # O bloqueio sumiu. Sobra o aviso de que a questão não tem disciplina nem
    # tópico — que é verdade, e continua à vista em vez de virar laudo limpo.
    assert not any(item["severity"] == "BLOCKER" for item in depois.json()["findings"])
    assert depois.json()["verdict"] == "WARNED"

    laudos = await _laudos(client, admin, target_public_id=public_id)
    assert len(laudos) == 2, "cada conferência é uma linha nova; nada é sobrescrito"
    # Do mais novo para o mais antigo: o defeito sumiu.
    assert [item["verdict"] for item in laudos] == ["WARNED", "BLOCKED"]


# --------------------------------------------------------------------------- #
# Regras configuráveis
# --------------------------------------------------------------------------- #
async def test_the_rules_say_what_they_cobram_and_what_vale_hoje(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="aud8@exemplo.com.br")

    resposta = await client.get("/api/v1/admin/content-audit/rules", headers=admin.auth_header)

    assert resposta.status_code == 200, resposta.text
    regras = resposta.json()
    assert len(regras) >= 10
    for regra in regras:
        assert regra["description"], f"{regra['key']} precisa dizer o que cobra"
        assert regra["default_severity"]


async def test_turning_a_rule_off_lets_the_publication_through(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A saída honesta não é burlar o portão: é desligar a regra, e isso fica registrado."""
    admin = await create_admin(client, emails, email="aud9@exemplo.com.br")

    desligar = await client.put(
        "/api/v1/admin/content-audit/rules/question.alternative_repeated",
        headers=admin.auth_header,
        json={"is_enabled": False, "severity": "BLOCKER"},
    )
    assert desligar.status_code == 200, desligar.text

    resposta = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json=_com_alternativas_repetidas(ENUNCIADO),
    )

    assert resposta.status_code == 201, resposta.text


async def test_a_blocking_rule_can_be_lowered_to_a_warning(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="aud10@exemplo.com.br")

    resposta = await client.put(
        "/api/v1/admin/content-audit/rules/question.alternative_repeated",
        headers=admin.auth_header,
        json={"is_enabled": True, "severity": "WARNING"},
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["severity"] == "WARNING"
    assert resposta.json()["default_severity"] == "BLOCKER"

    criada = await client.post(
        "/api/v1/admin/questions",
        headers=admin.auth_header,
        json=_com_alternativas_repetidas(ENUNCIADO),
    )
    assert criada.status_code == 201, criada.text


async def test_a_rule_cannot_be_set_to_not_checked(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """NOT_CHECKED não é escolha: é o que o auditor diz quando faltou insumo."""
    admin = await create_admin(client, emails, email="aud11@exemplo.com.br")

    resposta = await client.put(
        "/api/v1/admin/content-audit/rules/question.alternative_repeated",
        headers=admin.auth_header,
        json={"is_enabled": True, "severity": "NOT_CHECKED"},
    )

    assert resposta.status_code == 409, resposta.text
    assert resposta.json()["error"]["code"] == "invalid_severity"


async def test_an_unknown_rule_is_refused(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="aud12@exemplo.com.br")

    resposta = await client.put(
        "/api/v1/admin/content-audit/rules/regra.que.nao.existe",
        headers=admin.auth_header,
        json={"is_enabled": True, "severity": "BLOCKER"},
    )

    assert resposta.status_code == 404


# --------------------------------------------------------------------------- #
# Acesso
# --------------------------------------------------------------------------- #
async def test_a_student_cannot_reach_the_audit(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    aluno = await create_user(client, emails, email="aluno.aud@exemplo.com.br")

    assert (
        await client.get("/api/v1/admin/content-audit/rules", headers=aluno.auth_header)
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/content-audit/run",
            headers=aluno.auth_header,
            json={"target_kind": "QUESTION", "target_public_id": "x"},
        )
    ).status_code == 403


async def test_an_unknown_target_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="aud13@exemplo.com.br")

    resposta = await client.post(
        "/api/v1/admin/content-audit/run",
        headers=admin.auth_header,
        json={"target_kind": "QUESTION", "target_public_id": "nao-existe"},
    )

    assert resposta.status_code == 404
