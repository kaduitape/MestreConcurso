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


async def test_a_step_that_did_not_run_is_never_done(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A regra que sustenta o orquestrador inteiro.

    O Professor agora depende do **edital**, não da estatística, então numa
    execução sem edital ele chega a ``BLOCKED`` — bloqueado por dependência,
    com o motivo. O que não muda é o essencial: nunca ``DONE``.
    """
    admin = await create_admin(client, emails, email="agt4@exemplo.com.br")
    run = await _run(client, admin)

    executado = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header
    )

    assert executado.status_code == 200, executado.text
    body = executado.json()
    professor = _step(body, AgentKey.TEACHER)
    assert professor["status"] == "BLOCKED"
    assert professor["status"] != "DONE"
    assert professor["detail"], "bloqueado sem motivo vira mistério"
    # O motivo traz o que houve com a dependência, não só o nome dela.
    assert "Analista de editais" in professor["detail"]
    assert "aguardando insumo" in professor["detail"]


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
    # Falta de insumo tem estado próprio: nenhuma tentativa resolve, e por
    # isso ela também não consome tentativa nenhuma.
    assert analista["status"] == "AWAITING_INPUT"
    assert analista["attempts"] == 0
    assert "edital" in analista["detail"].lower()
    assert analista["action"] == "RESOLVE_INPUT"


async def test_what_depends_on_a_skipped_step_says_so(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="agt6@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    estatistica = _step(body, AgentKey.STATISTICS)
    assert estatistica["status"] == "BLOCKED"
    assert "depende de" in (estatistica["detail"] or "").lower()
    # E diz o que aconteceu com quem faltou, para não obrigar a caçar o passo.
    assert "Analista de editais" in (estatistica["detail"] or "")


async def test_a_run_with_only_pending_input_finishes_with_caveats(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Nada quebrou, e nada está completo: é o estado que faltava.

    Dizer ``DONE`` aqui mentiria sobre o que falta — e era o que acontecia,
    porque pendência e "rodou e não havia o que fazer" eram o mesmo estado.
    """
    admin = await create_admin(client, emails, email="agt7@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    assert body["status"] == "DONE_WITH_NOTES"
    assert body["finished_at"]
    # Nenhum passo falhou, então a execução não tem erro para mostrar.
    assert body["error"] is None


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
    # Ele rodou e descobriu que faltava o edital. Falta de insumo **não**
    # consome tentativa: era isso que levava um edital sem PDF a "esgotar as
    # 2 tentativas" sem nunca ter havido falha nenhuma.
    assert analista["status"] == "AWAITING_INPUT"
    assert analista["attempts"] == 0
    # E os outros continuam intocados.
    assert _step(body, AgentKey.TUTOR)["status"] == "PENDING"


async def test_an_agent_without_a_registered_runner_consumes_no_attempt(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Agente declarado sem implementação registrada tem estado próprio.

    Antes isto se misturava a "rodou e não havia o que fazer" — os dois viravam
    ``SKIPPED`` —, e a única pista era a contagem de tentativas. Agora é
    ``NOT_IMPLEMENTED``, que a tela pode tratar como o que é: contradição entre
    o catálogo e o registro, não resultado do agente.

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
    assert batalhas["status"] == "NOT_IMPLEMENTED"
    assert batalhas["attempts"] == 0
    assert "implementação" in batalhas["detail"]


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
    # Detector que não rodou é **ressalva**, não silêncio: falta de amostra não
    # pode passar por ausência comprovada de problema.
    assert melhorias["status"] == "DONE_WITH_NOTES"
    assert melhorias["attempts"] == 1
    assert melhorias["notes"], "detector sem amostra precisa aparecer nomeado"
    assert any("não rodou" in nota for nota in melhorias["notes"])
    detalhe = melhorias["detail"] or ""
    assert "falta de amostra" in detalhe
    # Sem credencial restrita configurada, o passo diz que a garantia é só do
    # código em vez de deixar parecer que há isolamento de banco.
    assert "só do código" in detalhe


async def test_a_manual_run_still_respects_the_dependency(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Rodar à mão não atropela a ordem.

    O tutor depende do **edital**: insistir nele antes disso ordenaria estudo
    sobre tópico que ninguém confirmou. O passo é bloqueado com a cadeia
    escrita e **não gasta tentativa**, porque não rodou.
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
    assert tutor["status"] == "BLOCKED"
    assert tutor["attempts"] == 0
    assert "depende de" in (tutor["detail"] or "").lower()
    assert tutor["action"] == "RESOLVE_DEPENDENCY"


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

    # Ausência de candidato é falta de insumo, com estado próprio — e por isso
    # não consome tentativa quando o orquestrador o chama.
    assert outcome.awaiting_input is True
    assert outcome.status == "AWAITING_INPUT"
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
    # Conteúdo inexistente é pendência, não falha técnica: o auditor precisa
    # separar as duas, e nenhuma tentativa faz conteúdo aparecer.
    assert auditor["status"] == "AWAITING_INPUT"
    assert auditor["attempts"] == 0
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
    # Depende do edital, então nem chega a rodar nesta execução vazia.
    assert professor["status"] == "BLOCKED"
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


# --------------------------------------------------------------------------- #
# Diagnóstico: a causa original não pode se perder
# --------------------------------------------------------------------------- #
async def test_running_out_of_attempts_keeps_the_original_cause(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O defeito que deixava a tela sem diagnóstico.

    Era a terceira chamada que apagava tudo: o ramo de "esgotou as tentativas"
    sobrescrevia o detalhe, e com ele a única pista do que havia quebrado.
    """
    from app.services.orchestrator import AgentOutcome, registry

    admin = await create_admin(client, emails, email="diag1@exemplo.com.br")
    run = await _run(client, admin)

    async def quebra(session: object, execucao: object) -> AgentOutcome:
        raise RuntimeError("conexão com o Qdrant recusada em qdrant:6333")

    monkeypatch.setitem(registry._runners, AgentKey.IMPROVEMENTS, quebra)

    for _ in range(3):
        body = (
            await client.post(
                f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.IMPROVEMENTS}",
                headers=admin.auth_header,
            )
        ).json()

    passo = _step(body, AgentKey.IMPROVEMENTS)
    assert passo["status"] == "FAILED"
    assert passo["attempts"] == 1  # max_attempts do analista de melhorias
    assert passo["attempts_exhausted"] is True
    # A causa continua lá — é o que serve para diagnosticar.
    assert "Qdrant" in (passo["detail"] or "")
    assert passo["action"] == "RETRY_STEP"


async def test_every_attempt_keeps_its_own_cause(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duas falhas por motivos diferentes: as duas precisam ser consultáveis."""
    from app.services.orchestrator import AgentOutcome, registry

    admin = await create_admin(client, emails, email="diag2@exemplo.com.br")
    run = await _run(client, admin)

    causas = iter(["o banco recusou a conexão", "o provedor devolveu 429"])

    async def quebra(session: object, execucao: object) -> AgentOutcome:
        raise RuntimeError(next(causas))

    monkeypatch.setitem(registry._runners, AgentKey.AUDITOR, quebra)

    for _ in range(2):
        body = (
            await client.post(
                f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.AUDITOR}",
                headers=admin.auth_header,
            )
        ).json()

    passo = _step(body, AgentKey.AUDITOR)
    historico = passo["attempts_history"]
    assert [item["number"] for item in historico] == [1, 2]
    assert "recusou a conexão" in historico[0]["detail"]
    assert "429" in historico[1]["detail"]
    # Cada tentativa guarda o próprio código, duração e id de correlação.
    assert all(item["error_code"] == "agent_unhandled_error" for item in historico)
    assert all(item["duration_ms"] is not None for item in historico)
    assert all(item["request_id"] for item in historico)


async def test_a_database_error_inside_an_agent_does_not_break_the_orchestrator(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Erro de banco deixava a transação morta e o próprio tratamento de erro
    estourava — a causa real era substituída por um estouro mais adiante.

    Agora o orquestrador faz rollback antes de registrar, então a causa chega
    inteira e os passos seguintes continuam rodando.
    """
    from sqlalchemy import text

    from app.services.orchestrator import AgentOutcome, registry

    admin = await create_admin(client, emails, email="diag3@exemplo.com.br")
    run = await _run(client, admin)

    async def quebra_o_banco(session: AsyncSession, execucao: object) -> AgentOutcome:
        await session.execute(text("SELECT * FROM tabela_que_nao_existe"))
        raise AssertionError("inalcançável")

    monkeypatch.setitem(registry._runners, AgentKey.AUDITOR, quebra_o_banco)

    resposta = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header
    )
    assert resposta.status_code == 200, resposta.text
    body = resposta.json()

    auditor = _step(body, AgentKey.AUDITOR)
    assert auditor["status"] == "FAILED"
    assert "tabela_que_nao_existe" in (auditor["detail"] or "")
    # E a execução continuou: o analista de melhorias é independente do auditor.
    assert _step(body, AgentKey.IMPROVEMENTS)["status"] in {"DONE", "DONE_WITH_NOTES"}
    # A execução inteira é FAILED, e o erro dela nomeia o passo que quebrou.
    assert body["status"] == "FAILED"
    assert "Auditor" in (body["error"] or "")


# --------------------------------------------------------------------------- #
# Auditoria: sucesso da requisição não é sucesso do agente
# --------------------------------------------------------------------------- #
async def test_the_audit_log_does_not_say_success_for_a_failed_run(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O registro descreve o resultado da execução, não a chegada do pedido."""
    from sqlalchemy import select

    from app.models.audit import AuditAction, AuditLog
    from app.services.orchestrator import AgentOutcome, registry

    admin = await create_admin(client, emails, email="diag4@exemplo.com.br")
    run = await _run(client, admin)

    async def quebra(session: object, execucao: object) -> AgentOutcome:
        raise RuntimeError("estourou")

    monkeypatch.setitem(registry._runners, AgentKey.IMPROVEMENTS, quebra)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()
    assert body["status"] == "FAILED"

    registros = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.AGENT_RUN_FINISHED,
                    AuditLog.resource_id == run["public_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    assert registros
    assert all(item.status == "FAILED" for item in registros)
    # E a meta guarda a contagem por estado, para cruzar com a tela.
    assert registros[-1].meta["run_status"] == "FAILED"
    assert registros[-1].meta["steps"]


async def test_a_run_with_caveats_is_audited_as_partial(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Pendência não é sucesso nem falha, e a auditoria precisa poder dizer isso."""
    from sqlalchemy import select

    from app.models.audit import AuditAction, AuditLog

    admin = await create_admin(client, emails, email="diag5@exemplo.com.br")
    run = await _run(client, admin)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()
    assert body["status"] == "DONE_WITH_NOTES"

    registro = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.AGENT_RUN_FINISHED,
                    AuditLog.resource_id == run["public_id"],
                )
            )
        )
        .scalars()
        .all()
    )[-1]
    assert registro.status == "PARTIAL"


async def test_a_step_waiting_for_input_is_audited_as_pending_not_success(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    from sqlalchemy import select

    from app.models.audit import AuditAction, AuditLog

    admin = await create_admin(client, emails, email="diag6@exemplo.com.br")
    run = await _run(client, admin)

    await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.NOTICE_ANALYST}",
        headers=admin.auth_header,
    )

    registro = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == AuditAction.AGENT_STEP_RUN)
            )
        )
        .scalars()
        .all()
    )[-1]
    assert registro.status == "PENDING_INPUT"
    assert registro.meta["step_status"] == "AWAITING_INPUT"
    assert registro.meta["attempts"] == 0


# --------------------------------------------------------------------------- #
# Pré-requisitos e execução duplicada
# --------------------------------------------------------------------------- #
async def test_preflight_names_the_missing_pdf_with_the_action(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Descobrir antes de disparar oito agentes, não depois de sete bloqueios."""
    admin = await create_admin(client, emails, email="diag7@exemplo.com.br")
    run = await _run(client, admin)

    resposta = await client.get(
        f"/api/v1/admin/agents/{run['public_id']}/preflight", headers=admin.auth_header
    )
    assert resposta.status_code == 200, resposta.text
    body = resposta.json()

    assert body["ready"] is False
    por_chave = {item["key"]: item for item in body["checks"]}
    assert por_chave["notice"]["ok"] is False
    assert por_chave["notice"]["action"] == "ATTACH_NOTICE"
    assert por_chave["ai_notice_extraction"]["ok"] is False
    assert por_chave["ai_notice_extraction"]["action"] == "CONFIGURE_AI"


async def test_a_second_simultaneous_run_is_refused(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """A trava é no banco: ler e depois escrever deixava dois pedidos passarem."""
    from sqlalchemy import select

    from app.models.agent_run import AgentRun as AgentRunModel

    admin = await create_admin(client, emails, email="diag8@exemplo.com.br")
    run = await _run(client, admin)

    linha = (
        await db_session.execute(
            select(AgentRunModel).where(AgentRunModel.public_id == run["public_id"])
        )
    ).scalar_one()
    linha.status = "RUNNING"
    await db_session.commit()

    recusado = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header
    )
    assert recusado.status_code == 409
    assert recusado.json()["error"]["code"] == "agent_run_running"


async def test_a_stuck_step_is_recovered_with_the_reason(db_session: AsyncSession) -> None:
    """Processo derrubado deixava "executando" eterno e a execução nunca fechava."""
    from datetime import UTC, datetime, timedelta

    from app.models.agent_run import AgentRun as AgentRunModel
    from app.models.agent_run import AgentStep, AgentStepAttempt
    from app.services.orchestrator import OrchestratorService

    run = AgentRunModel(status="RUNNING")
    db_session.add(run)
    await db_session.flush()
    passo = AgentStep(
        run_id=run.id,
        agent_key=AgentKey.AUDITOR,
        status="RUNNING",
        attempts=1,
        heartbeat_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db_session.add(passo)
    await db_session.flush()
    db_session.add(AgentStepAttempt(step_id=passo.id, number=1, status="RUNNING"))
    await db_session.commit()

    recuperados = await OrchestratorService(db_session).recover_stuck()

    assert recuperados == 1
    await db_session.refresh(passo)
    assert passo.status == "FAILED"
    assert "interrompida" in (passo.detail or "")
    # A tentativa aberta fecha com o motivo, sem consumir outra.
    assert passo.attempts == 1


async def test_canceling_preserves_what_already_finished(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Cancelar não desfaz trabalho concluído — refazê-lo custaria IA de novo."""
    admin = await create_admin(client, emails, email="diag9@exemplo.com.br")
    run = await _run(client, admin)

    antes = (
        await client.post(
            f"/api/v1/admin/agents/{run['public_id']}/run/{AgentKey.IMPROVEMENTS}",
            headers=admin.auth_header,
        )
    ).json()
    melhorias_antes = _step(antes, AgentKey.IMPROVEMENTS)
    assert melhorias_antes["status"] in {"DONE", "DONE_WITH_NOTES"}

    cancelado = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/cancel", headers=admin.auth_header
    )
    assert cancelado.status_code == 200, cancelado.text
    body = cancelado.json()

    assert body["status"] == "CANCELED"
    # O que terminou fica; o que não tinha rodado vira cancelado.
    assert _step(body, AgentKey.IMPROVEMENTS)["status"] == melhorias_antes["status"]
    assert _step(body, AgentKey.TUTOR)["status"] == "CANCELED"


# --------------------------------------------------------------------------- #
# Execução durável: a página fechar não pode cancelar o trabalho
# --------------------------------------------------------------------------- #
async def test_the_request_accepts_the_job_and_returns_before_it_finishes(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O job é aceito e segue fora do ciclo HTTP.

    Era aqui que a expiração de sessão matava trabalho: a execução rodava
    dentro da requisição, e a conexão caindo cancelava a tarefa no meio.
    """
    from app.core.config import settings
    from app.workers.tasks import agents as tarefa

    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    admin = await create_admin(client, emails, email="fila1@exemplo.com.br")
    run = await _run(client, admin)

    enfileirados: list[dict[str, object]] = []
    monkeypatch.setattr(
        tarefa.run_agents_task,
        "apply_async",
        lambda **kwargs: enfileirados.append(kwargs),
    )

    resposta = await client.post(
        f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header
    )

    assert resposta.status_code == 200, resposta.text
    body = resposta.json()
    # Devolveu antes de rodar: nenhum passo saiu de PENDING.
    assert body["status"] == "PENDING"
    assert all(item["status"] == "PENDING" for item in body["steps"])
    # E a tarefa foi para a fila com a execução e quem pediu.
    assert len(enfileirados) == 1
    assert enfileirados[0]["kwargs"]["run_public_id"] == run["public_id"]
    assert enfileirados[0]["kwargs"]["actor_id"]


async def test_accepting_the_job_is_audited_as_accepted_not_success(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Aceitar o job e concluir a execução são dois níveis diferentes."""
    from sqlalchemy import select

    from app.core.config import settings
    from app.models.audit import AuditAction, AuditLog
    from app.workers.tasks import agents as tarefa

    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    admin = await create_admin(client, emails, email="fila2@exemplo.com.br")
    run = await _run(client, admin)
    monkeypatch.setattr(tarefa.run_agents_task, "apply_async", lambda **kwargs: None)

    await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)

    registros = (
        (
            await db_session.execute(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.AGENT_RUN_STARTED,
                    AuditLog.resource_id == run["public_id"],
                )
            )
        )
        .scalars()
        .all()
    )
    aceites = [item for item in registros if item.status == "ACCEPTED"]
    assert aceites, "o aceite do job precisa ter registro próprio"
    assert aceites[-1].meta["mode"] == "background"


async def test_a_queue_that_is_down_does_not_lose_the_work(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fila indisponível executa na hora em vez de fingir que enfileirou."""
    from app.core.config import settings
    from app.workers.tasks import agents as tarefa

    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    admin = await create_admin(client, emails, email="fila3@exemplo.com.br")
    run = await _run(client, admin)

    def explode(**kwargs: object) -> None:
        raise RuntimeError("broker indisponível")

    monkeypatch.setattr(tarefa.run_agents_task, "apply_async", explode)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    # Rodou dentro do pedido: o trabalho não se perdeu.
    assert body["status"] == "DONE_WITH_NOTES"
    assert _step(body, AgentKey.NOTICE_ANALYST)["status"] == "AWAITING_INPUT"


async def test_the_worker_resumes_without_redoing_what_already_finished(
    client: AsyncClient, emails: CapturingDispatcher, db_session: AsyncSession
) -> None:
    """Retomar não refaz: passo em estado terminal é deixado quieto."""
    from sqlalchemy import select

    from app.models.agent_run import AgentRun as AgentRunModel
    from app.models.agent_run import AgentStep
    from app.workers.tasks.agents import _run as rodar_na_fila

    admin = await create_admin(client, emails, email="fila4@exemplo.com.br")
    run = await _run(client, admin)

    linha = (
        await db_session.execute(
            select(AgentRunModel).where(AgentRunModel.public_id == run["public_id"])
        )
    ).scalar_one()
    passo = (
        await db_session.execute(
            select(AgentStep).where(
                AgentStep.run_id == linha.id, AgentStep.agent_key == AgentKey.IMPROVEMENTS
            )
        )
    ).scalar_one()
    passo.status = "DONE"
    passo.detail = "já tinha rodado antes da interrupção"
    passo.attempts = 1
    await db_session.commit()

    resultado = await rodar_na_fila(run["public_id"], linha.started_by_user_id or 1)

    assert resultado["status"] == "OK"
    await db_session.refresh(passo)
    # O passo concluído não foi refeito: o detalhe dele é o de antes.
    assert passo.detail == "já tinha rodado antes da interrupção"
    assert passo.attempts == 1


async def test_no_statistics_sample_does_not_block_the_teacher(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O defeito das observações 2 e 3, na cadeia inteira.

    Com o edital analisado e a banca sem prova anterior, a estatística fica em
    "dados insuficientes" — e o Professor **continua rodando**, porque aula
    sobre tópico confirmado do edital não depende de amostra. Antes, ele era
    pulado em cascata e levava a memorização e o mestre de batalhas com ele.
    """
    from sqlalchemy import select

    from app.models.agent_run import AgentRun as AgentRunModel
    from app.models.agent_run import AgentStep
    from app.services.orchestrator import AgentOutcome, registry

    admin = await create_admin(client, emails, email="cascata@exemplo.com.br")
    run = await _run(client, admin)

    # O analista cumpre o contrato; a estatística não tem amostra.
    async def analista_ok(session: object, execucao: object) -> AgentOutcome:
        return AgentOutcome(detail="Edital analisado: 3 disciplinas.")

    async def sem_amostra(session: object, execucao: object) -> AgentOutcome:
        return AgentOutcome(
            detail="Nenhuma prova desta banca no acervo: dados insuficientes.",
            awaiting_input=True,
        )

    professor_rodou = False

    async def professor(session: object, execucao: object) -> AgentOutcome:
        nonlocal professor_rodou
        professor_rodou = True
        return AgentOutcome(detail="Nenhum plano confirmado para executar.", skipped=True)

    monkeypatch.setitem(registry._runners, AgentKey.NOTICE_ANALYST, analista_ok)
    monkeypatch.setitem(registry._runners, AgentKey.STATISTICS, sem_amostra)
    monkeypatch.setitem(registry._runners, AgentKey.TEACHER, professor)

    body = (
        await client.post(f"/api/v1/admin/agents/{run['public_id']}/run", headers=admin.auth_header)
    ).json()

    assert _step(body, AgentKey.NOTICE_ANALYST)["status"] == "DONE"
    estatistica = _step(body, AgentKey.STATISTICS)
    assert estatistica["status"] == "AWAITING_INPUT"
    assert "dados insuficientes" in (estatistica["detail"] or "")
    assert estatistica["attempts"] == 0, "falta de amostra não gasta tentativa"

    # O Professor rodou: é a correção da cascata.
    assert professor_rodou is True
    assert _step(body, AgentKey.TEACHER)["status"] == "SKIPPED"
    assert _step(body, AgentKey.TEACHER)["status"] != "BLOCKED"
    # E o tutor também não ficou preso à amostra.
    assert _step(body, AgentKey.TUTOR)["status"] != "BLOCKED"

    # Nada quebrou, e sobrou pendência: é "concluída com ressalvas".
    assert body["status"] == "DONE_WITH_NOTES"
    assert body["error"] is None

    # E o estado persistido concorda com o que a tela mostrou.
    linha = (
        await db_session.execute(
            select(AgentRunModel).where(AgentRunModel.public_id == run["public_id"])
        )
    ).scalar_one()
    passos = (
        (await db_session.execute(select(AgentStep).where(AgentStep.run_id == linha.id)))
        .scalars()
        .all()
    )
    por_chave = {item.agent_key: item for item in passos}
    assert linha.status == "DONE_WITH_NOTES"
    assert por_chave[AgentKey.STATISTICS].status == "AWAITING_INPUT"
    assert por_chave[AgentKey.STATISTICS].attempts == 0
