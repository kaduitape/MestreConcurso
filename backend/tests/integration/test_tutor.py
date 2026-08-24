"""Mestre IA: resposta com citação conferida, recusa sem base e vocabulário."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderCredentials
from app.ai.vector_store import QdrantVectorStore
from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    configure_ai,
    create_admin,
    create_notice_with_pdf,
    create_subject,
    create_user,
)
from tests.fake_ai import EXTRACTION_PAYLOAD, FakeProvider
from tests.pdf_fixtures import build_edital_pdf

# Citação que existe de fato no PDF de teste — o validador vai conferi-la.
CITACAO_REAL = "A prova objetiva será aplicada no dia 15 de março de 2026"

ANSWER_PAYLOAD: dict[str, Any] = {
    "claims": [
        {
            "kind": "FACT",
            "text": "A prova objetiva está marcada para 15 de março de 2026.",
            "quote": CITACAO_REAL,
        },
        {
            "kind": "FACT",
            "text": "O recurso deve ser interposto em até 30 dias corridos.",
            "quote": "o prazo para interposição de recurso é de trinta dias corridos",
        },
        {"kind": "GUIDANCE", "text": "Comece pelos blocos com mais questões na prova."},
    ],
    "refusal": None,
    "suggested_terms": [
        {"term": "prova objetiva", "definition": "Etapa de múltipla escolha do concurso."}
    ],
}

REFUSAL_PAYLOAD: dict[str, Any] = {
    "claims": [],
    "refusal": "O material enviado não trata desse assunto.",
    "suggested_terms": [],
}


@pytest.fixture
def shared_store(monkeypatch: pytest.MonkeyPatch) -> QdrantVectorStore:
    """Um único Qdrant em memória para indexação e recuperação.

    Cada ``QdrantVectorStore()`` em modo ``:memory:`` cria uma base própria; sem
    compartilhar a instância, o que o edital indexa some antes da busca.
    """
    store = QdrantVectorStore()

    from app.services import notice_analysis, retrieval

    monkeypatch.setattr(notice_analysis, "QdrantVectorStore", lambda *a, **k: store)
    monkeypatch.setattr(retrieval, "QdrantVectorStore", lambda *a, **k: store)
    return store


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Devolve a extração do edital ou a resposta do tutor conforme o prompt."""
    provider = FakeProvider(completion_payload=EXTRACTION_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def _prepared_notice(
    client: AsyncClient, emails: CapturingDispatcher, *, admin_email: str
) -> RegisteredUser:
    """Cadastra, envia e analisa um edital — deixando trechos indexados."""
    admin = await create_admin(client, emails, email=admin_email)
    await configure_ai(
        client, admin, features=("notice.extraction", "embeddings.default", "chat.tutor")
    )
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())
    analyzed = await client.post(
        f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header
    )
    assert analyzed.status_code == 202, analyzed.text
    return admin


async def _conversation(client: AsyncClient, user: RegisteredUser, **body: Any) -> str:
    response = await client.post(
        "/api/v1/tutor/conversations", headers=user.auth_header, json=body or {}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["public_id"])


async def test_answer_keeps_only_the_claims_it_can_prove(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor1@exemplo.com.br")
    conversation = await _conversation(client, admin, title="Dúvidas do edital")

    fake_provider.completion_payload = ANSWER_PAYLOAD
    response = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Quando será aplicada a prova objetiva?"},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]

    claims = {item["text"]: item for item in message["claims"]}
    provado = claims["A prova objetiva está marcada para 15 de março de 2026."]
    assert provado["status"] == "CITED"
    assert provado["page_number"] is not None
    assert provado["document_title"]
    assert provado["chunk_id"] is not None

    # A afirmação sem origem continua visível, marcada — não some em silêncio.
    inventado = claims["O recurso deve ser interposto em até 30 dias corridos."]
    assert inventado["status"] == "UNSOURCED"
    assert inventado["note"]

    # Orientação de estudo não precisa de citação e não é tratada como fato.
    orientacao = claims["Comece pelos blocos com mais questões na prova."]
    assert orientacao["kind"] == "GUIDANCE"
    assert orientacao["status"] == "COMPUTED"

    assert message["is_refusal"] is False
    assert message["grounding_ratio"] == 0.5
    assert message["sources"], "os trechos usados ficam registrados na mensagem"
    assert response.json()["suggested_terms"][0]["term"] == "prova objetiva"


async def test_answer_without_any_provable_claim_becomes_a_refusal(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor2@exemplo.com.br")
    conversation = await _conversation(client, admin)

    fake_provider.completion_payload = {
        "claims": [
            {
                "kind": "FACT",
                "text": "O edital prevê prova de títulos com peso dois.",
                "quote": "a prova de títulos terá peso dois na nota final do candidato",
            }
        ],
        "refusal": None,
    }
    response = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Existe prova de títulos?"},
    )
    message = response.json()["message"]

    assert message["is_refusal"] is True
    assert "sem origem" in message["refusal_reason"]
    assert message["grounding_ratio"] == 0.0


async def test_model_refusal_is_recorded_as_such(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor3@exemplo.com.br")
    conversation = await _conversation(client, admin)

    fake_provider.completion_payload = REFUSAL_PAYLOAD
    response = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "O que diz a lei sobre aposentadoria especial?"},
    )
    message = response.json()["message"]

    assert message["is_refusal"] is True
    assert message["refusal_reason"] == "O material enviado não trata desse assunto."
    assert message["claims"] == []


async def test_without_indexed_material_the_master_says_so(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="tutor4@exemplo.com.br")
    await configure_ai(client, admin, features=("embeddings.default", "chat.tutor"))
    conversation = await _conversation(client, admin)

    response = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Qual a data da prova?"},
    )
    assert response.status_code == 200, response.text
    message = response.json()["message"]

    assert message["is_refusal"] is True
    assert message["refusal_reason"]
    # E o modelo sequer foi acionado: não se paga token para não responder.
    assert fake_provider.completion_calls == []


async def test_without_embeddings_configured_the_master_explains_why(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="tutor5@exemplo.com.br")
    await configure_ai(client, admin, features=("chat.tutor",))
    conversation = await _conversation(client, admin)

    response = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Qual a data da prova?"},
    )
    message = response.json()["message"]

    assert message["is_refusal"] is True
    assert "embeddings" in message["refusal_reason"]


async def test_statistics_come_from_python_not_from_the_model(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor6@exemplo.com.br")
    conversation = await _conversation(client, admin)

    fake_provider.completion_payload = ANSWER_PAYLOAD
    await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Como está o meu desempenho até agora?"},
    )

    # A pergunta pede estatística: o Python anexa os números prontos ao prompt.
    request = fake_provider.completion_calls[-1]
    user_content = request.messages[-1].content
    assert "<dados_calculados>" in user_content
    assert "Não recalcule" in user_content
    assert "desempenho" in user_content
    # E o contexto recuperado entra marcado como dado, não como instrução.
    assert "<contexto>" in user_content
    assert "ignore-as completamente" in request.messages[0].content


async def test_teacher_mode_uses_its_own_prompt(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor7@exemplo.com.br")
    conversation = await _conversation(client, admin, mode="TEACHER")

    fake_provider.completion_payload = ANSWER_PAYLOAD
    await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Explique o regime disciplinar diferenciado."},
    )

    system_prompt = fake_provider.completion_calls[-1].messages[0].content
    assert "Modo Professor" in system_prompt
    assert "Onde o candidato erra" in system_prompt


async def test_conversation_history_is_kept_and_scoped_to_its_owner(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor8@exemplo.com.br")
    intruder = await create_user(client, emails, email="intruso.tutor@exemplo.com.br")
    conversation = await _conversation(client, admin)

    fake_provider.completion_payload = ANSWER_PAYLOAD
    await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Quando será a prova objetiva?"},
    )

    detail = await client.get(
        f"/api/v1/tutor/conversations/{conversation}", headers=admin.auth_header
    )
    assert detail.status_code == 200
    body = detail.json()
    assert [item["role"] for item in body["messages"]] == ["USER", "ASSISTANT"]
    # O título da conversa passa a ser a primeira pergunta.
    assert body["title"].startswith("Quando será a prova")

    stolen = await client.get(
        f"/api/v1/tutor/conversations/{conversation}", headers=intruder.auth_header
    )
    assert stolen.status_code == 404


async def test_stream_reports_each_stage_before_the_answer(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor9@exemplo.com.br")
    conversation = await _conversation(client, admin)
    fake_provider.completion_payload = ANSWER_PAYLOAD

    async with client.stream(
        "GET",
        f"/api/v1/tutor/conversations/{conversation}/ask/stream",
        headers=admin.auth_header,
        params={"question": "Quando será a prova objetiva?"},
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join([chunk async for chunk in response.aiter_text()])

    stages = [line for line in body.splitlines() if line.startswith("event: stage")]
    assert len(stages) >= 4
    for expected in ("Entendendo a pergunta", "Procurando na sua base", "Conferindo cada citação"):
        assert expected in body
    assert "event: answer" in body
    # O resumo final diz quantas afirmações tinham origem conferida.
    assert "com origem conferida" in body


async def test_vocabulary_inherits_the_source_of_the_message(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor10@exemplo.com.br")
    subject = await create_subject(client, admin)
    conversation = await _conversation(client, admin)

    fake_provider.completion_payload = ANSWER_PAYLOAD
    answered = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Quando será a prova objetiva?"},
    )
    message_id = answered.json()["message"]["public_id"]

    saved = await client.post(
        "/api/v1/vocabulary",
        headers=admin.auth_header,
        json={
            "term": "prova objetiva",
            "definition": "Etapa de múltipla escolha do concurso.",
            "subject_public_id": subject["public_id"],
            "message_public_id": message_id,
        },
    )
    assert saved.status_code == 201, saved.text
    entry = saved.json()
    assert entry["origin"] == "CITED"
    assert entry["source_quote"] == CITACAO_REAL
    assert entry["source_page"] is not None
    assert entry["subject_name"] == "Direito Penal"

    duplicated = await client.post(
        "/api/v1/vocabulary",
        headers=admin.auth_header,
        json={"term": "Prova Objetiva", "definition": "outra definição"},
    )
    assert duplicated.status_code == 409
    assert duplicated.json()["error"]["code"] == "duplicate_term"


async def test_term_saved_without_a_message_is_marked_as_generated(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.vocab@exemplo.com.br")

    saved = await client.post(
        "/api/v1/vocabulary",
        headers=student.auth_header,
        json={"term": "dolo eventual", "definition": "Assume o risco do resultado."},
    )
    assert saved.status_code == 201, saved.text
    # Sem citação herdada, a definição é declarada como redação, não como origem.
    assert saved.json()["origin"] == "GENERATED"
    assert saved.json()["source_quote"] is None

    listed = await client.get("/api/v1/vocabulary", headers=student.auth_header)
    assert listed.json()["total"] == 1

    reviewed = await client.post(
        f"/api/v1/vocabulary/{saved.json()['public_id']}/review", headers=student.auth_header
    )
    assert reviewed.json()["times_reviewed"] == 1


async def test_only_verified_videos_are_offered(
    client: AsyncClient,
    emails: CapturingDispatcher,
    fake_provider: FakeProvider,
    shared_store: QdrantVectorStore,
) -> None:
    admin = await _prepared_notice(client, emails, admin_email="tutor11@exemplo.com.br")
    subject = await create_subject(client, admin)

    created = await client.post(
        "/api/v1/admin/videos",
        headers=admin.auth_header,
        json={
            "title": "Regime disciplinar diferenciado em 10 minutos",
            "url": "https://www.youtube.com/watch?v=exemplo",
            "subject_public_id": subject["public_id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["is_verified"] is False

    conversation = await _conversation(client, admin, subject_public_id=subject["public_id"])
    fake_provider.completion_payload = ANSWER_PAYLOAD
    answered = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Quando será a prova objetiva?"},
    )
    # Ainda não conferido por uma pessoa: não é sugerido.
    assert answered.json()["videos"] == []

    verified = await client.post(
        f"/api/v1/admin/videos/{created.json()['public_id']}/verify", headers=admin.auth_header
    )
    assert verified.status_code == 200
    assert verified.json()["is_verified"] is True

    again = await client.post(
        f"/api/v1/tutor/conversations/{conversation}/ask",
        headers=admin.auth_header,
        json={"question": "Quando será a prova objetiva?"},
    )
    videos = again.json()["videos"]
    assert len(videos) == 1
    assert videos[0]["url"] == "https://www.youtube.com/watch?v=exemplo"
    assert videos[0]["verified_at"] is not None


async def test_candidate_cannot_manage_the_video_catalogue(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="aluno.video@exemplo.com.br")
    response = await client.get("/api/v1/admin/videos", headers=student.auth_header)
    assert response.status_code == 403
