"""Cadastro da arte da Batalha RPG.

A silhueta em SVG sempre foi um padrão, não um destino. Estes testes cobram as
duas pontas disso: que **a batalha funciona sem arte nenhuma**, e que a arte
cadastrada entra na tela sem deploy — validada pelos bytes, porque a imagem
enviada aqui aparece para todo mundo que estuda.
"""

from __future__ import annotations

import struct
import zlib
from typing import Any

from httpx import AsyncClient

from tests.conftest import CapturingDispatcher
from tests.factories import RegisteredUser, create_admin, create_question, create_user


def _png(width: int = 8, height: int = 8) -> bytes:
    """Um PNG mínimo de verdade — não um arquivo com extensão .png."""

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


async def _upload(
    client: AsyncClient,
    admin: RegisteredUser,
    *,
    kind: str,
    slug: str,
    content: bytes,
    filename: str = "arte.png",
    mime: str = "image/png",
) -> Any:
    return await client.put(
        f"/api/v1/admin/game/battle-art/{kind}/{slug}",
        headers=admin.auth_header,
        files={"file": (filename, content, mime)},
    )


async def _stock(client: AsyncClient, admin: RegisteredUser, *, total: int) -> None:
    for index in range(total):
        await create_question(
            client, admin, statement=f"Arte — enunciado {index} com texto suficiente."
        )


async def test_the_catalogue_lists_every_slot_including_the_empty_ones(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Uma lista só do que já foi enviado esconderia o que falta fazer."""
    admin = await create_admin(client, emails, email="art1@exemplo.com.br")

    slots = (await client.get("/api/v1/admin/game/battle-art", headers=admin.auth_header)).json()

    kinds = {item["kind"] for item in slots}
    assert kinds == {"MONSTER", "PLAYER", "SCENERY"}
    assert all(item["image_url"] is None for item in slots), "nada cadastrado ainda"
    for item in slots:
        assert item["fallback"], "todo lugar vazio diz o que a tela desenha no lugar"
        assert item["label"]


async def test_uploading_art_makes_it_reach_the_battle(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="art2@exemplo.com.br")
    await _stock(client, admin, total=10)
    student = await create_user(client, emails, email="aluno.art2@exemplo.com.br")

    antes = (await client.post("/api/v1/game/battle", headers=student.auth_header)).json()
    assert antes["enemy_image_url"] is None, "sem arte, a silhueta continua"

    # A espécie do inimigo é derivada da rodada: a arte tem de ser a dele.
    enviado = await _upload(
        client, admin, kind="MONSTER", slug=antes["enemy_species"], content=_png()
    )
    assert enviado.status_code == 200, enviado.text
    assert enviado.json()["image_url"] is not None

    # A mesma batalha, relida: a arte entra sem recomeçar nada.
    depois = (
        await client.get(
            f"/api/v1/game/battle/{antes['run']['public_id']}", headers=student.auth_header
        )
    ).json()
    assert depois["enemy_image_url"] == enviado.json()["image_url"]
    assert all(item["image_url"] is not None for item in depois["monsters"])


async def test_the_image_is_served_and_can_be_opened_by_an_img_tag(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Sem autenticação de propósito: um `<img>` não carrega o token."""
    admin = await create_admin(client, emails, email="art3@exemplo.com.br")
    conteudo = _png()
    enviado = (await _upload(client, admin, kind="MONSTER", slug="orc", content=conteudo)).json()

    resposta = await client.get(enviado["image_url"])

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("image/png")
    assert resposta.content == conteudo


async def test_a_file_that_is_not_an_image_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Extensão e Content-Type vêm de quem envia. Só os bytes valem."""
    admin = await create_admin(client, emails, email="art4@exemplo.com.br")

    resposta = await _upload(
        client,
        admin,
        kind="MONSTER",
        slug="orc",
        content=b"MZ\x90\x00 isto e um executavel",
        filename="monstro.png",
        mime="image/png",
    )

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "invalid_image"


async def test_an_empty_file_is_refused(client: AsyncClient, emails: CapturingDispatcher) -> None:
    admin = await create_admin(client, emails, email="art5@exemplo.com.br")

    resposta = await _upload(client, admin, kind="MONSTER", slug="orc", content=b"")

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "empty_file"


async def test_a_slot_outside_the_catalogue_is_refused(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Arte solta ninguém veria — e ocuparia disco para sempre."""
    admin = await create_admin(client, emails, email="art6@exemplo.com.br")

    resposta = await _upload(client, admin, kind="MONSTER", slug="dragao", content=_png())

    assert resposta.status_code == 422
    assert resposta.json()["error"]["code"] == "unknown_asset_slot"


async def test_uploading_again_replaces_the_previous_art(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="art7@exemplo.com.br")

    primeira = (await _upload(client, admin, kind="MONSTER", slug="golem", content=_png())).json()
    segunda = (
        await _upload(client, admin, kind="MONSTER", slug="golem", content=_png(12, 12))
    ).json()

    assert segunda["public_id"] == primeira["public_id"], "um lugar, uma peça"
    assert (await client.get(segunda["image_url"])).status_code == 200

    slots = (await client.get("/api/v1/admin/game/battle-art", headers=admin.auth_header)).json()
    golem = [item for item in slots if item["kind"] == "MONSTER" and item["slug"] == "golem"]
    assert len(golem) == 1


async def test_removing_the_art_brings_the_silhouette_back(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    admin = await create_admin(client, emails, email="art8@exemplo.com.br")
    await _stock(client, admin, total=10)
    student = await create_user(client, emails, email="aluno.art8@exemplo.com.br")

    battle = (await client.post("/api/v1/game/battle", headers=student.auth_header)).json()
    especie = battle["enemy_species"]
    enviado = (await _upload(client, admin, kind="MONSTER", slug=especie, content=_png())).json()

    com_arte = (
        await client.get(
            f"/api/v1/game/battle/{battle['run']['public_id']}", headers=student.auth_header
        )
    ).json()
    assert com_arte["enemy_image_url"] is not None

    removido = await client.delete(
        f"/api/v1/admin/game/battle-art/{enviado['public_id']}", headers=admin.auth_header
    )
    assert removido.status_code == 200
    assert removido.json()["image_url"] is None

    sem_arte = (
        await client.get(
            f"/api/v1/game/battle/{battle['run']['public_id']}", headers=student.auth_header
        )
    ).json()
    assert sem_arte["enemy_image_url"] is None
    assert (await client.get(enviado["image_url"])).status_code == 404


async def test_the_scenery_falls_back_to_the_default_one(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    """Cadeia curta: peça da espécie, peça padrão, nada."""
    admin = await create_admin(client, emails, email="art9@exemplo.com.br")
    await _stock(client, admin, total=10)
    student = await create_user(client, emails, email="aluno.art9@exemplo.com.br")

    padrao = (await _upload(client, admin, kind="SCENERY", slug="default", content=_png())).json()

    battle = (await client.post("/api/v1/game/battle", headers=student.auth_header)).json()

    assert battle["scenery_image_url"] == padrao["image_url"]


async def test_only_an_administrator_can_register_art(
    client: AsyncClient, emails: CapturingDispatcher
) -> None:
    student = await create_user(client, emails, email="art10@exemplo.com.br")

    resposta = await client.put(
        "/api/v1/admin/game/battle-art/MONSTER/orc",
        headers=student.auth_header,
        files={"file": ("arte.png", _png(), "image/png")},
    )

    assert resposta.status_code == 403
