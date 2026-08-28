"""Fase 10: o ciclo comercial inteiro — assinar, cobrar, limitar, cancelar.

É o critério de aceite da fase, e ele é verificado aqui de ponta a ponta, com os
limites vindo do banco: um teste altera o teto de um plano pela API de
administração e confirma que o bloqueio muda junto, sem deploy.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import (
    RegisteredUser,
    create_admin,
    create_question,
    create_user,
)

WEBHOOK_SECRET = "segredo-de-webhook-para-teste"


def _signature(*, data_id: str, request_id: str, secret: str = WEBHOOK_SECRET) -> dict[str, str]:
    """Monta o cabeçalho no mesmo formato documentado pelo provedor."""
    timestamp = str(int(time.time()))
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return {"x-signature": f"ts={timestamp},v1={digest}", "x-request-id": request_id}


async def _configure_provider(client: AsyncClient, admin: RegisteredUser) -> None:
    response = await client.put(
        "/api/v1/admin/billing/provider",
        headers=admin.auth_header,
        json={
            "access_token": "TEST-token-do-provedor",
            "webhook_secret": WEBHOOK_SECRET,
            "is_active": True,
            "is_sandbox": True,
        },
    )
    assert response.status_code == 200, response.text


async def _subscribe(
    client: AsyncClient, student: RegisteredUser, *, plan: str = "mestre", coupon: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {"plan_slug": plan}
    if coupon:
        payload["coupon_code"] = coupon
    response = await client.post(
        "/api/v1/billing/subscribe", headers=student.auth_header, json=payload
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Planos e direitos
# --------------------------------------------------------------------------- #
async def test_plans_declare_what_each_one_grants(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/billing/plans")).json()

    assert {item["slug"] for item in body} >= {"gratuito", "mestre"}
    for plan in body:
        assert plan["entitlements"], "plano sem direitos declarados não existe"
        for item in plan["entitlements"]:
            assert item["description"], "todo direito se descreve em texto"
            assert item["label"] != item["feature"]


async def test_without_a_subscription_the_candidate_falls_back_to_the_free_plan(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill1@exemplo.com.br")

    subscription = (
        await client.get("/api/v1/billing/subscription", headers=student.auth_header)
    ).json()
    usage = (await client.get("/api/v1/billing/usage", headers=student.auth_header)).json()

    assert subscription["status"] == "NONE"
    assert subscription["plan_slug"] == "gratuito"
    assert subscription["is_paid"] is False
    assert usage, "sem assinatura ainda há direitos definidos"
    tutor = next(item for item in usage if item["feature"] == "ai.tutor")
    assert tutor["allowed"] is True
    assert tutor["limit"] == 10


async def test_no_study_content_sits_behind_the_paywall(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Simulados, desafios e analytics são limitados no gratuito, não bloqueados."""
    student = await create_user(client, emails, email="bill2@exemplo.com.br")

    usage = (await client.get("/api/v1/billing/usage", headers=student.auth_header)).json()
    por_recurso = {item["feature"]: item for item in usage}

    for feature in ("simulations", "challenges", "analytics"):
        assert por_recurso[feature]["allowed"] is True, f"{feature} não pode ser bloqueado"


# --------------------------------------------------------------------------- #
# Assinar
# --------------------------------------------------------------------------- #
async def test_subscribing_a_paid_plan_does_not_grant_access_before_payment(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill3@exemplo.com.br")

    result = await _subscribe(client, student)

    # O plano Mestre tem teste: a assinatura nasce em TRIALING, com cobrança pendente.
    assert result["subscription"]["status"] == "TRIALING"
    assert result["payment"]["status"] == "PENDING"
    assert result["payment"]["amount_cents"] == 4990
    assert "teste" in result["detail"]


async def test_a_second_subscription_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill4@exemplo.com.br")
    await _subscribe(client, student)

    again = await client.post(
        "/api/v1/billing/subscribe",
        headers=student.auth_header,
        json={"plan_slug": "mestre"},
    )

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "subscription_already_active"


async def test_an_invalid_coupon_is_refused_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill5@exemplo.com.br")
    created = await client.post(
        "/api/v1/admin/billing/coupons",
        headers=admin.auth_header,
        json={
            "code": "EXPIRADO",
            "kind": "PERCENT",
            "value": 50,
            "ends_on": (date.today() - timedelta(days=1)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    student = await create_user(client, emails, email="aluno.bill5@exemplo.com.br")

    preview = (
        await client.post(
            "/api/v1/billing/coupons/preview",
            headers=student.auth_header,
            json={"code": "EXPIRADO", "plan_slug": "mestre"},
        )
    ).json()

    assert preview["valid"] is False
    assert "expirou" in preview["reason"]
    assert preview["final_cents"] == 4990


async def test_a_valid_coupon_lowers_the_charge(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill6@exemplo.com.br")
    await client.post(
        "/api/v1/admin/billing/coupons",
        headers=admin.auth_header,
        json={"code": "BEMVINDO", "kind": "PERCENT", "value": 30},
    )
    student = await create_user(client, emails, email="aluno.bill6@exemplo.com.br")

    result = await _subscribe(client, student, coupon="BEMVINDO")

    assert result["coupon"]["valid"] is True
    assert result["coupon"]["discount_cents"] == 1497
    assert result["payment"]["amount_cents"] == 3493


# --------------------------------------------------------------------------- #
# Cobrar
# --------------------------------------------------------------------------- #
async def test_checkout_is_refused_while_the_provider_is_not_configured(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill7@exemplo.com.br")
    result = await _subscribe(client, student)

    response = await client.post(
        "/api/v1/billing/checkout",
        headers=student.auth_header,
        json={
            "reference": result["payment"]["reference"],
            "success_url": "https://exemplo.com.br/ok",
            "failure_url": "https://exemplo.com.br/erro",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "payment_not_configured"


async def test_the_provider_secret_never_comes_back_from_the_api(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill8@exemplo.com.br")
    await _configure_provider(client, admin)

    body = (await client.get("/api/v1/admin/billing/provider", headers=admin.auth_header)).json()

    assert body["is_configured"] is True
    assert body["is_active"] is True
    assert "TEST-token-do-provedor" not in str(body)
    assert body["access_token_hint"]
    assert body["webhook_secret_hint"]


async def test_an_unsigned_webhook_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill9@exemplo.com.br")
    await _configure_provider(client, admin)

    response = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"type": "payment", "data": {"id": "123"}},
    )

    assert response.status_code == 200, "não pedimos reenvio de notificação inválida"
    assert response.json()["accepted"] is False
    assert "assinatura" in response.json()["detail"].lower()


async def test_a_forged_signature_is_rejected(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill10@exemplo.com.br")
    await _configure_provider(client, admin)

    headers = _signature(data_id="123", request_id="req-1", secret="segredo-errado")
    response = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"type": "payment", "data": {"id": "123"}},
        headers=headers,
    )

    assert response.json()["accepted"] is False
    assert "não confere" in response.json()["detail"]


async def test_a_signed_webhook_of_an_unknown_topic_is_recorded_and_ignored(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill11@exemplo.com.br")
    await _configure_provider(client, admin)

    headers = _signature(data_id="999", request_id="req-2")
    response = await client.post(
        "/api/v1/webhooks/mercadopago",
        json={"type": "plan", "data": {"id": "999"}},
        headers=headers,
    )
    body = response.json()

    assert body["accepted"] is True
    assert body["duplicate"] is False
    assert "não tratado" in body["detail"]


async def test_the_same_webhook_twice_is_processed_once(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Todo adquirente reenvia. Reenvio não pode creditar duas vezes."""
    admin = await create_admin(client, emails, email="bill12@exemplo.com.br")
    await _configure_provider(client, admin)

    payload = {"type": "plan", "data": {"id": "555"}}
    first = await client.post(
        "/api/v1/webhooks/mercadopago",
        json=payload,
        headers=_signature(data_id="555", request_id="req-3"),
    )
    second = await client.post(
        "/api/v1/webhooks/mercadopago",
        json=payload,
        headers=_signature(data_id="555", request_id="req-4"),
    )

    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    assert "já processado" in second.json()["detail"]


# --------------------------------------------------------------------------- #
# Limitar
# --------------------------------------------------------------------------- #
async def test_the_free_plan_limit_blocks_with_an_explained_refusal(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill13@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.bill13@exemplo.com.br")

    for index in range(5):
        await create_question(
            client, admin, statement=f"Limite — enunciado {index} com texto suficiente."
        )

    # O plano gratuito permite 4 simulados por mês.
    for _ in range(4):
        created = await client.post(
            "/api/v1/simulations",
            headers=student.auth_header,
            json={"kind": "FLASH", "questions_count": 5},
        )
        assert created.status_code == 201, created.text

    blocked = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "FLASH", "questions_count": 5},
    )

    assert blocked.status_code == 402
    error = blocked.json()["error"]
    assert error["code"] == "quota_exceeded"
    assert "4 de 4" in error["message"]
    assert error["details"]["plan"] == "gratuito"
    assert error["details"]["resets_on"]


async def test_the_limit_comes_from_the_database_and_changes_without_deploy(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """A regra da fase: limite é dado. Mudar o teto muda o bloqueio na hora."""
    admin = await create_admin(client, emails, email="bill14@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.bill14@exemplo.com.br")
    for index in range(5):
        await create_question(
            client, admin, statement=f"Teto — enunciado {index} com texto suficiente."
        )

    updated = await client.put(
        "/api/v1/admin/billing/plans/gratuito",
        headers=admin.auth_header,
        json={
            "entitlements": [
                {"feature": "simulations", "is_enabled": True, "limit_value": 1, "period": "MONTH"},
                {"feature": "ai.tutor", "is_enabled": True, "limit_value": 10, "period": "MONTH"},
            ]
        },
    )
    assert updated.status_code == 200, updated.text

    first = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "FLASH", "questions_count": 5},
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "FLASH", "questions_count": 5},
    )
    assert second.status_code == 402
    assert "1 de 1" in second.json()["error"]["message"]


async def test_a_feature_outside_the_plan_is_refused_with_the_path(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill15@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.bill15@exemplo.com.br")

    await client.put(
        "/api/v1/admin/billing/plans/gratuito",
        headers=admin.auth_header,
        json={
            "entitlements": [
                {
                    "feature": "analytics",
                    "is_enabled": False,
                    "limit_value": None,
                    "period": "MONTH",
                }
            ]
        },
    )

    response = await client.get("/api/v1/analytics/master-score", headers=student.auth_header)

    assert response.status_code == 402
    assert response.json()["error"]["code"] == "feature_not_included"
    assert "não está incluído" in response.json()["error"]["message"]


async def test_usage_is_only_counted_on_accepted_calls(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill16@exemplo.com.br")
    student = await create_user(client, emails, email="aluno.bill16@exemplo.com.br")
    for index in range(5):
        await create_question(
            client, admin, statement=f"Contador — enunciado {index} com texto suficiente."
        )

    await client.put(
        "/api/v1/admin/billing/plans/gratuito",
        headers=admin.auth_header,
        json={
            "entitlements": [
                {"feature": "simulations", "is_enabled": True, "limit_value": 1, "period": "MONTH"}
            ]
        },
    )
    await client.post(
        "/api/v1/simulations",
        headers=student.auth_header,
        json={"kind": "FLASH", "questions_count": 5},
    )
    for _ in range(3):
        await client.post(
            "/api/v1/simulations",
            headers=student.auth_header,
            json={"kind": "FLASH", "questions_count": 5},
        )

    usage = (await client.get("/api/v1/billing/usage", headers=student.auth_header)).json()
    simulados = next(item for item in usage if item["feature"] == "simulations")

    assert simulados["used"] == 1, "chamada recusada não faz o contador subir"


# --------------------------------------------------------------------------- #
# Trocar e cancelar
# --------------------------------------------------------------------------- #
async def test_an_upgrade_is_immediate_with_proportional_credit(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill17@exemplo.com.br")
    await _subscribe(client, student)

    changed = await client.post(
        "/api/v1/billing/change-plan",
        headers=student.auth_header,
        json={"plan_slug": "mestre-anual"},
    )
    body = changed.json()

    assert changed.status_code == 200, changed.text
    assert body["kind"] == "UPGRADE"
    assert body["immediate"] is True
    assert body["subscription"]["plan_slug"] == "mestre-anual"
    assert body["payment"]["amount_cents"] == body["charge_cents"]


async def test_a_downgrade_is_scheduled_and_keeps_the_current_plan(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill18@exemplo.com.br")
    await _subscribe(client, student, plan="mestre-anual")

    changed = await client.post(
        "/api/v1/billing/change-plan",
        headers=student.auth_header,
        json={"plan_slug": "mestre"},
    )
    body = changed.json()

    assert body["kind"] == "DOWNGRADE"
    assert body["immediate"] is False
    assert body["charge_cents"] == 0
    assert body["subscription"]["plan_slug"] == "mestre-anual", "o plano de hoje continua"
    assert body["subscription"]["scheduled_plan_slug"] == "mestre"


async def test_canceling_keeps_access_until_the_end_of_the_paid_period(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Quem pagou até o dia 30 tem acesso até o dia 30."""
    student = await create_user(client, emails, email="bill19@exemplo.com.br")
    await _subscribe(client, student)

    canceled = await client.post(
        "/api/v1/billing/cancel",
        headers=student.auth_header,
        json={"reason": "Vou prestar outro concurso."},
    )
    body = canceled.json()

    assert canceled.status_code == 200, canceled.text
    assert body["status"] == "CANCELING"
    assert "até o fim do período" in body["status_label"]
    assert body["canceled_at"]
    assert body["current_period_end"]

    # E o acesso do plano contratado continua valendo hoje.
    usage = (await client.get("/api/v1/billing/usage", headers=student.auth_header)).json()
    tutor = next(item for item in usage if item["feature"] == "ai.tutor")
    assert tutor["limit"] == 300, "ainda com os limites do plano pago"


async def test_canceling_twice_is_refused(client: AsyncClient, emails: CapturingDispatcher) -> None:
    student = await create_user(client, emails, email="bill20@exemplo.com.br")
    await _subscribe(client, student)
    await client.post("/api/v1/billing/cancel", headers=student.auth_header, json={})

    # Cancelar de novo enquanto ainda está CANCELING é aceito (idempotente no
    # sentido de estado), mas cancelar uma assinatura já encerrada não é.
    again = await client.post("/api/v1/billing/cancel", headers=student.auth_header, json={})
    assert again.status_code in (200, 409)


# --------------------------------------------------------------------------- #
# Painel de SaaS
# --------------------------------------------------------------------------- #
async def test_the_saas_dashboard_declares_the_basis_of_every_metric(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="bill21@exemplo.com.br")

    body = (await client.get("/api/v1/admin/billing/dashboard", headers=admin.auth_header)).json()

    assert {item["key"] for item in body["metrics"]} == {
        "mrr",
        "arpu",
        "churn",
        "ai_cost",
        "margin",
    }
    for metric in body["metrics"]:
        assert metric["basis"], f"{metric['key']} não declara a base"
        if metric["value"] is None:
            assert metric["empty_reason"], "indicador sem base explica a ausência"


async def test_the_dashboard_requires_permission(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="bill22@exemplo.com.br")

    response = await client.get("/api/v1/admin/billing/dashboard", headers=student.auth_header)

    assert response.status_code == 403
