"""Mestre IA: conversas com citação conferida, vocabulário e vídeos verificados."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession, RequestCtx, rate_limit, require_permissions
from app.core.errors import AppError, NotFoundError
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams, page_params
from app.db.session import get_session_factory
from app.domain import permissions as perms
from app.models.audit import AuditAction
from app.models.catalog import Subject
from app.models.tutor import Message, VideoResource, VocabularyTerm
from app.models.user import User
from app.repositories.tutor import VideoResourceRepository
from app.repositories.user import UserRepository
from app.schemas.common import MessageResponse
from app.schemas.tutor import (
    AskInput,
    AskResultRead,
    ClaimRead,
    ConversationCreate,
    ConversationDetailRead,
    ConversationRead,
    MessageRead,
    SourceRead,
    VideoAdminRead,
    VideoCreate,
    VideoRead,
    VocabularyCreate,
    VocabularyRead,
)
from app.services.audit import AuditService
from app.services.tutor import TutorReply, TutorService, TutorStage
from app.services.vocabulary import VocabularyService

logger = get_logger(__name__)

router = APIRouter(tags=["mestre ia"])
tutor_router = APIRouter(prefix="/tutor", tags=["mestre ia"])
vocab_router = APIRouter(prefix="/vocabulary", tags=["vocabulário"])
admin_router = APIRouter(prefix="/admin/videos", tags=["admin · vídeos"])

VideoWriter = Annotated[User, Depends(require_permissions(perms.CATALOG_WRITE))]
PageDep = Annotated[PageParams, Depends(page_params)]


def _message_read(message: Message) -> MessageRead:
    return MessageRead(
        public_id=message.public_id,
        role=message.role,
        content=message.content,
        claims=[ClaimRead(**item) for item in (message.claims or [])],
        sources=[SourceRead(**item) for item in (message.sources or [])],
        computed_context=message.computed_context or {},
        is_refusal=message.is_refusal,
        refusal_reason=message.refusal_reason,
        grounding_ratio=(
            float(message.grounding_ratio) if message.grounding_ratio is not None else None
        ),
        model_slug=message.model_slug,
        input_tokens=message.input_tokens,
        output_tokens=message.output_tokens,
        created_at=message.created_at,
    )


def _vocabulary_read(entry: VocabularyTerm) -> VocabularyRead:
    return VocabularyRead(
        public_id=entry.public_id,
        term=entry.term,
        definition=entry.definition,
        subject_name=entry.subject.name if entry.subject else None,
        origin=entry.origin,
        source_quote=entry.source_quote,
        source_page=entry.source_page,
        source_document=entry.source_document,
        times_reviewed=entry.times_reviewed,
        created_at=entry.created_at,
    )


# --------------------------------------------------------------------------- #
# Conversas
# --------------------------------------------------------------------------- #
@tutor_router.post(
    "/conversations",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationRead,
    summary="Abrir conversa",
)
async def create_conversation(
    payload: ConversationCreate, user: CurrentUser, db: DbSession
) -> ConversationRead:
    conversation = await TutorService(db).create_conversation(
        user,
        title=payload.title,
        mode=payload.mode,
        notice_public_id=payload.notice_public_id,
        subject_public_id=payload.subject_public_id,
    )
    return ConversationRead.model_validate(conversation)


@tutor_router.get(
    "/conversations", response_model=list[ConversationRead], summary="Minhas conversas"
)
async def list_conversations(user: CurrentUser, db: DbSession) -> list[ConversationRead]:
    rows = await TutorService(db).list_conversations(user)
    return [ConversationRead.model_validate(item) for item in rows]


@tutor_router.get(
    "/conversations/{public_id}",
    response_model=ConversationDetailRead,
    summary="Abrir uma conversa",
)
async def get_conversation(
    public_id: str, user: CurrentUser, db: DbSession
) -> ConversationDetailRead:
    conversation = await TutorService(db).get_conversation(user, public_id)
    return ConversationDetailRead(
        public_id=conversation.public_id,
        title=conversation.title,
        mode=conversation.mode,
        message_count=conversation.message_count,
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
        messages=[_message_read(item) for item in conversation.messages],
    )


@tutor_router.delete(
    "/conversations/{public_id}", response_model=MessageResponse, summary="Arquivar conversa"
)
async def archive_conversation(public_id: str, user: CurrentUser, db: DbSession) -> MessageResponse:
    await TutorService(db).archive(user, public_id)
    return MessageResponse(message="Conversa arquivada.")


@tutor_router.post(
    "/conversations/{public_id}/ask",
    response_model=AskResultRead,
    summary="Perguntar ao Mestre",
    dependencies=[Depends(rate_limit("60/hour", scope="tutor:ask"))],
)
async def ask(public_id: str, payload: AskInput, user: CurrentUser, db: DbSession) -> AskResultRead:
    """Resposta completa, já com as citações conferidas."""
    reply = await TutorService(db).ask(user, public_id, payload.question)
    return AskResultRead(
        message=_message_read(reply.message),
        videos=[VideoRead.model_validate(item) for item in reply.videos],
        suggested_terms=reply.suggested_terms,
    )


@tutor_router.get(
    "/conversations/{public_id}/ask/stream",
    summary="Perguntar acompanhando cada etapa (SSE)",
    response_class=StreamingResponse,
    dependencies=[Depends(rate_limit("60/hour", scope="tutor:ask"))],
)
async def ask_stream(
    public_id: str,
    user: CurrentUser,
    question: Annotated[str, Query(min_length=1, max_length=2000)],
) -> StreamingResponse:
    """Transmite o caminho da resposta: buscar, calcular, redigir, conferir.

    A transmissão é por **etapa**, não token a token, e isso é deliberado: o texto
    só é liberado depois que as citações são conferidas. Transmitir tokens crus
    exibiria ao candidato afirmações que ainda podem ser descartadas por não terem
    origem — exatamente o que esta plataforma se recusa a fazer.
    """
    user_id = user.id

    async def event_source() -> AsyncIterator[str]:
        factory = get_session_factory()
        async with factory() as session:
            reloaded = await UserRepository(session).get(user_id)
            if reloaded is None:
                yield f"event: error\ndata: {json.dumps({'code': 'user_not_found'})}\n\n"
                return
            service = TutorService(session)
            try:
                async for event in service.ask_stream(reloaded, public_id, question):
                    if isinstance(event, TutorStage):
                        payload = {
                            "key": event.key,
                            "label": event.label,
                            "detail": event.detail,
                        }
                        yield f"event: stage\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    elif isinstance(event, TutorReply):
                        body = AskResultRead(
                            message=_message_read(event.message),
                            videos=[VideoRead.model_validate(item) for item in event.videos],
                            suggested_terms=event.suggested_terms,
                        )
                        yield (f"event: answer\ndata: {body.model_dump_json()}\n\n")
            except AppError as exc:
                payload = {"code": exc.code, "message": exc.message}
                yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# --------------------------------------------------------------------------- #
# Vocabulário
# --------------------------------------------------------------------------- #
@vocab_router.get("", response_model=Page[VocabularyRead], summary="Meu vocabulário")
async def list_vocabulary(
    user: CurrentUser,
    db: DbSession,
    params: PageDep,
    search: Annotated[str | None, Query(max_length=160)] = None,
) -> Page[VocabularyRead]:
    rows, total = await VocabularyService(db).list(
        user, limit=params.page_size, offset=params.offset, search=search
    )
    return Page.create([_vocabulary_read(item) for item in rows], total, params)


@vocab_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=VocabularyRead,
    summary="Guardar um termo",
)
async def add_term(payload: VocabularyCreate, user: CurrentUser, db: DbSession) -> VocabularyRead:
    entry = await VocabularyService(db).add(
        user,
        term=payload.term,
        definition=payload.definition,
        subject_public_id=payload.subject_public_id,
        message_public_id=payload.message_public_id,
    )
    return _vocabulary_read(entry)


@vocab_router.post(
    "/{public_id}/review", response_model=VocabularyRead, summary="Marcar como revisado"
)
async def review_term(public_id: str, user: CurrentUser, db: DbSession) -> VocabularyRead:
    return _vocabulary_read(await VocabularyService(db).review(user, public_id))


@vocab_router.delete("/{public_id}", response_model=MessageResponse, summary="Remover termo")
async def delete_term(public_id: str, user: CurrentUser, db: DbSession) -> MessageResponse:
    await VocabularyService(db).delete(user, public_id)
    return MessageResponse(message="Termo removido.")


# --------------------------------------------------------------------------- #
# Vídeos (curadoria humana)
# --------------------------------------------------------------------------- #
@admin_router.get("", response_model=Page[VideoAdminRead], summary="Listar vídeos")
async def list_videos(_: VideoWriter, db: DbSession, params: PageDep) -> Page[VideoAdminRead]:
    rows, total = await VideoResourceRepository(db).search(
        limit=params.page_size, offset=params.offset
    )
    return Page.create([_video_admin_read(item) for item in rows], total, params)


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=VideoAdminRead,
    summary="Cadastrar vídeo",
)
async def create_video(
    payload: VideoCreate, actor: VideoWriter, db: DbSession, ctx: RequestCtx
) -> VideoAdminRead:
    subject_id = None
    if payload.subject_public_id:
        subject_id = (
            await db.execute(
                select(Subject.id).where(Subject.public_id == payload.subject_public_id)
            )
        ).scalar_one_or_none()
        if subject_id is None:
            raise NotFoundError("Disciplina não encontrada.")

    video = VideoResource(
        title=payload.title,
        url=payload.url,
        provider=payload.provider,
        channel=payload.channel,
        duration_seconds=payload.duration_seconds,
        subject_id=int(subject_id) if subject_id else None,
        summary=payload.summary,
    )
    db.add(video)
    await db.flush()
    await AuditService(db).record(
        AuditAction.CATALOG_CREATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="video_resource",
        resource_id=video.public_id,
    )
    await db.commit()
    # Releitura: o objeto recém-inserido ainda não tem a disciplina carregada.
    stored = await VideoResourceRepository(db).get_by_public_id(video.public_id)
    assert stored is not None
    return _video_admin_read(stored)


@admin_router.post(
    "/{public_id}/verify", response_model=VideoAdminRead, summary="Marcar como conferido"
)
async def verify_video(
    public_id: str, actor: VideoWriter, db: DbSession, ctx: RequestCtx
) -> VideoAdminRead:
    """Só depois disso o Mestre pode sugerir o vídeo."""
    repository = VideoResourceRepository(db)
    video = await repository.get_by_public_id(public_id)
    if video is None:
        raise NotFoundError("Vídeo não encontrado.")
    video.verified_by_user_id = actor.id
    video.verified_at = datetime.now(UTC)
    await AuditService(db).record(
        AuditAction.CATALOG_UPDATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="video_resource",
        resource_id=public_id,
        meta={"verified": True},
    )
    await db.commit()
    return _video_admin_read(video)


@admin_router.delete("/{public_id}", response_model=MessageResponse, summary="Remover vídeo")
async def delete_video(
    public_id: str, actor: VideoWriter, db: DbSession, ctx: RequestCtx
) -> MessageResponse:
    repository = VideoResourceRepository(db)
    video = await repository.get_by_public_id(public_id)
    if video is None:
        raise NotFoundError("Vídeo não encontrado.")
    await repository.delete(video)
    await AuditService(db).record(
        AuditAction.CATALOG_DELETED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="video_resource",
        resource_id=public_id,
    )
    await db.commit()
    return MessageResponse(message="Vídeo removido.")


def _video_admin_read(video: VideoResource) -> VideoAdminRead:
    return VideoAdminRead(
        public_id=video.public_id,
        title=video.title,
        url=video.url,
        provider=video.provider,
        channel=video.channel,
        duration_seconds=video.duration_seconds,
        summary=video.summary,
        verified_at=video.verified_at,
        subject_name=video.subject.name if video.subject else None,
        is_active=video.is_active,
        is_verified=video.is_verified,
    )


router.include_router(tutor_router)
router.include_router(vocab_router)
router.include_router(admin_router)
