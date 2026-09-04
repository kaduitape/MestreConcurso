"""Orquestração do roteiro estruturado do Estúdio de Treinamento."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage, CompletionRequest
from app.core.errors import NotFoundError, ValidationError
from app.domain.game import GameEvent, GameEventKind
from app.models.ai import AIFeature
from app.models.audit import AuditAction
from app.models.catalog import Competition
from app.models.training import (
    TrainingLesson,
    TrainingProgress,
    TrainingProgressStatus,
    TrainingStatus,
)
from app.models.user import User
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.game_engine import GameEngine

PROMPT_VERSION = "v1"


def _script_prompt(lesson: TrainingLesson) -> list[ChatMessage]:
    context = {
        "subject": lesson.subject,
        "topic": lesson.topic,
        "character": lesson.character_name,
        "level": lesson.level,
        "style": lesson.style,
        "target_duration_minutes": lesson.target_duration_minutes,
        "board": lesson.board_name,
        "additional_instructions": lesson.additional_prompt,
        "research_requested": lesson.research_before_generate,
    }
    return [
        ChatMessage(
            role="system",
            content=(
                "Você cria roteiros pedagógicos rigorosos para concursos públicos "
                "em português do Brasil. "
                "A fantasia é recurso de memorização, nunca substitui precisão acadêmica. "
                "Retorne somente JSON válido, sem markdown, com title, objectives e scenes. "
                "Cada scene deve conter id, type, narration, dialogue, screen_text, "
                "keywords, emphasis, "
                "visual_elements, duration, transition e character (emotion, animation, gesture). "
                "Inclua ao menos uma cena de explicação, um exemplo, uma pegadinha "
                "quando aplicável e "
                "uma pergunta de múltipla escolha com type exatamente igual a "
                "'question', options, correct_option e feedback. "
                "keywords deve conter conceitos importantes exatamente como aparecem no diálogo."
            ),
        ),
        ChatMessage(role="user", content=json.dumps(context, ensure_ascii=False)),
    ]


def _validate_script(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("scenes"), list):
        raise ValidationError(
            "A IA não devolveu um roteiro em cenas válido.", code="training_invalid_script"
        )
    if not value["scenes"]:
        raise ValidationError("O roteiro gerado não possui cenas.", code="training_empty_script")
    for index, scene in enumerate(value["scenes"], start=1):
        if not isinstance(scene, dict):
            raise ValidationError("Uma cena do roteiro é inválida.", code="training_invalid_scene")
        scene.setdefault("id", index)
        scene.setdefault("type", "explanation")
        scene.setdefault("narration", scene.get("dialogue", ""))
        scene.setdefault("dialogue", scene.get("narration", ""))
        scene.setdefault("screen_text", "")
        scene.setdefault("keywords", [])
        scene.setdefault("emphasis", [])
        scene.setdefault("visual_elements", [])
        scene.setdefault("duration", 12)
        scene.setdefault("transition", "fade")
        scene.setdefault(
            "character", {"emotion": "confident", "animation": "talking", "gesture": "explain"}
        )
    value.setdefault("objectives", [])
    return value


class TrainingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def get(self, public_id: str, *, published_only: bool = False) -> TrainingLesson:
        stmt = select(TrainingLesson).where(TrainingLesson.public_id == public_id)
        if published_only:
            stmt = stmt.where(TrainingLesson.status == TrainingStatus.PUBLISHED)
        lesson = (await self.session.execute(stmt)).scalar_one_or_none()
        if lesson is None:
            raise NotFoundError("Treinamento não encontrado.")
        return lesson

    async def list(
        self, *, limit: int, offset: int, published_only: bool = False
    ) -> tuple[list[TrainingLesson], int]:
        stmt = select(TrainingLesson)
        if published_only:
            stmt = stmt.where(TrainingLesson.status == TrainingStatus.PUBLISHED)
        total = int(
            (
                await self.session.execute(select(func.count()).select_from(stmt.subquery()))
            ).scalar_one()
        )
        rows = (
            (
                await self.session.execute(
                    stmt.order_by(TrainingLesson.created_at.desc()).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def progress_for(self, lesson: TrainingLesson, user: User) -> TrainingProgress | None:
        return (
            await self.session.execute(
                select(TrainingProgress).where(
                    TrainingProgress.lesson_id == lesson.id, TrainingProgress.user_id == user.id
                )
            )
        ).scalar_one_or_none()

    async def start(self, lesson: TrainingLesson, user: User) -> TrainingProgress:
        progress = await self.progress_for(lesson, user)
        if progress is not None:
            return progress
        now = datetime.now(UTC)
        progress = TrainingProgress(
            user_id=user.id, lesson_id=lesson.id, started_at=now, last_seen_at=now
        )
        self.session.add(progress)
        await self.session.commit()
        return progress

    @staticmethod
    def _focus_seconds(progress: TrainingProgress, now: datetime) -> int:
        """Conta apenas um intervalo curto entre heartbeats ativos.

        O cliente não envia minutos: ele só confirma que o player segue ativo. O
        teto impede que deixar a aba aberta durante horas seja tratado como foco.
        """
        elapsed = max(0, int((now - progress.last_seen_at).total_seconds()))
        return progress.focus_seconds + min(elapsed, 30)

    async def update_progress(
        self, lesson: TrainingLesson, user: User, *, current_scene: int
    ) -> TrainingProgress:
        progress = await self.start(lesson, user)
        if progress.status == TrainingProgressStatus.COMPLETED:
            return progress
        now = datetime.now(UTC)
        scene_count = len(lesson.script.get("scenes", []))
        max_scene = max(scene_count - 1, 0)
        progress.current_scene = max(progress.current_scene, min(current_scene, max_scene))
        progress.completed_scenes = max(progress.completed_scenes, progress.current_scene + 1)
        progress.focus_seconds = self._focus_seconds(progress, now)
        progress.last_seen_at = now
        await self.session.commit()
        return progress

    async def complete(self, lesson: TrainingLesson, user: User) -> TrainingProgress:
        progress = await self.start(lesson, user)
        if progress.status == TrainingProgressStatus.COMPLETED:
            return progress
        scene_count = len(lesson.script.get("scenes", []))
        if scene_count == 0 or progress.current_scene < scene_count - 1:
            raise ValidationError(
                "Percorra todas as cenas antes de concluir a missão.", code="training_not_finished"
            )

        now = datetime.now(UTC)
        progress.focus_seconds = self._focus_seconds(progress, now)
        progress.last_seen_at = now
        if progress.focus_seconds < 5 * 60:
            await self.session.commit()
            raise ValidationError(
                "A missão precisa de pelo menos 5 minutos de foco para ser concluída.",
                code="training_focus_too_short",
                details={"remaining_seconds": 5 * 60 - progress.focus_seconds},
            )
        progress.status = TrainingProgressStatus.COMPLETED
        progress.completed_scenes = scene_count
        progress.completed_at = now
        await self.session.commit()

        award = await GameEngine(self.session).award(
            user,
            GameEvent(
                kind=GameEventKind.TRAINING_FINISHED,
                reference=f"training:{lesson.public_id}",
                metrics={"focus_minutes": progress.focus_seconds / 60},
            ),
        )
        progress.xp_awarded = award.award.amount if award.recorded else 0
        await self.session.commit()
        return progress

    async def metrics(self, lesson: TrainingLesson) -> dict[str, int | float]:
        row = (
            await self.session.execute(
                select(
                    func.count(TrainingProgress.id),
                    func.coalesce(
                        func.sum(
                            case(
                                (TrainingProgress.status == TrainingProgressStatus.COMPLETED, 1),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(TrainingProgress.focus_seconds), 0),
                ).where(TrainingProgress.lesson_id == lesson.id)
            )
        ).one()
        starts, completions, focus_seconds = (int(row[0]), int(row[1]), int(row[2]))
        return {
            "starts": starts,
            "completions": completions,
            "completion_rate": round(completions / starts, 4) if starts else 0,
            "total_focus_seconds": focus_seconds,
            "average_focus_seconds": round(focus_seconds / starts) if starts else 0,
        }

    async def create(
        self, actor: User, data: dict[str, Any], context: RequestContext
    ) -> TrainingLesson:
        competition_id: int | None = None
        competition_public_id = data.pop("competition_public_id", None)
        if competition_public_id:
            competition = (
                await self.session.execute(
                    select(Competition).where(Competition.public_id == competition_public_id)
                )
            ).scalar_one_or_none()
            if competition is None:
                raise NotFoundError("Concurso não encontrado.")
            competition_id = competition.id
        lesson = TrainingLesson(
            created_by_user_id=actor.id,
            competition_id=competition_id,
            title=f"{data['topic']} · {data['subject']}",
            **data,
        )
        self.session.add(lesson)
        await self.session.flush()
        await self.audit.record(
            AuditAction.TRAINING_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="training_lesson",
            resource_id=lesson.public_id,
        )
        await self.session.commit()
        return await self.get(lesson.public_id)

    async def generate(
        self, lesson: TrainingLesson, actor: User, context: RequestContext
    ) -> TrainingLesson:
        lesson.status = TrainingStatus.GENERATING
        lesson.generation_error = None
        await self.session.commit()
        resolved = await AISettingsService(self.session).resolve_feature(AIFeature.TRAINING_SCRIPT)
        messages = _script_prompt(lesson)
        cache_payload = {"messages": [message.content for message in messages]}
        cache_key = fingerprint(
            feature=AIFeature.TRAINING_SCRIPT,
            model_slug=resolved.model_slug,
            prompt_version=PROMPT_VERSION,
            payload=cache_payload,
        )
        cache = AICacheService(self.session)
        cached = await cache.get(cache_key)
        try:
            if cached:
                script = _validate_script(cached.payload["script"])
                input_tokens = cached.input_tokens
                output_tokens = cached.output_tokens
                latency_ms = 0
            else:
                completion = await resolved.provider.complete(
                    CompletionRequest(
                        model=resolved.model_slug,
                        messages=messages,
                        temperature=float(resolved.binding.temperature),
                        max_output_tokens=resolved.binding.max_output_tokens or 6000,
                        json_response=True,
                    )
                )
                script = _validate_script(json.loads(completion.content))
                input_tokens = completion.usage.input_tokens
                output_tokens = completion.usage.output_tokens
                latency_ms = completion.latency_ms
                await cache.store(
                    cache_key=cache_key,
                    feature=AIFeature.TRAINING_SCRIPT,
                    provider_slug=resolved.provider_slug,
                    model_slug=resolved.model_slug,
                    payload={"script": script},
                    prompt_version=PROMPT_VERSION,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    ttl_hours=resolved.binding.cache_ttl_hours,
                )
        except Exception as exc:
            lesson.status = TrainingStatus.DRAFT
            lesson.generation_error = str(exc)[:1000]
            await self.session.commit()
            raise

        lesson.title = str(script.get("title") or lesson.title)[:200]
        lesson.script = script
        lesson.status = TrainingStatus.READY
        lesson.model_slug = resolved.model_slug
        lesson.input_tokens = input_tokens
        lesson.output_tokens = output_tokens
        lesson.latency_ms = latency_ms
        lesson.generated_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.TRAINING_GENERATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="training_lesson",
            resource_id=lesson.public_id,
            meta={"scenes": len(script["scenes"]), "model": resolved.model_slug},
        )
        await self.session.commit()
        return await self.get(lesson.public_id)

    async def update_script(
        self,
        lesson: TrainingLesson,
        *,
        title: str,
        script: dict[str, Any],
        actor: User,
        context: RequestContext,
    ) -> TrainingLesson:
        lesson.title = title
        lesson.script = _validate_script(script)
        lesson.status = TrainingStatus.READY
        await self.audit.record(
            AuditAction.TRAINING_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="training_lesson",
            resource_id=lesson.public_id,
        )
        await self.session.commit()
        return await self.get(lesson.public_id)

    async def publish(
        self, lesson: TrainingLesson, actor: User, context: RequestContext
    ) -> TrainingLesson:
        if not lesson.script.get("scenes"):
            raise ValidationError("Gere e revise ao menos uma cena antes de publicar.")
        lesson.status = TrainingStatus.PUBLISHED
        lesson.published_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.TRAINING_PUBLISHED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="training_lesson",
            resource_id=lesson.public_id,
        )
        await self.session.commit()
        return await self.get(lesson.public_id)
