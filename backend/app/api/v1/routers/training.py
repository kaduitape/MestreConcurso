"""Estúdio de Treinamento: criação editorial e catálogo publicado."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import CurrentUser, DbSession, RequestCtx, require_permissions
from app.core.pagination import Page, PageParams, page_params
from app.domain import permissions as perms
from app.models.audit import AuditAction
from app.models.user import User
from app.schemas.training import (
    NarrationSceneRead,
    NarrationSegmentRead,
    TrainingCreate,
    TrainingMetricsRead,
    TrainingNarrationRead,
    TrainingProgressRead,
    TrainingProgressUpdate,
    TrainingRead,
    TrainingScriptUpdate,
    TrainingVoiceRead,
    TrainingVoiceUpdate,
)
from app.services.training import TrainingService
from app.services.training_narration import LessonNarration, TrainingNarrationService

training_router = APIRouter(prefix="/training", tags=["estúdio de treinamento"])
admin_router = APIRouter(prefix="/admin/training", tags=["admin · estúdio de treinamento"])
PageDep = Annotated[PageParams, Depends(page_params)]
TrainingReader = Annotated[User, Depends(require_permissions(perms.TRAINING_READ))]
TrainingWriter = Annotated[User, Depends(require_permissions(perms.TRAINING_WRITE))]


@training_router.get("", response_model=Page[TrainingRead], summary="Treinamentos publicados")
async def list_published(_: CurrentUser, db: DbSession, params: PageDep) -> Page[TrainingRead]:
    rows, total = await TrainingService(db).list(
        limit=params.page_size, offset=params.offset, published_only=True
    )
    return Page.create([TrainingRead.model_validate(item) for item in rows], total, params)


@training_router.get(
    "/{public_id}", response_model=TrainingRead, summary="Abrir treinamento publicado"
)
async def get_published(public_id: str, _: CurrentUser, db: DbSession) -> TrainingRead:
    return TrainingRead.model_validate(
        await TrainingService(db).get(public_id, published_only=True)
    )


@training_router.post(
    "/{public_id}/progress/start",
    response_model=TrainingProgressRead,
    summary="Iniciar ou retomar missão",
)
async def start_progress(public_id: str, user: CurrentUser, db: DbSession) -> TrainingProgressRead:
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return TrainingProgressRead.model_validate(await service.start(lesson, user))


@training_router.put(
    "/{public_id}/progress",
    response_model=TrainingProgressRead,
    summary="Salvar progresso da missão",
)
async def save_progress(
    public_id: str, payload: TrainingProgressUpdate, user: CurrentUser, db: DbSession
) -> TrainingProgressRead:
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return TrainingProgressRead.model_validate(
        await service.update_progress(lesson, user, current_scene=payload.current_scene)
    )


@training_router.post(
    "/{public_id}/complete",
    response_model=TrainingProgressRead,
    summary="Concluir missão e creditar XP",
)
async def complete_progress(
    public_id: str, user: CurrentUser, db: DbSession
) -> TrainingProgressRead:
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return TrainingProgressRead.model_validate(await service.complete(lesson, user))


@admin_router.get("", response_model=Page[TrainingRead], summary="Listar treinamentos do estúdio")
async def list_admin(_: TrainingReader, db: DbSession, params: PageDep) -> Page[TrainingRead]:
    rows, total = await TrainingService(db).list(limit=params.page_size, offset=params.offset)
    return Page.create([TrainingRead.model_validate(item) for item in rows], total, params)


@admin_router.post(
    "", response_model=TrainingRead, status_code=status.HTTP_201_CREATED, summary="Criar rascunho"
)
async def create_training(
    payload: TrainingCreate, actor: TrainingWriter, db: DbSession, ctx: RequestCtx
) -> TrainingRead:
    lesson = await TrainingService(db).create(actor, payload.model_dump(), ctx)
    return TrainingRead.model_validate(lesson)


# A rota de vozes vem antes de qualquer rota com ``{public_id}``: o FastAPI
# casa na ordem de declaração, e depois dela "voices" seria lido como um
# identificador de aula.
@admin_router.get("/voices", response_model=list[TrainingVoiceRead], summary="Vozes disponíveis")
async def list_voices(_: TrainingWriter, db: DbSession) -> list[TrainingVoiceRead]:
    """As vozes do provedor configurado. Lista vazia quando ele não fala."""
    return [
        TrainingVoiceRead(slug=slug, label=label)
        for slug, label in await TrainingNarrationService(db).available_voices()
    ]


@admin_router.get(
    "/{public_id}", response_model=TrainingRead, summary="Abrir treinamento no editor"
)
async def get_admin(public_id: str, _: TrainingReader, db: DbSession) -> TrainingRead:
    return TrainingRead.model_validate(await TrainingService(db).get(public_id))


@admin_router.get(
    "/{public_id}/metrics",
    response_model=TrainingMetricsRead,
    summary="Métricas reais do treinamento",
)
async def training_metrics(public_id: str, _: TrainingReader, db: DbSession) -> TrainingMetricsRead:
    service = TrainingService(db)
    return TrainingMetricsRead(**await service.metrics(await service.get(public_id)))


@admin_router.post(
    "/{public_id}/generate", response_model=TrainingRead, summary="Gerar roteiro com IA"
)
async def generate_training(
    public_id: str, actor: TrainingWriter, db: DbSession, ctx: RequestCtx
) -> TrainingRead:
    service = TrainingService(db)
    lesson = await service.generate(await service.get(public_id), actor, ctx)
    return TrainingRead.model_validate(lesson)


@admin_router.put(
    "/{public_id}/script", response_model=TrainingRead, summary="Salvar edição das cenas"
)
async def update_script(
    public_id: str,
    payload: TrainingScriptUpdate,
    actor: TrainingWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> TrainingRead:
    service = TrainingService(db)
    lesson = await service.update_script(
        await service.get(public_id),
        title=payload.title,
        script=payload.script,
        actor=actor,
        context=ctx,
    )
    return TrainingRead.model_validate(lesson)


@admin_router.post(
    "/{public_id}/publish", response_model=TrainingRead, summary="Publicar treinamento"
)
async def publish_training(
    public_id: str, actor: TrainingWriter, db: DbSession, ctx: RequestCtx
) -> TrainingRead:
    service = TrainingService(db)
    lesson = await service.publish(await service.get(public_id), actor, ctx)
    return TrainingRead.model_validate(lesson)


# --------------------------------------------------------------------------- #
# Narração
# --------------------------------------------------------------------------- #
def _narration_read(narration: LessonNarration) -> TrainingNarrationRead:
    return TrainingNarrationRead(
        voice=narration.voice,
        model_slug=narration.model_slug,
        scenes=[
            NarrationSceneRead(
                scene_id=scene.scene_id,
                segments=[
                    NarrationSegmentRead(
                        index=segment.index,
                        text=segment.text,
                        offset=segment.offset,
                        length=segment.length,
                        audio_url=segment.audio_url,
                        duration_hint_ms=segment.duration_hint_ms,
                    )
                    for segment in scene.segments
                ],
            )
            for scene in narration.scenes
        ],
        ready=narration.ready,
        total=narration.total,
        is_complete=narration.is_complete,
        unavailable_reason=narration.unavailable_reason,
    )


@training_router.get(
    "/{public_id}/narration",
    response_model=TrainingNarrationRead,
    summary="Narração da aula",
)
async def lesson_narration(public_id: str, _: CurrentUser, db: DbSession) -> TrainingNarrationRead:
    """O que existe de áudio para esta aula — e o motivo, quando não existe.

    Nunca falha por falta de configuração: sem provedor, a resposta diz por quê
    e o player cai para a voz do navegador.
    """
    service = TrainingService(db)
    lesson = await service.get(public_id, published_only=True)
    return _narration_read(await TrainingNarrationService(db).overview(lesson))


@training_router.get(
    "/narration/{public_id}/audio",
    response_class=Response,
    summary="Áudio de um trecho narrado",
)
async def narration_audio(public_id: str, db: DbSession) -> Response:
    """Serve o áudio.

    Sem autenticação pelo mesmo motivo da arte da batalha: um ``<audio>`` não
    carrega o token da aplicação. O identificador é aleatório e o conteúdo é o
    texto de uma aula publicada.
    """
    service = TrainingNarrationService(db)
    row = await service.get_audio(public_id)
    return Response(
        content=service.read_bytes(row),
        media_type=row.mime_type,
        headers={"Cache-Control": "public, max-age=604800"},
    )


@admin_router.get(
    "/{public_id}/narration",
    response_model=TrainingNarrationRead,
    summary="Estado da narração",
)
async def admin_narration(
    public_id: str, _: TrainingWriter, db: DbSession
) -> TrainingNarrationRead:
    service = TrainingService(db)
    lesson = await service.get(public_id)
    return _narration_read(await TrainingNarrationService(db).overview(lesson))


@admin_router.post(
    "/{public_id}/narration",
    response_model=TrainingNarrationRead,
    summary="Gerar a narração da aula",
)
async def generate_narration(
    public_id: str,
    actor: TrainingWriter,
    db: DbSession,
    ctx: RequestCtx,
    force: bool = False,
) -> TrainingNarrationRead:
    """Gera só os trechos que faltam — ou todos, com ``force``.

    Texto igual não gera nada: o áudio é identificado pelo conteúdo, pela
    direção de cena, pela voz e pelo modelo.
    """
    service = TrainingService(db)
    lesson = await service.get(public_id)
    narration = await TrainingNarrationService(db).generate(lesson, force=force)
    await service.audit.record(
        AuditAction.TRAINING_UPDATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="training_narration",
        resource_id=lesson.public_id,
        meta={"ready": narration.ready, "total": narration.total, "force": force},
    )
    await db.commit()
    return _narration_read(narration)


@admin_router.put(
    "/{public_id}/voice", response_model=TrainingRead, summary="Escolher a voz da aula"
)
async def set_lesson_voice(
    public_id: str,
    payload: TrainingVoiceUpdate,
    actor: TrainingWriter,
    db: DbSession,
    ctx: RequestCtx,
) -> TrainingRead:
    """Personagens diferentes merecem vozes diferentes.

    Trocar a voz **não apaga** o áudio já gerado: ele continua identificado pela
    voz antiga, e só a próxima geração produz os trechos na voz nova.
    """
    service = TrainingService(db)
    lesson = await service.get(public_id)
    lesson = await TrainingNarrationService(db).set_voice(lesson, payload.voice)
    await service.audit.record(
        AuditAction.TRAINING_UPDATED,
        actor=actor,
        actor_ip=ctx.ip_address,
        resource_type="training_lesson",
        resource_id=lesson.public_id,
        meta={"narration_voice": lesson.narration_voice},
    )
    await db.commit()
    # Releitura depois do commit: a instância anterior ficou com os atributos
    # expirados, e serializá-la tentaria I/O fora do contexto async.
    return TrainingRead.model_validate(await service.get(public_id))
