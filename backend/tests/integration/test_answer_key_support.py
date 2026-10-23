"""A conferência do gabarito por julgamento tipado, ponta a ponta.

Esta é a parte que fecha o buraco declarado na parte 2b: a conferência
determinística prova que a citação **existe** no material; o `Noul` do Jev dá
uma probabilidade de ela **sustentar** o gabarito. O que estes testes sustentam:

1. **Desligado, é "não conferido" — não é zero e não é aprovação.** A questão
   entra com a coluna nula e a resposta diz por quê.
2. **Ligado, a probabilidade fica gravada** e a fila de revisão ordena por ela,
   do respaldo mais fraco para o mais forte.
3. **O piso é escolha de quem administra.** Padrão zero: nada é descartado pelo
   julgamento até alguém decidir o contrário no painel.
4. **Falha no julgamento não derruba a geração.** A questão fica não conferida,
   com o motivo dito uma vez.
"""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderCredentials, ProviderRateLimitedError
from app.models.ai import AIFeature
from app.models.question import Question
from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, configure_ai, create_admin
from tests.fake_ai import FakeDecisionProvider, FakeProvider

MATERIAL = (
    "A crase é a contração da preposição A com o artigo feminino A. Não se usa "
    "crase antes de palavra masculina, antes de verbo e antes da maioria dos "
    "pronomes. Diante de nome de lugar, o teste é voltar de: se se volta da "
    "Bahia, vai-se à Bahia. A crase é obrigatória nas locuções adverbiais."
)


def _alternativas(indice_correta: int = 1) -> list[dict[str, Any]]:
    textos = [
        "É a contração de duas preposições iguais.",
        "É a contração da preposição A com o artigo feminino A.",
        "É o acento usado obrigatoriamente antes de verbo.",
        "É o acento usado antes de qualquer palavra masculina.",
    ]
    return [
        {
            "letter": letra,
            "content": texto,
            "is_correct": i == indice_correta,
            "feedback": "É o que o material diz." if i == indice_correta else "O material nega.",
        }
        for i, (letra, texto) in enumerate(zip("ABCD", textos, strict=True))
    ]


def _payload(quantas: int = 2) -> dict[str, Any]:
    enunciados = [
        "Assinale a alternativa que define corretamente o fenômeno da crase.",
        "Assinale a alternativa correta sobre o emprego do acento grave na crase.",
        "Assinale a alternativa correta quanto à contração da preposição com o artigo.",
    ]
    return {
        "questions": [
            {
                "statement": enunciados[i],
                "difficulty": "MEDIUM",
                "alternatives": _alternativas(),
                "explanation": "A definição está no material.",
                "quote": "A crase é a contração da preposição A com o artigo feminino A",
            }
            for i in range(quantas)
        ],
        "skipped_reason": None,
    }


@pytest.fixture
def geracao(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Troca só o adaptador de texto: a geração em si roda de verdade."""
    provider = FakeProvider(completion_payload=_payload())

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


def _bind_judgment(monkeypatch: pytest.MonkeyPatch, fake: FakeDecisionProvider) -> None:
    """Liga o provedor de julgamento falso no lugar do adaptador real."""

    def build(slug: str, credentials: ProviderCredentials) -> FakeDecisionProvider:
        fake.credentials = credentials
        return fake

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_decision_provider", build)


async def _configurar_julgamento(
    client: AsyncClient, admin: RegisteredUser, *, options: dict[str, Any] | None = None
) -> None:
    """Cadastra o provedor de julgamento e vincula a funcionalidade, pelo painel."""
    criado = await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "typesafe"}
    )
    assert criado.status_code in {200, 201}, criado.text
    chave = await client.put(
        "/api/v1/admin/ai/providers/typesafe/key",
        headers=admin.auth_header,
        json={"api_key": "sk-typesafe-chave-de-teste-123456"},
    )
    assert chave.status_code == 200, chave.text
    sincronizado = await client.post(
        "/api/v1/admin/ai/providers/typesafe/models/sync", headers=admin.auth_header
    )
    assert sincronizado.status_code == 200, sincronizado.text
    ativado = await client.patch(
        "/api/v1/admin/ai/providers/typesafe",
        headers=admin.auth_header,
        json={"is_active": True},
    )
    assert ativado.status_code == 200, ativado.text

    corpo: dict[str, Any] = {
        "provider_slug": "typesafe",
        "model_slug": "jev-fake",
        "is_enabled": True,
    }
    if options is not None:
        corpo.update(options)
    vinculado = await client.put(
        f"/api/v1/admin/ai/features/{AIFeature.ANSWER_KEY_SUPPORT}",
        headers=admin.auth_header,
        json=corpo,
    )
    assert vinculado.status_code == 200, vinculado.text


async def _gerar(client: AsyncClient, admin: RegisteredUser) -> dict[str, Any]:
    resposta = await client.post(
        "/api/v1/admin/questions/generate",
        headers=admin.auth_header,
        json={"material": MATERIAL, "quantity": 3},
    )
    assert resposta.status_code == 200, resposta.text
    return dict(resposta.json())


# --------------------------------------------------------------------------- #
# Desligado
# --------------------------------------------------------------------------- #
async def test_without_the_judgment_the_question_is_born_unchecked(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    geracao: FakeProvider,
) -> None:
    """Silêncio leria como "está tudo certo"; a resposta diz o motivo."""
    admin = await create_admin(client, emails, email="jev1@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))

    corpo = await _gerar(client, admin)

    assert corpo["created"]
    assert corpo["support"]["ran"] is False
    assert corpo["support"]["reason"]
    assert "julgamento" in corpo["support"]["reason"]
    assert all(item["answer_key_support"] is None for item in corpo["created"])

    linhas = (await db_session.execute(select(Question.answer_key_support))).scalars().all()
    assert all(valor is None for valor in linhas)


# --------------------------------------------------------------------------- #
# Ligado
# --------------------------------------------------------------------------- #
async def test_the_probability_is_recorded_and_orders_the_review_queue(
    client: AsyncClient,
    emails: CapturingDispatcher,
    geracao: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="jev2@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    julgador = FakeDecisionProvider(probabilities=[0.91, 0.24])
    _bind_judgment(monkeypatch, julgador)
    await _configurar_julgamento(client, admin)

    corpo = await _gerar(client, admin)

    assert corpo["support"]["ran"] is True
    assert corpo["support"]["judged"] == 2
    assert corpo["support"]["below_floor"] == 0
    assert corpo["support"]["model"] == "jev-fake"
    # Uma pergunta por rascunho aceito, e o estado leva a citação e as opções.
    assert len(julgador.calls) == 2
    estado = julgador.calls[0].state
    assert "citacao_do_material" in estado
    assert estado["alternativa_marcada_como_correta"].startswith("É a contração da preposição A")

    # A fila de revisão: respaldo mais fraco primeiro.
    fila = (
        await client.get(
            "/api/v1/admin/questions?page=1&page_size=20&status=DRAFT&order=support",
            headers=admin.auth_header,
        )
    ).json()
    apoios = [item["answer_key_support"] for item in fila["items"]]
    assert apoios == [0.24, 0.91]


async def test_the_floor_is_a_choice_and_defaults_to_discarding_nothing(
    client: AsyncClient,
    emails: CapturingDispatcher,
    geracao: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qualquer piso embutido por mim seria régua inventada decidindo o lixo."""
    admin = await create_admin(client, emails, email="jev3@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    _bind_judgment(monkeypatch, FakeDecisionProvider(probabilities=[0.05, 0.07]))
    await _configurar_julgamento(client, admin)

    corpo = await _gerar(client, admin)

    # Probabilidade baixíssima e nada descartado: o padrão não joga fora.
    assert corpo["support"]["floor"] == 0.0
    assert corpo["support"]["below_floor"] == 0
    assert len(corpo["created"]) == 2
    assert sorted(item["answer_key_support"] for item in corpo["created"]) == [0.05, 0.07]


async def test_with_a_floor_the_weakest_draft_is_discarded_with_the_number(
    client: AsyncClient,
    emails: CapturingDispatcher,
    geracao: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = await create_admin(client, emails, email="jev4@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    _bind_judgment(monkeypatch, FakeDecisionProvider(probabilities=[0.88, 0.19]))
    await _configurar_julgamento(client, admin, options={"min_support": 0.5})

    corpo = await _gerar(client, admin)

    assert corpo["support"]["floor"] == 0.5
    assert corpo["support"]["below_floor"] == 1
    assert len(corpo["created"]) == 1
    descartada = next(item for item in corpo["discarded"] if "19%" in item["reason"])
    assert "abaixo do piso de 50%" in descartada["reason"]


async def test_a_judgment_failure_does_not_break_the_generation(
    client: AsyncClient,
    emails: CapturingDispatcher,
    geracao: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A questão fica não conferida, e o motivo é dito uma vez — não por questão."""
    admin = await create_admin(client, emails, email="jev5@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    _bind_judgment(monkeypatch, FakeDecisionProvider(fail_with=ProviderRateLimitedError()))
    await _configurar_julgamento(client, admin)

    corpo = await _gerar(client, admin)

    assert len(corpo["created"]) == 2
    assert corpo["support"]["ran"] is False
    assert corpo["support"]["reason"]
    assert all(item["answer_key_support"] is None for item in corpo["created"])


# --------------------------------------------------------------------------- #
# A medição
# --------------------------------------------------------------------------- #
async def test_the_judgment_is_measured_like_any_other_ai_call(
    client: AsyncClient,
    emails: CapturingDispatcher,
    db_session: AsyncSession,
    geracao: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Julgamento é mais barato que texto, e "mais barato" não é "de graça"."""
    from app.models.ai import AIUsage

    admin = await create_admin(client, emails, email="jev6@exemplo.com.br")
    await configure_ai(client, admin, features=("question.generation",))
    _bind_judgment(monkeypatch, FakeDecisionProvider(probabilities=[0.8, 0.8]))
    await _configurar_julgamento(client, admin)

    await _gerar(client, admin)

    linhas = (
        (
            await db_session.execute(
                select(AIUsage).where(AIUsage.feature == AIFeature.ANSWER_KEY_SUPPORT)
            )
        )
        .scalars()
        .all()
    )
    assert len(linhas) == 2
    assert {linha.provider_slug for linha in linhas} == {"typesafe"}
    assert {linha.model_slug for linha in linhas} == {"jev-fake"}
    assert all(linha.input_tokens == 90 for linha in linhas)
    assert all(linha.status == "SUCCESS" for linha in linhas)
