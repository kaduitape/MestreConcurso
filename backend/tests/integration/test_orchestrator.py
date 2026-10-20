"""Orquestrador de agentes, ponta a ponta.

O que se cobra aqui com mais insistência: **agente que não existe nunca aparece
verde**. Um passo concluído que não fez nada é pior que um passo falho, porque
ninguém vai investigar. Pulado traz o motivo escrito; concluído mente.
"""

from __future__ import annotations

from typing import Any

from httpx import AsyncClient

from app.domain.agents import AgentKey
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin, create_user


async def _competition(client: AsyncClient, admin: RegisteredUser) -> dict[str, Any]:
    org = await client.post(
        "/api/v1/admin/catalog/organizations",
        headers=admin.auth_header,
        json={"name": "Tribunal de Teste", "short_name": "TT", "sphere": "FEDERAL"},
    )
    assert org.status_code == 201, org.text
    created = await client.post(
        "/api/v1/admin/catalog/competitions",
        headers=admin.auth_header,
        json={
            "name": "Concurso do Orquestrador",
            "year": 2026,
            "organization_public_id": org.json()["public_id"],
        },
    )
    assert created.status_code == 201, created.text
    return dict(created.json())


async def _run(client: AsyncClient, admin: RegisteredUser) -> dict[str, Any]:
    competition = await _competition(client, admin)
    created = await client.post(
        "/api/v1/admin/agents",
        headers=admin.auth_header,
        json={"competition_public_id": competition["public_id"]},
    )
    assert created.status_code == 201, created.text
    return dict(created.json())


def _step(body: dict[str, Any], key: str) -> dict[str, Any]:
    return next(item for item in body["steps"] if item["key"] == key)


# --------------------------------------------------------------------------- #
# Catálogo
# --------------------------------------------------------------------------- #
async def test_the_catalogue_lists_the_eight_agents_and_the_parallel_layers(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt1@exemplo.com.br")

    response = await client.get("/api/v1/admin/agents/catalog", headers=admin.auth_header)

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["agents"]) == 8
    # O pedido pede paralelismo só onde não há dependência; as camadas dizem onde.
    assert any(len(camada) > 1 for camada in body["layers"])


async def test_an_unimplemented_agent_declares_why_in_the_catalogue(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt2@exemplo.com.br")

    body = (await client.get("/api/v1/admin/agents/catalog", headers=admin.auth_header)).json()

    for agente in body["agents"]:
        if not agente["is_implemented"]:
            assert agente["pending_reason"], f"{agente['key']} precisa dizer por que não roda"


# --------------------------------------------------------------------------- #
# Execução
# --------------------------------------------------------------------------- #
async def test_a_new_run_starts_with_the_eight_steps_pending(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt3@exemplo.com.br")

    body = await _run(client, admin)

    assert body["status"] == "PENDING"
    assert len(body["steps"]) == 8
    assert all(item["status"] == "PENDING" for item in body["steps"])


async def test_an_unbuilt_agent_is_skipped_never_done(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A regra que sustenta o orquestrador inteiro."""
    admin = await create_admin(client, emails, email="agt4@exemplo.com.br")
    run = await _run(client, admin)

    executado = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header
    )

    assert executado.status_code == 200, executado.text
    body = executado.json()
    auditor = _step(body, AgentKey.AUDITOR)
    assert auditor["status"] == "SKIPPED"
    assert auditor["status"] != "DONE"
    assert auditor["detail"], "pulado sem motivo vira mistério"


async def test_a_run_without_a_notice_skips_the_analyst_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Ausência de insumo não é falha — e o motivo evita caça a erro que não há."""
    admin = await create_admin(client, emails, email="agt5@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    analista = _step(body, AgentKey.NOTICE_ANALYST)
    assert analista["status"] == "SKIPPED"
    assert "edital" in analista["detail"].lower()


async def test_what_depends_on_a_skipped_step_says_so(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt6@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    estatistica = _step(body, AgentKey.STATISTICS)
    assert estatistica["status"] == "SKIPPED"
    assert "depende de" in (estatistica["detail"] or "").lower()


async def test_a_run_with_only_skips_still_completes(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Pulado com motivo é resultado legítimo; quebrado não é."""
    admin = await create_admin(client, emails, email="agt7@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    assert body["status"] == "DONE"
    assert body["finished_at"]


async def test_a_single_agent_can_be_run_by_hand(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """É o que permite insistir num passo sem refazer a execução inteira."""
    admin = await create_admin(client, emails, email="agt8@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.NOTICE_ANALYST}",
            headers=admin.auth_header,
        )
    ).json()

    analista = _step(body, AgentKey.NOTICE_ANALYST)
    # Ele RODOU e concluiu que não havia edital: isso consome tentativa.
    assert analista["status"] == "SKIPPED"
    assert analista["attempts"] == 1
    # E os outros continuam intocados.
    assert _step(body, AgentKey.TUTOR)["status"] == "PENDING"


async def test_an_unbuilt_agent_consumes_no_attempt(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Duas coisas diferentes viram "pulado", e a contagem as separa:
    o agente que rodou e não achou o que fazer gasta tentativa; o que nem
    existe, não."""
    admin = await create_admin(client, emails, email="agt12@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.IMPROVEMENTS}",
            headers=admin.auth_header,
        )
    ).json()

    melhorias = _step(body, AgentKey.IMPROVEMENTS)
    assert melhorias["status"] == "SKIPPED"
    assert melhorias["attempts"] == 0
    assert melhorias["is_implemented"] is False


async def test_an_unknown_agent_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt9@exemplo.com.br")
    run = await _run(client, admin)

    response = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run/agente-que-nao-existe",
        headers=admin.auth_header,
    )

    assert response.status_code == 404


async def test_the_run_can_be_followed_live(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt10@exemplo.com.br")
    run = await _run(client, admin)

    aberto = await client.get(f"/api/v1/admin/agents/{run['public_id']}", headers=admin.auth_header)

    assert aberto.status_code == 200
    assert len(aberto.json()["steps"]) == 8
    # Cada passo se explica, mesmo antes de rodar.
    assert all(item["description"] for item in aberto.json()["steps"])


async def test_an_unknown_competition_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt11@exemplo.com.br")

    response = await client.post(
        "/api/v1/admin/agents",
        headers=admin.auth_header,
        json={"competition_public_id": "nao-existe"},
    )

    assert response.status_code == 404


async def test_a_student_cannot_reach_the_orchestrator(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.agt@exemplo.com.br")

    assert (
        await client.get("/api/v1/admin/agents/catalog", headers=student.auth_header)
    ).status_code == 403
    assert (
        await client.post(
            "/api/v1/admin/agents",
            headers=student.auth_header,
            json={"competition_public_id": "x"},
        )
    ).status_code == 403
