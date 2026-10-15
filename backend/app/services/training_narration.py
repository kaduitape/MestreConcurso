"""Narração das aulas: do roteiro aprovado ao áudio que o aluno ouve.

Três decisões sustentam o serviço.

**O token é pago uma vez.** Cada trecho é identificado por um checksum de
texto + direção + voz + modelo. Reabrir a aula não gera nada; reescrever uma
vírgula gera só o trecho que mudou. É a mesma regra do cache de IA do resto da
plataforma.

**A narração não bloqueia a aula.** Se não houver provedor configurado, se o
modelo escolhido não falar, ou se a geração falhar, a aula continua a mesma — o
player cai para a voz do navegador e **diz qual voz está usando**. Uma tela que
só funciona depois que alguém configura uma chave seria uma tela quebrada.

**Nada do conteúdo é inventado.** O que a IA recebe é o texto que já estava no
roteiro aprovado por uma pessoa, mais uma direção de cena montada a partir dos
campos do próprio roteiro. Ela escolhe entonação, não informação.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ProviderNotConfiguredError, SpeechNotSupportedError, SpeechRequest
from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.training.narration import NarrationSegment, SceneNarration, narrate_script
from app.models.ai import AIFeature
from app.models.training import TrainingLesson, TrainingNarration
from app.services.ai_settings import AISettingsService
from app.services.storage import get_storage

logger = get_logger(__name__)

#: Prefixo no armazenamento, fora da árvore servida diretamente.
STORAGE_PREFIX = "training-narration"

#: Voz usada quando o administrador ainda não escolheu uma. Grave e narrativa,
#: que é o registro que o Estúdio pede — e trocável no painel.
DEFAULT_VOICE = "onyx"


@dataclass(frozen=True, slots=True)
class NarratedSegment:
    """Um trecho pronto para a tela: o texto, onde ele está e o áudio dele."""

    index: int
    text: str
    offset: int
    length: int
    audio_url: str | None
    duration_hint_ms: int


@dataclass(frozen=True, slots=True)
class NarratedScene:
    scene_id: int
    segments: list[NarratedSegment]


@dataclass(frozen=True, slots=True)
class LessonNarration:
    """O que a aula tem de narração — inclusive quando não tem nenhuma."""

    voice: str
    model_slug: str | None
    scenes: list[NarratedScene]
    #: Quantos trechos já existem em áudio, de quantos o roteiro pede.
    ready: int
    total: int
    #: Por que ainda não há áudio, quando for o caso. A tela mostra isto.
    unavailable_reason: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.total > 0 and self.ready == self.total


class TrainingNarrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.storage = get_storage()
        self.settings = AISettingsService(session)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    @staticmethod
    def audio_url(public_id: str) -> str:
        """Rota do áudio. Pública como a arte: um ``<audio>`` não leva token."""
        return f"/api/v1/training/narration/{public_id}/audio"

    @staticmethod
    def voice_for(lesson: TrainingLesson, binding_options: dict[str, object]) -> str:
        """A voz da aula: a dela, a padrão da funcionalidade, ou a de fábrica."""
        return str(lesson.narration_voice or binding_options.get("voice") or DEFAULT_VOICE)

    async def _voice_and_model(self, lesson: TrainingLesson) -> tuple[str, str | None, str | None]:
        """A voz e o modelo configurados — ou o motivo de não haver nenhum."""
        try:
            resolved = await self.settings.resolve_feature(AIFeature.TRAINING_NARRATION)
        except ProviderNotConfiguredError as exc:
            return DEFAULT_VOICE, None, str(exc.message)

        options = resolved.binding.options if isinstance(resolved.binding.options, dict) else {}
        return self.voice_for(lesson, options), resolved.model_slug, None

    async def _stored(self, lesson: TrainingLesson) -> dict[str, TrainingNarration]:
        rows = (
            await self.session.execute(
                select(TrainingNarration).where(TrainingNarration.lesson_id == lesson.id)
            )
        ).scalars()
        return {item.checksum: item for item in rows}

    def _plan(self, lesson: TrainingLesson, *, voice: str, model: str) -> list[SceneNarration]:
        script = lesson.script if isinstance(lesson.script, dict) else {}
        return narrate_script(script, character=lesson.character_name, voice=voice, model=model)

    async def overview(self, lesson: TrainingLesson) -> LessonNarration:
        """O estado da narração da aula, sem gerar nada."""
        voice, model, reason = await self._voice_and_model(lesson)
        if model is None:
            return LessonNarration(
                voice=voice,
                model_slug=None,
                scenes=[],
                ready=0,
                total=0,
                unavailable_reason=reason,
            )

        stored = await self._stored(lesson)
        scenes: list[NarratedScene] = []
        ready = 0
        total = 0

        for scene in self._plan(lesson, voice=voice, model=model):
            segments: list[NarratedSegment] = []
            for segment in scene.segments:
                total += 1
                row = stored.get(segment.checksum)
                if row is not None:
                    ready += 1
                segments.append(
                    NarratedSegment(
                        index=segment.index,
                        text=segment.text,
                        offset=segment.offset,
                        length=segment.length,
                        audio_url=self.audio_url(row.public_id) if row else None,
                        duration_hint_ms=_duration_hint(segment.text),
                    )
                )
            scenes.append(NarratedScene(scene_id=scene.scene_id, segments=segments))

        return LessonNarration(
            voice=voice, model_slug=model, scenes=scenes, ready=ready, total=total
        )

    async def available_voices(self) -> list[tuple[str, str]]:
        """As vozes que o provedor configurado oferece.

        Lista vazia quando não há provedor ou quando ele não fala — a tela
        mostra o motivo em vez de um menu de escolhas que não funcionam.
        """
        try:
            resolved = await self.settings.resolve_feature(AIFeature.TRAINING_NARRATION)
        except ProviderNotConfiguredError:
            return []
        return [tuple(item) for item in getattr(resolved.provider, "voices", ())]

    async def set_voice(self, lesson: TrainingLesson, voice: str | None) -> TrainingLesson:
        """Grava a voz da aula. Vazio devolve a aula à voz padrão."""
        chosen = (voice or "").strip() or None
        if chosen is not None:
            known = {slug for slug, _ in await self.available_voices()}
            if known and chosen not in known:
                raise ConflictError(
                    "Esta voz não existe no provedor configurado.",
                    code="unknown_voice",
                )
        lesson.narration_voice = chosen
        await self.session.flush()
        return lesson

    async def get_audio(self, public_id: str) -> TrainingNarration:
        row = (
            await self.session.execute(
                select(TrainingNarration).where(TrainingNarration.public_id == public_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Áudio de narração não encontrado.")
        return row

    def read_bytes(self, row: TrainingNarration) -> bytes:
        return self.storage.read(row.storage_key)

    # ------------------------------------------------------------------ #
    # Geração
    # ------------------------------------------------------------------ #
    async def generate(self, lesson: TrainingLesson, *, force: bool = False) -> LessonNarration:
        """Gera o que falta (ou tudo, com ``force``) e devolve o estado final."""
        try:
            resolved = await self.settings.resolve_feature(AIFeature.TRAINING_NARRATION)
        except ProviderNotConfiguredError as exc:
            raise ConflictError(str(exc.message), code="narration_not_configured") from exc

        options = resolved.binding.options if isinstance(resolved.binding.options, dict) else {}
        voice = self.voice_for(lesson, options)
        model = resolved.model_slug

        plan = self._plan(lesson, voice=voice, model=model)
        if not plan:
            raise ConflictError(
                "Este roteiro não tem texto para narrar.", code="nothing_to_narrate"
            )

        stored = await self._stored(lesson)
        if force:
            # Regerar é apagar o que havia: deixar o arquivo velho no disco
            # encheria o armazenamento com áudio que ninguém mais referencia.
            for row in stored.values():
                self.storage.delete(row.storage_key)
                await self.session.delete(row)
            await self.session.commit()
            stored = {}

        created = 0
        for scene in plan:
            for segment in scene.segments:
                if segment.checksum in stored:
                    continue
                await self._synthesize(
                    lesson,
                    scene_id=scene.scene_id,
                    segment=segment,
                    provider=resolved.provider,
                    provider_slug=resolved.provider_slug,
                    model=model,
                    voice=voice,
                )
                created += 1

        if created:
            await self.session.commit()
        logger.info(
            "training.narration_generated",
            lesson=lesson.public_id,
            created=created,
            voice=voice,
            model=model,
        )
        return await self.overview(lesson)

    async def _synthesize(
        self,
        lesson: TrainingLesson,
        *,
        scene_id: int,
        segment: NarrationSegment,
        provider: object,
        provider_slug: str,
        model: str,
        voice: str,
    ) -> None:
        synthesize = getattr(provider, "synthesize_speech", None)
        if synthesize is None:
            raise ConflictError(
                "O provedor configurado não gera voz.", code="narration_unsupported"
            )

        try:
            result = await synthesize(
                SpeechRequest(
                    text=segment.text,
                    model=model,
                    voice=voice,
                    instructions=segment.direction,
                )
            )
        except SpeechNotSupportedError as exc:
            raise ConflictError(
                f"{exc.message} Escolha um modelo de voz no painel de IA.",
                code="narration_unsupported",
            ) from exc

        stored_file = self.storage.save(
            result.audio,
            prefix=STORAGE_PREFIX,
            extension="mp3",
            mime_type=result.mime_type,
        )
        self.session.add(
            TrainingNarration(
                lesson_id=lesson.id,
                scene_id=scene_id,
                segment_index=segment.index,
                checksum=segment.checksum,
                text=segment.text,
                direction=segment.direction,
                storage_key=stored_file.storage_key,
                mime_type=result.mime_type,
                size_bytes=stored_file.size_bytes,
                voice=voice,
                model_slug=model,
                provider_slug=provider_slug,
                characters=result.characters,
                latency_ms=result.latency_ms,
            )
        )


def _duration_hint(text: str) -> int:
    """Estimativa grosseira de duração, só para o player dimensionar a barra.

    É **dica, não medida**: o player usa a duração real do arquivo assim que o
    áudio carrega. Serve para a interface não nascer com a barra zerada.
    """
    words = max(1, len(text.split()))
    return int(words / 2.6 * 1000)
