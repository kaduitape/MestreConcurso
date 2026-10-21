"""Roteador de modelos: a regra vale, a escolha fica registrada e a reserva existe.

O teste que pesa mais aqui é ``test_the_usage_row_points_at_the_decision``: é
ele que cobra o critério de aceite da fase — poder dizer, para uma linha de
gasto, por que aquele modelo foi usado naquela execução. Sem o vínculo entre
``ai_usage`` e ``ai_routing_decisions``, a resposta seria aproximação de
horário entre duas tabelas.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    CompletionRequest,
    CompletionResult,
    ModelInfo,
    ProviderCredentials,
    ProviderRateLimitedError,
)
from app.models.ai import AIUsage
from tests.conftest import CapturingDispatcher
from tests.factories import (
    configure_ai,
    create_admin,
    create_question,
    create_subject,
    create_user,
)
from tests.fake_ai import CLASSIFY_PAYLOAD, FakeProvider

ENUNCIADO = (
    "Segundo o Código Penal, o homicídio praticado por motivo fútil é classificado como "
    "qualificado, e a pena é agravada na forma prevista em lei."
)


class TwoModelProvider(FakeProvider):
    """Expõe dois modelos de chat — o roteador precisa de para onde ir.

    O ``FakeProvider`` padrão lista um único modelo de chat, e uma regra que
    aponta para o mesmo modelo do vínculo não provaria nada.
    """

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(slug="gpt-4o-mini", display_name="gpt-4o-mini", kind="chat"),
            ModelInfo(slug="gpt-4o", display_name="gpt-4o", kind="chat", supports_json=True),
            ModelInfo(
                slug="text-embedding-3-small",
                display_name="text-embedding-3-small",
                kind="embedding",
            ),
        ]


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> TwoModelProvider:
    provider = TwoModelProvider(completion_payload=CLASSIFY_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> TwoModelProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


class FlakyProvider(TwoModelProvider):
    """Recusa o modelo principal com limite de requisições; atende os outros."""

    def __init__(self, *, failing_model: str) -> None:
        super().__init__(completion_payload=CLASSIFY_PAYLOAD)
        self.failing_model = failing_model
        self.attempts: list[str] = []

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.attempts.append(request.model)
        if request.model == self.failing_model:
            raise ProviderRateLimitedError("o provedor limitou as requisições")
        return await super().complete(request)


async def _question(client: AsyncClient, admin: Any) -> str:
    await create_subject(client, admin, name="Direito Penal")
    created = await create_question(client, admin, statement=ENUNCIADO)
    return str(created["public_id"])


# --------------------------------------------------------------------------- #
# Acesso
# --------------------------------------------------------------------------- #
async def test_student_cannot_see_or_change_routing_rules(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.rota@exemplo.com.br")

    listagem = await client.get("/api/v1/admin/ai/routes", headers=student.auth_header)
    assert listagem.status_code == 403

    criacao = await client.post(
        "/api/v1/admin/ai/routes",
        headers=student.auth_header,
        json={
            "feature": "question.classify",
            "label": "Qualquer",
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
        },
    )
    assert criacao.status_code == 403


# --------------------------------------------------------------------------- #
# Cadastro das regras
# --------------------------------------------------------------------------- #
async def test_a_rule_is_registered_with_its_conditions_and_required_signals(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota1@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    criada = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Enunciado longo",
            "priority": 10,
            "is_enabled": True,
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
            "min_input_chars": 50,
        },
    )
    assert criada.status_code == 201, criada.text
    corpo = criada.json()
    assert corpo["model_slug"] == "gpt-4o"
    assert corpo["model_is_usable"] is True
    assert corpo["required_signals"] == ["INPUT_CHARS"]

    listagem = await client.get(
        "/api/v1/admin/ai/routes?feature=question.classify", headers=admin.auth_header
    )
    assert [item["label"] for item in listagem.json()] == ["Enunciado longo"]


async def test_a_window_with_minimum_above_maximum_is_refused(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota2@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    recusada = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Impossível",
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
            "min_input_chars": 9_000,
            "max_input_chars": 100,
        },
    )
    assert recusada.status_code == 422
    assert recusada.json()["error"]["code"] == "ai_route_impossible_condition"


async def test_embeddings_cannot_be_routed_because_the_vector_space_would_change(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    """Vetor de outro modelo vive em outro espaço — a busca compararia o incomparável."""
    admin = await create_admin(client, emails, email="rota3@exemplo.com.br")
    await configure_ai(client, admin, features=("embeddings.default",))

    recusada = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "embeddings.default",
            "label": "Economizar embedding",
            "provider_slug": "openai",
            "model_slug": "text-embedding-3-small",
        },
    )
    assert recusada.status_code == 422
    assert recusada.json()["error"]["code"] == "ai_route_feature_not_routable"
    assert "outro espaço" in recusada.json()["error"]["message"]


async def test_narration_cannot_be_routed_because_the_voice_would_change(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota4@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    recusada = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "training.narration",
            "label": "Narração barata",
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
        },
    )
    assert recusada.status_code == 422
    assert recusada.json()["error"]["code"] == "ai_route_feature_not_routable"


async def test_a_rule_cannot_point_a_text_feature_at_an_embedding_model(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota14@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    recusada = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Modelo errado",
            "provider_slug": "openai",
            "model_slug": "text-embedding-3-small",
        },
    )
    assert recusada.status_code == 422
    assert recusada.json()["error"]["code"] == "ai_route_model_kind_mismatch"


async def test_conditions_are_only_cleared_when_asked_explicitly(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota5@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    criada = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Com condição",
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
            "min_input_chars": 100,
        },
    )
    route_id = criada.json()["id"]

    # Trocar o rótulo não apaga a condição.
    renomeada = await client.patch(
        f"/api/v1/admin/ai/routes/{route_id}",
        headers=admin.auth_header,
        json={"label": "Nome novo"},
    )
    assert renomeada.json()["min_input_chars"] == 100

    limpa = await client.patch(
        f"/api/v1/admin/ai/routes/{route_id}",
        headers=admin.auth_header,
        json={"clear_conditions": True},
    )
    assert limpa.json()["min_input_chars"] is None
    assert limpa.json()["required_signals"] == []

    removida = await client.delete(f"/api/v1/admin/ai/routes/{route_id}", headers=admin.auth_header)
    assert removida.status_code == 200
    vazio = await client.get(
        "/api/v1/admin/ai/routes?feature=question.classify", headers=admin.auth_header
    )
    assert vazio.json() == []


# --------------------------------------------------------------------------- #
# A regra valendo numa chamada de verdade
# --------------------------------------------------------------------------- #
async def test_a_matching_rule_changes_the_model_that_is_actually_called(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota6@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    public_id = await _question(client, admin)

    await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Enunciado longo",
            "priority": 10,
            "is_enabled": True,
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
            "min_input_chars": 50,
        },
    )

    sugerida = await client.post(
        f"/api/v1/admin/questions/{public_id}/suggest-classification", headers=admin.auth_header
    )
    assert sugerida.status_code == 200, sugerida.text

    # O vínculo aponta gpt-4o-mini; a regra levou a chamada para o gpt-4o.
    assert [call.model for call in fake_provider.completion_calls] == ["gpt-4o"]

    historico = await client.get(
        "/api/v1/admin/ai/routes/decisions?feature=question.classify",
        headers=admin.auth_header,
    )
    assert historico.status_code == 200
    decisao = historico.json()[0]
    assert decisao["reason"] == "RULE_MATCHED"
    assert decisao["model_slug"] == "gpt-4o"
    assert decisao["route_label"] == "Enunciado longo"
    assert decisao["signals"]["needs_json"] is True
    assert decisao["signals"]["input_chars"] >= 50
    assert decisao["trace"][0]["outcome"] == "MATCHED"


async def test_a_disabled_rule_does_not_change_the_model(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota7@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    public_id = await _question(client, admin)

    await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Desligada",
            "is_enabled": False,
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
            "min_input_chars": 1,
        },
    )

    await client.post(
        f"/api/v1/admin/questions/{public_id}/suggest-classification", headers=admin.auth_header
    )

    assert [call.model for call in fake_provider.completion_calls] == ["gpt-4o-mini"]
    historico = await client.get(
        "/api/v1/admin/ai/routes/decisions?feature=question.classify",
        headers=admin.auth_header,
    )
    decisao = historico.json()[0]
    assert decisao["reason"] == "BINDING_DEFAULT"
    assert decisao["trace"][0]["outcome"] == "DISABLED"


async def test_a_rule_that_needs_a_missing_signal_is_recorded_as_not_evaluated(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    """Sem teto mensal cadastrado não existe percentual do teto.

    A regra não é tratada como "0% gastos, logo não atende": ela fica **não
    avaliada**, e o histórico diz qual sinal faltou. É a diferença entre não
    saber e afirmar que é zero.
    """
    admin = await create_admin(client, emails, email="rota8@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    public_id = await _question(client, admin)

    await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Orçamento apertado",
            "is_enabled": True,
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
            "min_budget_used_pct": 80,
        },
    )

    await client.post(
        f"/api/v1/admin/questions/{public_id}/suggest-classification", headers=admin.auth_header
    )

    historico = await client.get(
        "/api/v1/admin/ai/routes/decisions?feature=question.classify",
        headers=admin.auth_header,
    )
    decisao = historico.json()[0]
    assert decisao["reason"] == "BINDING_DEFAULT"
    assert decisao["trace"][0]["outcome"] == "NOT_EVALUATED"
    assert decisao["trace"][0]["missing_signals"] == ["BUDGET_USED_PCT"]
    assert "BUDGET_USED_PCT" not in decisao["signals"]


async def test_the_usage_row_points_at_the_decision(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: TwoModelProvider,
    db_session: AsyncSession,
) -> None:
    """O critério de aceite da fase, verificado no banco."""
    admin = await create_admin(client, emails, email="rota9@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    public_id = await _question(client, admin)

    await client.post(
        f"/api/v1/admin/questions/{public_id}/suggest-classification", headers=admin.auth_header
    )

    linhas = (
        (await db_session.execute(select(AIUsage).where(AIUsage.feature == "question.classify")))
        .scalars()
        .all()
    )
    assert len(linhas) == 1
    assert linhas[0].routing_decision_id is not None

    historico = await client.get(
        "/api/v1/admin/ai/routes/decisions?feature=question.classify",
        headers=admin.auth_header,
    )
    ids = {item["id"] for item in historico.json()}
    assert linhas[0].routing_decision_id in ids


# --------------------------------------------------------------------------- #
# Modelo de reserva
# --------------------------------------------------------------------------- #
async def test_the_reserve_model_must_differ_from_the_main_one(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    admin = await create_admin(client, emails, email="rota10@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    recusada = await client.put(
        "/api/v1/admin/ai/features/question.classify",
        headers=admin.auth_header,
        json={
            "provider_slug": "openai",
            "model_slug": "gpt-4o-mini",
            "fallback_provider_slug": "openai",
            "fallback_model_slug": "gpt-4o-mini",
            "is_enabled": True,
        },
    )
    assert recusada.status_code == 422
    assert recusada.json()["error"]["code"] == "ai_fallback_same_model"


async def test_a_rate_limited_model_hands_the_call_to_the_reserve(
    client: AsyncClient,
    emails: CapturingDispatcher,
    monkeypatch: pytest.MonkeyPatch,
    db_session: AsyncSession,
) -> None:
    provider = FlakyProvider(failing_model="gpt-4o-mini")

    def build(slug: str, credentials: ProviderCredentials) -> FlakyProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="rota11@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    public_id = await _question(client, admin)

    vinculada = await client.put(
        "/api/v1/admin/ai/features/question.classify",
        headers=admin.auth_header,
        json={
            "provider_slug": "openai",
            "model_slug": "gpt-4o-mini",
            "fallback_provider_slug": "openai",
            "fallback_model_slug": "gpt-4o",
            "is_enabled": True,
        },
    )
    assert vinculada.status_code == 200, vinculada.text
    assert vinculada.json()["fallback_model_slug"] == "gpt-4o"
    assert vinculada.json()["fallback_is_usable"] is True

    sugerida = await client.post(
        f"/api/v1/admin/questions/{public_id}/suggest-classification", headers=admin.auth_header
    )
    assert sugerida.status_code == 200, sugerida.text
    assert provider.attempts == ["gpt-4o-mini", "gpt-4o"]

    # As duas chamadas aparecem na conta: a que falhou consumiu tempo e pode
    # ter consumido token. Somar as duas num registro só esconderia uma.
    linhas = (
        (
            await db_session.execute(
                select(AIUsage).where(AIUsage.feature == "question.classify").order_by(AIUsage.id)
            )
        )
        .scalars()
        .all()
    )
    assert [(linha.model_slug, linha.status) for linha in linhas] == [
        ("gpt-4o-mini", "ERROR"),
        ("gpt-4o", "SUCCESS"),
    ]

    historico = await client.get(
        "/api/v1/admin/ai/routes/decisions?feature=question.classify",
        headers=admin.auth_header,
    )
    motivos = [item["reason"] for item in historico.json()]
    assert "FALLBACK_AFTER_ERROR" in motivos
    desvio = next(item for item in historico.json() if item["reason"] == "FALLBACK_AFTER_ERROR")
    assert desvio["model_slug"] == "gpt-4o"
    assert "ai_provider_rate_limited" in desvio["explanation"]


async def test_without_a_reserve_the_provider_error_still_surfaces(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FlakyProvider(failing_model="gpt-4o-mini")

    def build(slug: str, credentials: ProviderCredentials) -> FlakyProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="rota12@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))
    public_id = await _question(client, admin)

    resposta = await client.post(
        f"/api/v1/admin/questions/{public_id}/suggest-classification", headers=admin.auth_header
    )
    assert resposta.status_code == 429
    assert provider.attempts == ["gpt-4o-mini"]


# --------------------------------------------------------------------------- #
# Teto de regras
# --------------------------------------------------------------------------- #
async def test_the_number_of_rules_per_feature_is_capped(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: TwoModelProvider
) -> None:
    from app.domain.model_routing import MAX_RULES_PER_FEATURE

    admin = await create_admin(client, emails, email="rota13@exemplo.com.br")
    await configure_ai(client, admin, features=("question.classify",))

    for indice in range(MAX_RULES_PER_FEATURE):
        criada = await client.post(
            "/api/v1/admin/ai/routes",
            headers=admin.auth_header,
            json={
                "feature": "question.classify",
                "label": f"Regra {indice}",
                "priority": indice,
                "provider_slug": "openai",
                "model_slug": "gpt-4o",
            },
        )
        assert criada.status_code == 201, criada.text

    excedente = await client.post(
        "/api/v1/admin/ai/routes",
        headers=admin.auth_header,
        json={
            "feature": "question.classify",
            "label": "Uma a mais",
            "provider_slug": "openai",
            "model_slug": "gpt-4o",
        },
    )
    assert excedente.status_code == 422
    assert excedente.json()["error"]["code"] == "ai_route_limit_reached"
