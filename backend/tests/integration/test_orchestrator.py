"""Orquestrador de agentes, ponta a ponta.

O que se cobra aqui com mais insistência: **agente que não existe nunca aparece
verde**. Um passo concluído que não fez nada é pior que um passo falho, porque
ninguém vai investigar. Pulado traz o motivo escrito; concluído mente.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agents import AgentKey
from app.models.catalog import Competition, Organization
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
    professor = _step(body, AgentKey.TEACHER)
    assert professor["status"] == "SKIPPED"
    assert professor["status"] != "DONE"
    assert professor["detail"], "pulado sem motivo vira mistério"


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


async def test_an_agent_without_a_registered_runner_consumes_no_attempt(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duas coisas diferentes viram "pulado", e a contagem as separa: o agente
    que rodou e não achou o que fazer gasta tentativa; o que não tem
    implementação registrada, não.

    Os oito agentes do pedido já estão construídos, então o exemplo não vem mais
    do catálogo: a implementação de um deles é **retirada do registro** aqui. É
    o caso que o docstring de ``register_default_agents`` chama de contradição —
    catálogo dizendo "construído" e registro sem nada — e ele precisa continuar
    terminando em passo **pulado com motivo**, nunca em verde.

    A dependência do Professor é concluída à mão para que o pulo seja por falta
    de implementação, e não por dependência: são motivos diferentes, e é a
    diferença que este teste cobra.
    """
    from sqlalchemy import select

    from app.models.agent_run import AgentRun, AgentStep
    from app.services.orchestrator import registry

    admin = await create_admin(client, emails, email="agt12@exemplo.com.br")
    run = await _run(client, admin)

    linha = (
        await db_session.execute(select(AgentRun).where(AgentRun.public_id == run["public_id"]))
    ).scalar_one()
    passo = (
        await db_session.execute(
            select(AgentStep).where(
                AgentStep.run_id == linha.id, AgentStep.agent_key == AgentKey.TEACHER
            )
        )
    ).scalar_one()
    passo.status = "DONE"
    await db_session.commit()

    sem_runner = dict(registry._runners)
    sem_runner.pop(AgentKey.BATTLE_MASTER)
    monkeypatch.setattr(registry, "_runners", sem_runner)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.BATTLE_MASTER}",
            headers=admin.auth_header,
        )
    ).json()

    batalhas = _step(body, AgentKey.BATTLE_MASTER)
    assert batalhas["status"] == "SKIPPED"
    assert batalhas["attempts"] == 0
    assert "ainda não foi implementado" in batalhas["detail"]


async def test_the_eight_agents_of_the_request_all_have_a_runner(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Catálogo e registro precisam contar a mesma história.

    Um agente declarado como construído sem implementação registrada seria
    pulado dizendo "ainda não foi implementado" — contradizendo a própria ficha
    dele na tela, que é justamente o que o teste acima exercita de propósito.
    """
    from app.domain.agents import AGENTS
    from app.services.orchestrator import registry

    declarados_construidos = {spec.key for spec in AGENTS if spec.is_implemented}

    assert declarados_construidos == set(registry._runners)
    assert len(declarados_construidos) == 8


async def test_the_improvements_analyst_runs_and_declares_what_it_could_not_see(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O Agente 8 roda sem depender de ninguém: ele analisa o que já aconteceu.

    Numa instalação vazia ele não acha nada **e diz por quê** — detector sem
    amostra não vira silêncio, e o passo declara qual garantia de isolamento
    está valendo.
    """
    admin = await create_admin(client, emails, email="agt17@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.IMPROVEMENTS}",
            headers=admin.auth_header,
        )
    ).json()

    melhorias = _step(body, AgentKey.IMPROVEMENTS)
    assert melhorias["is_implemented"] is True
    assert melhorias["status"] == "DONE"
    assert melhorias["attempts"] == 1
    detalhe = melhorias["detail"] or ""
    assert "falta de amostra" in detalhe
    # Sem credencial restrita configurada, o passo diz que a garantia é só do
    # código em vez de deixar parecer que há isolamento de banco.
    assert "só do código" in detalhe


async def test_a_manual_run_still_respects_the_dependency(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Rodar à mão não atropela a ordem.

    O tutor depende da estatística: insistir nele antes disso recalcularia
    prioridade sobre incidência que ainda não existe. O passo é pulado com a
    cadeia escrita e **não gasta tentativa**, porque não rodou.
    """
    admin = await create_admin(client, emails, email="agt13@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.TUTOR}",
            headers=admin.auth_header,
        )
    ).json()

    tutor = _step(body, AgentKey.TUTOR)
    assert tutor["status"] == "SKIPPED"
    assert tutor["attempts"] == 0
    assert "depende de" in (tutor["detail"] or "").lower()


async def test_the_tutor_says_there_is_nobody_to_reorder(db_session: AsyncSession) -> None:
    """O tutor é um dos três construídos: ele roda de verdade.

    Sem candidato com plano ativo não há prioridade para recalcular, e isso é
    ausência de insumo — não "agente que não existe". Aqui ele é chamado
    direto, sem o orquestrador, para cobrar o que ele mesmo faz.
    """
    from app.models.agent_run import AgentRun as AgentRunModel
    from app.services.agent_runners import run_tutor

    org = Organization(
        name="Tribunal do Tutor", slug="tribunal-do-tutor", short_name="TTU", sphere="FEDERAL"
    )
    db_session.add(org)
    await db_session.flush()
    competition = Competition(
        name="Concurso do Tutor",
        slug="concurso-do-tutor",
        year=2026,
        organization_id=org.id,
    )
    db_session.add(competition)
    await db_session.flush()
    run = AgentRunModel(competition_id=competition.id, status="PENDING")
    db_session.add(run)
    await db_session.flush()

    outcome = await run_tutor(db_session, run)

    assert outcome.skipped is True
    assert "plano de estudo ativo" in outcome.detail


async def test_every_agent_declared_as_built_has_an_implementation(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Catálogo e registro precisam contar a mesma história.

    Um agente declarado como construído sem implementação registrada seria
    pulado dizendo "ainda não foi implementado" — contradizendo a ficha dele na
    mesma tela. Verde que mente é o defeito que este orquestrador existe para
    não ter.
    """
    from app.services.orchestrator import registry

    admin = await create_admin(client, emails, email="agt14@exemplo.com.br")
    body = (await client.get("/api/v1/admin/agents/catalog", headers=admin.auth_header)).json()

    for agente in body["agents"]:
        construido = agente["is_implemented"]
        registrado = registry.get(agente["key"]) is not None
        assert construido == registrado, (
            f"{agente['key']}: catálogo diz construído={construido}, registro diz {registrado}"
        )


async def test_the_auditor_runs_and_declares_what_it_could_not_check(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O auditor é o portão da Fase 3: ele roda sem depender de geração em massa.

    Sem conteúdo publicado não há o que conferir — e o motivo escrito inclui o
    que ficou fora do alcance da varredura.
    """
    admin = await create_admin(client, emails, email="agt15@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.AUDITOR}",
            headers=admin.auth_header,
        )
    ).json()

    auditor = _step(body, AgentKey.AUDITOR)
    assert auditor["is_implemented"] is True
    assert auditor["status"] == "SKIPPED"
    assert auditor["attempts"] == 1, "ele rodou e não achou conteúdo: gasta tentativa"
    assert "edital analisado" in auditor["detail"]


async def test_the_teacher_does_not_authorize_its_own_spending(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """O agente executa plano de geração; quem autoriza o gasto é uma pessoa.

    Se o Professor pudesse confirmar o próprio plano, a confirmação — que é
    onde a estimativa é olhada — não valeria nada.
    """
    admin = await create_admin(client, emails, email="agt16@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.TEACHER}",
            headers=admin.auth_header,
        )
    ).json()

    professor = _step(body, AgentKey.TEACHER)
    assert professor["is_implemented"] is True
    # Depende da estatística, então nem chega a rodar nesta execução vazia.
    assert professor["status"] == "SKIPPED"
    assert "depende de" in (professor["detail"] or "").lower()


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
