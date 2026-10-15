"""Mapas mentais, da matéria ao mapa publicado.

Três coisas são cobradas aqui com mais insistência que as outras:

*A IA propõe, uma pessoa publica.* Gerar deixa o mapa pronto para revisão, nunca
publicado — mapa mental é material de memorização.

*Lixo não vira mapa.* Resposta sem painéis, com tipo inventado ou com um painel
só é recusada, e o motivo fica gravado para quem revisa.

*O token é pago uma vez.* Gerar duas vezes o mesmo mapa não chama o provedor de
novo.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderCredentials
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin, create_user
from tests.fake_ai import FakeProvider

#: Resposta plausível de um modelo: painéis fora de ordem, um tipo inventado no
#: meio e um item sem fonte. É assim que a resposta real costuma chegar.
MAP_PAYLOAD: dict[str, Any] = {
    "center_label": "Princípios da Administração",
    "panels": [
        {
            "kind": "PEGADINHAS",
            "title": "O que a banca troca",
            "items": [
                {"text": "Trocar 'publicidade' por 'publicação'.", "tone": "ALERTA"},
                {"text": "Afirmar que a moralidade é facultativa.", "tone": "INCORRETO"},
            ],
        },
        {
            "kind": "CONCEITO",
            "title": "O que são",
            "items": [
                {
                    "text": "Vetores que orientam toda a atuação da Administração.",
                    "tone": "NEUTRO",
                    "source": "art. 37, caput, CF/88",
                }
            ],
        },
        {
            "kind": "REGRAS",
            "title": "LIMPE",
            "items": [
                {"text": "Legalidade", "tone": "CORRETO"},
                {"text": "Impessoalidade", "tone": "CORRETO"},
                {"text": "Moralidade", "tone": "CORRETO"},
            ],
        },
        # Tipo que não existe no catálogo: o mapa tem de sair sem ele.
        {"kind": "RESUMO_FINAL", "title": "Resumão", "items": [{"text": "Decore LIMPE."}]},
    ],
    "review_notes": ["Confirmar se o edital cobra eficiência como princípio expresso."],
}

CONTEUDO = (
    "Art. 37, caput, da CF/88: a administração pública obedecerá aos princípios "
    "de legalidade, impessoalidade, moralidade, publicidade e eficiência."
)


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Troca só o adaptador: o resto do caminho roda de verdade."""
    provider = FakeProvider(completion_payload=MAP_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _create_map(client: AsyncClient, admin: RegisteredUser, **overrides: Any) -> str:
    payload: dict[str, Any] = {
        "subject": "Direito Administrativo",
        "topic": "Princípios da Administração Pública",
        "level": "INTERMEDIARIO",
        "max_panels": 6,
        "source_content": CONTEUDO,
    }
    payload.update(overrides)
    created = await client.post("/api/v1/admin/mindmaps", headers=admin.auth_header, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "DRAFT"
    return str(created.json()["public_id"])


# --------------------------------------------------------------------------- #
# Catálogo de painéis
# --------------------------------------------------------------------------- #
async def test_panel_catalogue_is_fixed_and_carries_its_colours(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A cor é informação: o editor precisa recebê-la junto com o tipo."""
    admin = await create_admin(client, emails, email="mapa0@exemplo.com.br")

    response = await client.get("/api/v1/admin/mindmaps/panels", headers=admin.auth_header)

    assert response.status_code == 200, response.text
    panels = response.json()
    assert [item["kind"] for item in panels] == [
        "CONCEITO",
        "REGRAS",
        "CLASSIFICACOES",
        "APLICACAO",
        "EXCECOES",
        "ERROS_COMUNS",
        "MACETES",
        "PEGADINHAS",
    ]
    cores = {item["kind"]: item["color_token"] for item in panels}
    assert cores["CONCEITO"] == "game-blue"
    assert cores["MACETES"] == "game-gold"
    assert cores["PEGADINHAS"] == "game-orange"
    assert all(item["guidance"] for item in panels), "o editor precisa saber o que entra"


async def test_a_student_cannot_reach_the_studio(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.mapa0@exemplo.com.br")
    response = await client.get("/api/v1/admin/mindmaps", headers=student.auth_header)
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
# Sem provedor configurado
# --------------------------------------------------------------------------- #
async def test_generating_without_a_provider_is_refused_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="mapa1@exemplo.com.br")
    public_id = await _create_map(client, admin)

    response = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header
    )

    assert response.status_code >= 400
    # E o mapa não fica preso em GENERATING: volta para rascunho, com o motivo.
    reopened = await client.get(f"/api/v1/admin/mindmaps/{public_id}", headers=admin.auth_header)
    assert reopened.json()["status"] == "DRAFT"
    assert reopened.json()["generation_error"], "quem revisa precisa saber o que falhou"


# --------------------------------------------------------------------------- #
# Geração
# --------------------------------------------------------------------------- #
async def test_generation_builds_the_map_and_stops_before_publishing(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="mapa2@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)

    response = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # READY, não PUBLISHED: nada chega a quem estuda sem passar por uma pessoa.
    assert body["status"] == "READY"
    assert body["model_slug"] == "gpt-4o-mini"
    assert body["generated_at"]
    assert body["published_at"] is None

    content = body["content"]
    assert content["center_label"] == "Princípios da Administração"
    # Ordem de leitura fixa, mesmo com a IA respondendo fora de ordem.
    assert [panel["kind"] for panel in content["panels"]] == [
        "CONCEITO",
        "REGRAS",
        "PEGADINHAS",
    ]
    # O tipo inventado foi descartado em vez de virar painel sem cor nem sentido.
    assert "RESUMO_FINAL" not in json.dumps(content)


async def test_the_colours_and_the_notes_reach_the_reviewer(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="mapa3@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)

    content = (
        await client.post(f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header)
    ).json()["content"]

    paineis = {panel["kind"]: panel for panel in content["panels"]}
    assert paineis["PEGADINHAS"]["color_token"] == "game-orange"
    assert paineis["PEGADINHAS"]["items"][0]["tone_color"] == "game-orange"
    assert paineis["REGRAS"]["items"][0]["tone_color"] == "success"

    # Fonte só aparece quando veio do material; o resto fica vazio de propósito.
    conceito = paineis["CONCEITO"]["items"][0]
    assert conceito["source"] == "art. 37, caput, CF/88"
    assert all(item["source"] is None for item in paineis["REGRAS"]["items"])

    # A dúvida da IA não some: vai para quem revisa.
    assert content["review_notes"] == [
        "Confirmar se o edital cobra eficiência como princípio expresso."
    ]


async def test_the_study_material_reaches_the_model(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    """Fidelidade ao material enviado começa por enviá-lo."""
    admin = await create_admin(client, emails, email="mapa4@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)

    await client.post(f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header)

    enviado = fake_provider.completion_calls[0]
    system = enviado.messages[0].content
    user = enviado.messages[1].content
    assert "Não invente lei, artigo, súmula, data" in system
    assert "PEGADINHAS" in system, "o catálogo de painéis vai junto"
    assert CONTEUDO in user
    assert "Princípios da Administração Pública" in user
    assert enviado.json_response is True


async def test_generating_twice_does_not_pay_twice(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="mapa5@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)

    primeira = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header
    )
    assert primeira.status_code == 200
    assert len(fake_provider.completion_calls) == 1

    segunda = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header
    )

    assert segunda.status_code == 200
    assert len(fake_provider.completion_calls) == 1, "conteúdo igual não chama a API de novo"
    assert segunda.json()["content"] == primeira.json()["content"]


async def test_a_map_the_model_could_not_build_is_refused(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um painel só não é mapa mental, é um cartão com título."""
    provider = FakeProvider(
        completion_payload={
            "center_label": "Crase",
            "panels": [{"kind": "CONCEITO", "title": "O que é", "items": [{"text": "Fusão."}]}],
        }
    )

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="mapa6@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)

    response = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mindmap_invalid_content"

    reopened = await client.get(f"/api/v1/admin/mindmaps/{public_id}", headers=admin.auth_header)
    assert reopened.json()["status"] == "DRAFT"
    assert "painéis" in reopened.json()["generation_error"]
    assert reopened.json()["content"] == {}


async def test_a_map_without_panels_is_refused(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeProvider(raw_completion='{"center_label": "Nada"}')

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="mapa7@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)

    response = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "mindmap_invalid_content"


# --------------------------------------------------------------------------- #
# Revisão e publicação
# --------------------------------------------------------------------------- #
async def test_the_human_revision_goes_through_the_same_validation(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="mapa8@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)
    gerado = (
        await client.post(f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header)
    ).json()

    revisado = gerado["content"]
    revisado["panels"][0]["items"][0]["text"] = "Vetores que orientam a Administração Pública."

    saved = await client.put(
        f"/api/v1/admin/mindmaps/{public_id}/content",
        headers=admin.auth_header,
        json={"title": "Princípios — LIMPE", "content": revisado},
    )

    assert saved.status_code == 200, saved.text
    assert saved.json()["title"] == "Princípios — LIMPE"
    texto = saved.json()["content"]["panels"][0]["items"][0]["text"]
    assert texto == "Vetores que orientam a Administração Pública."

    # E um mapa quebrado pela mão humana é recusado do mesmo jeito.
    quebrado = await client.put(
        f"/api/v1/admin/mindmaps/{public_id}/content",
        headers=admin.auth_header,
        json={"title": "Princípios", "content": {"panels": []}},
    )
    assert quebrado.status_code == 422
    assert quebrado.json()["error"]["code"] == "mindmap_invalid_content"


async def test_only_a_published_map_reaches_the_student(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="mapa9@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.mapa9@exemplo.com.br")
    await configure_ai(client, admin, features=("mindmap.generation",))
    public_id = await _create_map(client, admin)
    await client.post(f"/api/v1/admin/mindmaps/{public_id}/generate", headers=admin.auth_header)

    # Pronto para revisão ainda não é material de estudo.
    antes = await client.get(f"/api/v1/mindmaps/{public_id}", headers=student.auth_header)
    assert antes.status_code == 404
    listado = await client.get("/api/v1/mindmaps", headers=student.auth_header)
    assert listado.json()["total"] == 0

    published = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/publish", headers=admin.auth_header
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"
    assert published.json()["published_at"]

    depois = await client.get(f"/api/v1/mindmaps/{public_id}", headers=student.auth_header)
    assert depois.status_code == 200
    assert depois.json()["content"]["panels"], "o aluno recebe o mapa inteiro"
    assert (await client.get("/api/v1/mindmaps", headers=student.auth_header)).json()["total"] == 1


async def test_an_empty_map_is_not_published(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="mapa10@exemplo.com.br")
    public_id = await _create_map(client, admin)

    response = await client.post(
        f"/api/v1/admin/mindmaps/{public_id}/publish", headers=admin.auth_header
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "mindmap_empty"


async def test_an_unknown_map_is_not_found(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="mapa11@exemplo.com.br")
    response = await client.get(
        "/api/v1/admin/mindmaps/mapa-que-nao-existe", headers=admin.auth_header
    )
    assert response.status_code == 404
