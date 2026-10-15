"""Narração do Estúdio de Treinamento, ponta a ponta.

Dois comportamentos são cobrados aqui com mais insistência que os outros:

*A aula funciona sem narração.* Sem provedor configurado nada quebra — a
resposta diz o motivo e o player cai para a voz do navegador.

*O token é pago uma vez.* Gerar de novo a mesma aula não chama o provedor.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin, create_user

API_KEY = "sk-proj-chave-de-teste-1234567890"

#: Um "MP3" de mentira. O serviço não interpreta o áudio, só o guarda e o serve.
FAKE_AUDIO = b"ID3\x04\x00\x00\x00\x00\x00\x00audio-de-teste"

SCRIPT: dict[str, Any] = {
    "objectives": ["Dominar a crase"],
    "scenes": [
        {
            "id": 1,
            "type": "intro",
            "narration": (
                "Saudações, aprendizes! Hoje vamos desvendar o mistério da crase. "
                "A crase é a fusão da preposição 'a' com o artigo definido 'a'."
            ),
            "dialogue": "",
            "screen_text": "Crase = 'a' + 'a'",
            "keywords": ["crase"],
            "emphasis": ["crase", "preposição"],
            "visual_elements": [],
            "duration": 12,
            "transition": "fade",
            "character": {"emotion": "confident", "animation": "talking", "gesture": "explain"},
        },
        {
            "id": 2,
            "type": "question",
            "narration": "Qual alternativa está correta sobre o uso da crase?",
            "dialogue": "",
            "screen_text": "Desafio",
            "keywords": [],
            "emphasis": [],
            "visual_elements": [],
            "duration": 10,
            "transition": "cut",
            "character": {"emotion": "curious", "animation": "idle", "gesture": "ask"},
            "options": ["Vou a escola", "Vou à escola"],
            "correct_option": 1,
            "feedback": "A crase ocorre com o artigo feminino.",
        },
    ],
}


class _SpeechCalls:
    """Conta quantas vezes o provedor foi chamado de verdade."""

    def __init__(self) -> None:
        self.count = 0
        self.payloads: list[dict[str, Any]] = []


def _mock_provider(monkeypatch: pytest.MonkeyPatch, calls: _SpeechCalls) -> None:
    """Intercepta o HTTP sem trocar o adaptador — ele roda de verdade."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/audio/speech"):
            import json

            calls.count += 1
            calls.payloads.append(json.loads(request.content))
            return httpx.Response(200, content=FAKE_AUDIO, headers={"content-type": "audio/mpeg"})
        return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini-tts"}]})

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient.__init__

    def patched(self: httpx.AsyncClient, *args: object, **kwargs: object) -> None:
        kwargs["transport"] = transport
        original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)


async def _lesson(client: AsyncClient, admin: RegisteredUser, *, publish: bool = True) -> str:
    """Cria uma aula com roteiro aprovado e, por padrão, publicada."""
    created = await client.post(
        "/api/v1/admin/training",
        headers=admin.auth_header,
        json={
            "subject": "Língua Portuguesa",
            "topic": "Crase",
            "character_name": "Mestre Arcanus",
            "level": "INTERMEDIARIO",
            "style": "AULA",
            "target_duration_minutes": 10,
            "research_before_generate": False,
        },
    )
    assert created.status_code == 201, created.text
    public_id = created.json()["public_id"]

    saved = await client.put(
        f"/api/v1/admin/training/{public_id}/script",
        headers=admin.auth_header,
        json={"title": "Domínio da Crase", "script": SCRIPT},
    )
    assert saved.status_code == 200, saved.text

    if publish:
        published = await client.post(
            f"/api/v1/admin/training/{public_id}/publish", headers=admin.auth_header
        )
        assert published.status_code == 200, published.text
    return public_id


async def _configure_voice(
    client: AsyncClient, admin: RegisteredUser, monkeypatch: pytest.MonkeyPatch
) -> _SpeechCalls:
    """Deixa a funcionalidade de narração pronta, com provedor ativo."""
    calls = _SpeechCalls()
    await client.post(
        "/api/v1/admin/ai/providers", headers=admin.auth_header, json={"slug": "openai"}
    )
    await client.put(
        "/api/v1/admin/ai/providers/openai/key",
        headers=admin.auth_header,
        json={"api_key": API_KEY},
    )
    _mock_provider(monkeypatch, calls)
    await client.post("/api/v1/admin/ai/providers/openai/models/sync", headers=admin.auth_header)
    await client.patch(
        "/api/v1/admin/ai/providers/openai",
        headers=admin.auth_header,
        json={"is_active": True},
    )
    bound = await client.put(
        "/api/v1/admin/ai/features/training.narration",
        headers=admin.auth_header,
        json={
            "provider_slug": "openai",
            "model_slug": "gpt-4o-mini-tts",
            "is_enabled": True,
        },
    )
    assert bound.status_code == 200, bound.text
    return calls


# --------------------------------------------------------------------------- #
# Sem provedor: a aula continua inteira
# --------------------------------------------------------------------------- #
async def test_without_a_provider_the_lesson_still_opens_and_says_why(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="narr1@exemplo.com.br")
    public_id = await _lesson(client, admin)
    student = await create_user(client, emails, email="aluno.narr1@exemplo.com.br")

    response = await client.get(
        f"/api/v1/training/{public_id}/narration", headers=student.auth_header
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scenes"] == []
    assert body["total"] == 0
    assert body["unavailable_reason"], "a tela precisa saber por que está muda"


async def test_generating_without_a_provider_is_refused_with_the_reason(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="narr2@exemplo.com.br")
    public_id = await _lesson(client, admin, publish=False)

    response = await client.post(
        f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "narration_not_configured"


async def test_the_voice_list_is_empty_without_a_provider(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Melhor nenhuma opção do que um menu de escolhas que não funcionam."""
    admin = await create_admin(client, emails, email="narr3@exemplo.com.br")

    response = await client.get("/api/v1/admin/training/voices", headers=admin.auth_header)

    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------------------- #
# Com provedor
# --------------------------------------------------------------------------- #
async def test_the_narration_speaks_the_approved_script_with_scene_direction(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="narr4@exemplo.com.br")
    calls = await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin)

    response = await client.post(
        f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["is_complete"] is True
    assert body["total"] == calls.count > 0
    assert body["model_slug"] == "gpt-4o-mini-tts"

    # O texto falado é o do roteiro aprovado — a IA não reescreve conteúdo.
    falado = " ".join(item["input"] for item in calls.payloads)
    assert "fusão da preposição" in falado

    # E a direção de cena vai junto, montada do próprio roteiro.
    direcao = calls.payloads[0]["instructions"]
    assert "Mestre Arcanus" in direcao
    assert "'crase'" in direcao


async def test_the_same_lesson_does_not_pay_twice(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="narr5@exemplo.com.br")
    calls = await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin)

    primeira = await client.post(
        f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header
    )
    assert primeira.status_code == 200
    gerados = calls.count
    assert gerados > 0

    segunda = await client.post(
        f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header
    )

    assert segunda.status_code == 200
    assert calls.count == gerados, "texto igual não chama o provedor de novo"
    assert segunda.json()["is_complete"] is True


async def test_rewriting_the_script_regenerates_only_what_changed(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="narr6@exemplo.com.br")
    calls = await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin, publish=False)

    await client.post(f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header)
    antes = calls.count

    alterado = {**SCRIPT, "scenes": [dict(SCRIPT["scenes"][0]), dict(SCRIPT["scenes"][1])]}
    alterado["scenes"][1]["narration"] = "Agora responda: quando a crase é obrigatória?"
    await client.put(
        f"/api/v1/admin/training/{public_id}/script",
        headers=admin.auth_header,
        json={"title": "Domínio da Crase", "script": alterado},
    )

    await client.post(f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header)

    # Só a cena reescrita custou: a outra continua valendo.
    assert calls.count == antes + 1


async def test_the_audio_is_served_and_plays_without_a_token(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="narr7@exemplo.com.br")
    await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin)
    student = await create_user(client, emails, email="aluno.narr7@exemplo.com.br")

    await client.post(f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header)
    narration = (
        await client.get(f"/api/v1/training/{public_id}/narration", headers=student.auth_header)
    ).json()

    url = narration["scenes"][0]["segments"][0]["audio_url"]
    audio = await client.get(url)

    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/")
    assert audio.content == FAKE_AUDIO


async def test_the_segments_point_at_the_scene_text(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """É o que permite acender a frase que está tocando, em vez de estimar."""
    admin = await create_admin(client, emails, email="narr8@exemplo.com.br")
    await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin)
    student = await create_user(client, emails, email="aluno.narr8@exemplo.com.br")

    await client.post(f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header)
    narration = (
        await client.get(f"/api/v1/training/{public_id}/narration", headers=student.auth_header)
    ).json()

    cena = next(item for item in narration["scenes"] if item["scene_id"] == 1)
    texto = SCRIPT["scenes"][0]["narration"]
    for segmento in cena["segments"]:
        recorte = texto[segmento["offset"] : segmento["offset"] + segmento["length"]]
        assert recorte == segmento["text"]


async def test_the_lesson_can_have_its_own_voice(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="narr9@exemplo.com.br")
    calls = await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin, publish=False)

    voices = (await client.get("/api/v1/admin/training/voices", headers=admin.auth_header)).json()
    assert voices, "o provedor configurado oferece vozes"

    escolhida = await client.put(
        f"/api/v1/admin/training/{public_id}/voice",
        headers=admin.auth_header,
        json={"voice": "fable"},
    )
    assert escolhida.status_code == 200, escolhida.text
    assert escolhida.json()["narration_voice"] == "fable"

    await client.post(f"/api/v1/admin/training/{public_id}/narration", headers=admin.auth_header)
    assert all(item["voice"] == "fable" for item in calls.payloads)


async def test_an_unknown_voice_is_refused(
    client: AsyncClient, emails: CapturingDispatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = await create_admin(client, emails, email="narr10@exemplo.com.br")
    await _configure_voice(client, admin, monkeypatch)
    public_id = await _lesson(client, admin, publish=False)

    response = await client.put(
        f"/api/v1/admin/training/{public_id}/voice",
        headers=admin.auth_header,
        json={"voice": "voz-que-nao-existe"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unknown_voice"


async def test_an_unknown_audio_is_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/training/narration/nao-existe/audio")
    assert response.status_code == 404
