"""Cadastro da arte da Batalha RPG.

A silhueta em SVG foi sempre um padrão, não um destino: ela garante que a
batalha funcione no dia um, sem download e sem depender de ninguém desenhar
nada. Este serviço é o caminho para a arte de verdade entrar — e sair, se não
prestar — sem deploy.

Duas disciplinas, herdadas do upload de editais: **o conteúdo do arquivo é o que
vale** (nome e ``Content-Type`` vêm de quem envia) e o nome no disco é gerado
aqui. Uma imagem cadastrada aparece na tela de todo mundo que estuda; um arquivo
que não é imagem não pode chegar lá.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.game.battle_art import (
    CATALOGUE_BY_KEY,
    AssetSlot,
    catalogue,
    is_known,
    resolve,
)
from app.models.game import BattleAsset
from app.models.user import User
from app.services.storage import detect_image, get_storage

logger = get_logger(__name__)

#: Prefixo no armazenamento. Fora da árvore servida diretamente, como os editais.
STORAGE_PREFIX = "battle-art"


class BattleArtService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.storage = get_storage()

    async def all_assets(self) -> list[BattleAsset]:
        return list(
            (await self.session.execute(select(BattleAsset).order_by(BattleAsset.kind)))
            .scalars()
            .all()
        )

    async def url_map(self) -> dict[tuple[str, str], str]:
        """As URLs por chave, para a batalha montar a tela numa consulta só."""
        return {
            (item.kind, item.slug): self.public_url(item.public_id)
            for item in await self.all_assets()
        }

    @staticmethod
    def public_url(public_id: str) -> str:
        """A rota pública da imagem.

        Pública de propósito: arte de monstro não é dado de ninguém, e um
        ``<img>`` não carrega o token de autenticação da aplicação.
        """
        return f"/api/v1/game/battle/art/{public_id}"

    def resolve_url(self, assets: dict[tuple[str, str], str], kind: str, slug: str) -> str | None:
        return resolve(assets, kind, slug)

    async def slots(self) -> list[tuple[AssetSlot, BattleAsset | None]]:
        """O catálogo inteiro, com a peça cadastrada de cada lugar — ou nada.

        A tela do administrador mostra **todos** os lugares, inclusive os vazios,
        com o que aparece enquanto estiverem vazios. Uma lista só do que já foi
        enviado esconderia exatamente o que falta fazer.
        """
        stored = {(item.kind, item.slug): item for item in await self.all_assets()}
        return [(slot, stored.get((slot.kind, slot.slug))) for slot in catalogue()]

    async def get(self, public_id: str) -> BattleAsset:
        asset = (
            await self.session.execute(
                select(BattleAsset).where(BattleAsset.public_id == public_id)
            )
        ).scalar_one_or_none()
        if asset is None:
            raise NotFoundError("Arte não encontrada.")
        return asset

    async def upload(
        self,
        actor: User,
        *,
        kind: str,
        slug: str,
        content: bytes,
        declared_mime: str | None,
        filename: str | None,
    ) -> BattleAsset:
        """Grava a arte de um lugar do catálogo, substituindo a anterior."""
        if not is_known(kind, slug):
            raise ValidationError(
                "Este lugar de arte não existe na batalha.",
                code="unknown_asset_slot",
                details={"kind": kind, "slug": slug},
            )

        mime, extension = detect_image(content, declared_mime=declared_mime)
        stored_file = self.storage.save(
            content, prefix=STORAGE_PREFIX, extension=extension, mime_type=mime
        )

        existing = (
            await self.session.execute(
                select(BattleAsset).where(BattleAsset.kind == kind, BattleAsset.slug == slug)
            )
        ).scalar_one_or_none()

        previous_key = existing.storage_key if existing else None
        asset = existing or BattleAsset(kind=kind, slug=slug)
        asset.label = CATALOGUE_BY_KEY[(kind, slug)].label
        asset.storage_key = stored_file.storage_key
        asset.mime_type = stored_file.mime_type
        asset.size_bytes = stored_file.size_bytes
        asset.checksum_sha256 = stored_file.checksum_sha256
        # O nome enviado é guardado só para quem administra reconhecer o arquivo:
        # ele nunca vira caminho no disco.
        asset.original_filename = (filename or "")[:255] or None
        asset.uploaded_by_user_id = actor.id
        if existing is None:
            self.session.add(asset)
        await self.session.commit()

        # A substituída sai do disco depois do commit: falha no meio deixaria o
        # banco apontando para um arquivo que não existe mais.
        if previous_key and previous_key != stored_file.storage_key:
            self.storage.delete(previous_key)

        logger.info(
            "battle_art.uploaded",
            actor=actor.public_id,
            kind=kind,
            slug=slug,
            size=stored_file.size_bytes,
        )
        return asset

    async def remove(self, actor: User, public_id: str) -> None:
        """Tira a arte do ar. A silhueta volta a aparecer na questão seguinte."""
        asset = await self.get(public_id)
        storage_key = asset.storage_key
        kind, slug = asset.kind, asset.slug
        await self.session.delete(asset)
        await self.session.commit()
        self.storage.delete(storage_key)
        logger.info("battle_art.removed", actor=actor.public_id, kind=kind, slug=slug)

    async def read_bytes(self, asset: BattleAsset) -> bytes:
        return self.storage.read(asset.storage_key)
