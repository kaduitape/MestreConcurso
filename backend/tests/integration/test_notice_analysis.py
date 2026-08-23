"""Pipeline completo de análise de edital, do PDF ao Raio-X."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.ai.base import ProviderCredentials
from app.models.notice_analysis import EvidenceLevel
from tests.conftest import CapturingDispatcher
from tests.factories import (
    configure_ai,
    create_admin,
    create_notice_with_pdf,
    create_user,
)
from tests.fake_ai import EXTRACTION_PAYLOAD, FakeProvider
from tests.pdf_fixtures import build_edital_pdf, build_scanned_pdf


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Substitui o adaptador real mantendo todo o resto do caminho intacto."""
    provider = FakeProvider(completion_payload=EXTRACTION_PAYLOAD)

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        provider.credentials = credentials
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)
    return provider


async def test_full_pipeline_produces_facts_with_evidence(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia1@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header
    )
    assert response.status_code == 202, response.text
    assert response.json()["executed_inline"] is True

    state = await client.get(
        f"/api/v1/admin/notices/{notice_id}/analysis", headers=admin.auth_header
    )
    assert state.status_code == 200
    body = state.json()
    assert body["status"] == "AWAITING_CONFIRMATION"
    assert body["error"] is None
    steps = {step["key"]: step["status"] for step in body["steps"]}
    assert steps["read"] == "DONE"
    assert steps["extract"] == "DONE"
    assert steps["structure"] == "DONE"
    assert steps["ai"] == "DONE"
    assert steps["verify"] == "DONE"
    assert steps["persist"] == "DONE"
    # Sem modelo de embeddings configurado, a indexação é pulada com motivo explícito.
    assert steps["index"] == "SKIPPED"


async def test_quote_decides_what_is_official(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia2@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())
    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    radiography = await client.get(
        f"/api/v1/admin/notices/{notice_id}/radiography", headers=admin.auth_header
    )
    assert radiography.status_code == 200
    facts = {fact["field_path"]: fact for fact in radiography.json()["facts"]}

    salary = facts["position.salary_cents"]
    assert salary["evidence_level"] == EvidenceLevel.OFFICIAL
    assert salary["page_number"] == 1
    assert "8.157,00" in (salary["quote"] or "")

    # A citação inventada pelo modelo NÃO promove o campo a oficial.
    min_score = facts["exam.min_score_rule"]
    assert min_score["evidence_level"] == EvidenceLevel.INFERRED
    assert min_score["page_number"] is None


async def test_radiography_numbers_come_from_python(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia3@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())
    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    body = (
        await client.get(
            f"/api/v1/admin/notices/{notice_id}/radiography", headers=admin.auth_header
        )
    ).json()

    assert body["subjects_count"] == 3
    assert body["topics_count"] == 5
    assert body["questions_count"] == 120
    assert body["vacancies"] == 1200
    assert body["salary_cents"] == 815700
    assert body["page_count"] == 4
    assert body["exam_date"] == "2026-03-15"

    # Cobertura calculada sobre os níveis de prova, não estimada.
    coverage = body["coverage"]
    assert coverage["total"] == 15
    assert coverage["official"] >= 12
    assert 0 < coverage["proven_ratio"] <= 1

    # Evento sem data legível é descartado em vez de virar data inventada.
    kinds = [event["kind"] for event in body["events"]]
    assert kinds == ["EXAM", "PHYSICAL_TEST"]
    assert [event["kind"] for event in body["critical_events"]] == ["EXAM", "PHYSICAL_TEST"]

    # Disciplina sem conteúdo programático vira ponto de atenção.
    attention = {point["kind"] for point in body["attention_points"]}
    assert "SUBJECTS_WITHOUT_TOPICS" in attention
    assert "NEEDS_REVIEW" in attention

    largest = body["largest_subjects"][0]
    assert largest["name"] == "Língua Portuguesa"
    assert largest["topics_count"] == 3


async def test_second_analysis_reuses_document_and_cache(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia4@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)
    assert len(fake_provider.completion_calls) == 1

    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)
    # Mesmo PDF, mesmo modelo, mesmo prompt: nenhuma nova chamada paga.
    assert len(fake_provider.completion_calls) == 1

    state = (
        await client.get(f"/api/v1/admin/notices/{notice_id}/analysis", headers=admin.auth_header)
    ).json()
    steps = {step["key"]: step for step in state["steps"]}
    assert steps["ai"]["status"] == "SKIPPED"
    assert "nenhum token" in (steps["ai"]["detail"] or "")
    assert steps["extract"]["status"] == "SKIPPED"

    cache = (await client.get("/api/v1/admin/ai/cache", headers=admin.auth_header)).json()
    assert cache["entries"] == 1
    assert cache["total_hits"] == 1
    assert cache["tokens_saved"] == 1600


async def test_document_is_sent_as_untrusted_data(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia5@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())
    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    request = fake_provider.completion_calls[0]
    user_message = request.messages[-1].content
    assert "<untrusted_document>" in user_message
    assert "</untrusted_document>" in user_message
    # O prompt de sistema instrui explicitamente a ignorar ordens vindas do PDF.
    assert "ignore-os completamente" in request.messages[0].content
    assert request.json_response is True


async def test_indexing_runs_when_embeddings_are_configured(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia6@exemplo.com.br")
    await configure_ai(client, admin, features=("notice.extraction", "embeddings.default"))
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    state = (
        await client.get(f"/api/v1/admin/notices/{notice_id}/analysis", headers=admin.auth_header)
    ).json()
    index_step = next(step for step in state["steps"] if step["key"] == "index")
    assert index_step["status"] == "DONE"
    assert "trechos indexados" in (index_step["detail"] or "")
    assert fake_provider.embedding_calls, "os trechos deveriam ter sido vetorizados"


async def test_scanned_pdf_fails_with_actionable_message(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia7@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_scanned_pdf())

    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ocr_required"

    state = (
        await client.get(f"/api/v1/admin/notices/{notice_id}/analysis", headers=admin.auth_header)
    ).json()
    assert state["status"] == "FAILED"
    assert "digitalizado" in state["error"]
    assert any(step["status"] == "FAILED" for step in state["steps"])


async def test_analysis_requires_configured_model(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="edital.ia8@exemplo.com.br")
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header
    )
    # Sem IA configurada a plataforma avisa; não tenta adivinhar o conteúdo.
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ai_provider_not_configured"


async def test_analysis_requires_uploaded_file(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia9@exemplo.com.br")
    await configure_ai(client, admin)
    created = await client.post(
        "/api/v1/admin/notices", headers=admin.auth_header, json={"title": "Sem arquivo"}
    )
    response = await client.post(
        f"/api/v1/admin/notices/{created.json()['public_id']}/analyze",
        headers=admin.auth_header,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "notice_without_file"


async def test_review_and_confirm_flow(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia10@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.raiox@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())
    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    # Enquanto não confirmado, o candidato não vê o Raio-X.
    hidden = await client.get(
        f"/api/v1/catalog/notices/{notice_id}/radiography", headers=student.auth_header
    )
    assert hidden.status_code == 404

    facts = (
        await client.get(
            f"/api/v1/admin/notices/{notice_id}/radiography", headers=admin.auth_header
        )
    ).json()["facts"]
    inferred = next(fact for fact in facts if fact["evidence_level"] == EvidenceLevel.INFERRED)

    reviewed = await client.patch(
        f"/api/v1/admin/notices/{notice_id}/facts/{inferred['id']}",
        headers=admin.auth_header,
        json={"value": "Nota mínima de 50% em cada bloco"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["evidence_level"] == EvidenceLevel.CONFIRMED
    assert reviewed.json()["extracted_by"] == "HUMAN"

    confirmed = await client.post(
        f"/api/v1/admin/notices/{notice_id}/confirm", headers=admin.auth_header
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"

    visible = await client.get(
        f"/api/v1/catalog/notices/{notice_id}/radiography", headers=student.auth_header
    )
    assert visible.status_code == 200
    assert visible.json()["subjects_count"] == 3


async def test_human_review_survives_reanalysis(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia11@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())
    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    facts = (
        await client.get(
            f"/api/v1/admin/notices/{notice_id}/radiography", headers=admin.auth_header
        )
    ).json()["facts"]
    target = next(fact for fact in facts if fact["field_path"] == "exam.min_score_rule")
    await client.patch(
        f"/api/v1/admin/notices/{notice_id}/facts/{target['id']}",
        headers=admin.auth_header,
        json={"value": "Valor conferido por uma pessoa"},
    )

    await client.post(f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header)

    facts_after = {
        fact["field_path"]: fact
        for fact in (
            await client.get(
                f"/api/v1/admin/notices/{notice_id}/radiography", headers=admin.auth_header
            )
        ).json()["facts"]
    }
    kept = facts_after["exam.min_score_rule"]
    # A correção humana não é sobrescrita por uma nova rodada da IA.
    assert kept["evidence_level"] == EvidenceLevel.CONFIRMED
    assert kept["value"] == "Valor conferido por uma pessoa"


async def test_confirm_requires_finished_analysis(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia12@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/confirm", headers=admin.auth_header
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "notice_not_ready"


async def test_malformed_model_response_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = FakeProvider(raw_completion="isto não é json")

    def build(slug: str, credentials: ProviderCredentials) -> FakeProvider:
        return provider

    from app.services import ai_settings

    monkeypatch.setattr(ai_settings, "build_provider", build)

    admin = await create_admin(client, emails, email="edital.ia13@exemplo.com.br")
    await configure_ai(client, admin)
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/analyze", headers=admin.auth_header
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_ai_response"


async def test_student_cannot_analyze(
    client: AsyncClient, emails: CapturingDispatcher, fake_provider: FakeProvider
) -> None:
    admin = await create_admin(client, emails, email="edital.ia14@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.analise@exemplo.com.br")
    notice_id = await create_notice_with_pdf(client, admin, pdf=build_edital_pdf())

    response = await client.post(
        f"/api/v1/admin/notices/{notice_id}/analyze", headers=student.auth_header
    )
    assert response.status_code == 403
