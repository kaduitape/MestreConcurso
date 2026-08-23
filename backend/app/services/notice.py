"""Cadastro de editais e upload dos arquivos oficiais.

Fase 2 cuida do registro e do armazenamento seguro; a extração com IA acontece na
Fase 3 e reaproveita o ``checksum`` para nunca reprocessar o mesmo documento.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.audit import AuditAction
from app.models.notice import Notice, NoticeFile, NoticeFileStatus
from app.models.user import User
from app.repositories.catalog import CompetitionRepository
from app.repositories.notice import NoticeFileRepository, NoticeRepository
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.storage import LocalFileStorage, get_storage, validate_pdf

logger = get_logger(__name__)


class NoticeService:
    def __init__(self, session: AsyncSession, storage: LocalFileStorage | None = None) -> None:
        self.session = session
        self.notices = NoticeRepository(session)
        self.files = NoticeFileRepository(session)
        self.competitions = CompetitionRepository(session)
        self.audit = AuditService(session)
        self.storage = storage or get_storage()

    async def list_notices(
        self, *, limit: int, offset: int, status: str | None = None
    ) -> tuple[Sequence[Notice], int]:
        return await self.notices.search(limit=limit, offset=offset, status=status)

    async def get_notice(self, public_id: str) -> Notice:
        notice = await self.notices.get_by_public_id(public_id)
        if notice is None:
            raise NotFoundError("Edital não encontrado.")
        return notice

    async def list_for_competition(self, competition_public_id: str) -> Sequence[Notice]:
        competition = await self.competitions.get_by_public_id(competition_public_id)
        if competition is None:
            raise NotFoundError("Concurso não encontrado.")
        return await self.notices.list_for_competition(competition.id)

    async def create_notice(
        self,
        data: dict[str, Any],
        *,
        competition_public_id: str | None,
        actor: User,
        context: RequestContext,
    ) -> Notice:
        competition_id: int | None = None
        if competition_public_id:
            competition = await self.competitions.get_by_public_id(competition_public_id)
            if competition is None:
                raise NotFoundError("Concurso não encontrado.")
            competition_id = competition.id

        notice = Notice(competition_id=competition_id, created_by_user_id=actor.id, **data)
        self.session.add(notice)
        await self.session.flush()
        await self.audit.record(
            AuditAction.NOTICE_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice",
            resource_id=notice.public_id,
        )
        await self.session.commit()
        return await self.get_notice(notice.public_id)

    async def update_notice(
        self, public_id: str, data: dict[str, Any], *, actor: User, context: RequestContext
    ) -> Notice:
        notice = await self.get_notice(public_id)
        for field, value in data.items():
            setattr(notice, field, value)
        await self.audit.record(
            AuditAction.NOTICE_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice",
            resource_id=public_id,
            meta={"fields": sorted(data)},
        )
        await self.session.commit()
        return await self.get_notice(public_id)

    async def delete_notice(self, public_id: str, *, actor: User, context: RequestContext) -> None:
        notice = await self.get_notice(public_id)
        for file in notice.files:
            self.storage.delete(file.storage_key)
        await self.notices.delete(notice)
        await self.audit.record(
            AuditAction.NOTICE_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice",
            resource_id=public_id,
            meta={"deleted": True},
        )
        await self.session.commit()

    async def upload_file(
        self,
        notice_public_id: str,
        *,
        content: bytes,
        original_name: str,
        declared_mime: str | None,
        actor: User,
        context: RequestContext,
    ) -> NoticeFile:
        notice = await self.get_notice(notice_public_id)
        validate_pdf(content, declared_mime=declared_mime)

        stored = self.storage.save(content, prefix="notices", extension="pdf")
        duplicate = await self.files.get_by_checksum(notice.id, stored.checksum_sha256)
        if duplicate is not None:
            # Documento idêntico já enviado: descarta a cópia em vez de duplicar custo.
            self.storage.delete(stored.storage_key)
            raise ConflictError(
                "Este arquivo já foi enviado para o edital.",
                code="duplicate_notice_file",
                details={"file_public_id": duplicate.public_id},
            )

        file = NoticeFile(
            notice_id=notice.id,
            uploaded_by_user_id=actor.id,
            storage_key=stored.storage_key,
            original_name=original_name[:255],
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            checksum_sha256=stored.checksum_sha256,
            status=NoticeFileStatus.STORED,
        )
        self.session.add(file)
        await self.session.flush()

        await self.audit.record(
            AuditAction.NOTICE_FILE_UPLOADED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice_file",
            resource_id=file.public_id,
            meta={"size_bytes": stored.size_bytes, "notice": notice.public_id},
        )
        await self.session.commit()
        logger.info("notice.file_uploaded", notice=notice.public_id, size=stored.size_bytes)
        return file

    async def get_file(self, file_public_id: str) -> NoticeFile:
        file = await self.files.get_by_public_id(file_public_id)
        if file is None:
            raise NotFoundError("Arquivo não encontrado.")
        return file

    async def read_file(self, file_public_id: str) -> tuple[NoticeFile, bytes]:
        file = await self.get_file(file_public_id)
        return file, self.storage.read(file.storage_key)

    async def delete_file(
        self, file_public_id: str, *, actor: User, context: RequestContext
    ) -> None:
        file = await self.get_file(file_public_id)
        self.storage.delete(file.storage_key)
        await self.files.delete(file)
        await self.audit.record(
            AuditAction.NOTICE_FILE_DELETED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice_file",
            resource_id=file_public_id,
        )
        await self.session.commit()
