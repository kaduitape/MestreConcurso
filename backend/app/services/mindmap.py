"""Mapas mentais: da matéria ao painel revisável.

O ciclo é o mesmo do Estúdio de Treinamento, e pela mesma razão: **a IA propõe,
uma pessoa revisa, e só então o mapa é publicado**. Um mapa mental é material de
memorização — quem estuda vai decorar o que estiver escrito ali, então nada
chega a ele sem passar por um humano.

Três cuidados específicos deste serviço:

*O mapa é dado, não imagem.* Gerador de imagem não escreve português confiável,
e um "art. 37" que vira "ait. 3Z" na figura ensina coisa falsa. A IA estrutura;
a plataforma desenha; o texto é texto.

*Fonte não se inventa.* O prompt proíbe criar lei, artigo, súmula ou data que
não esteja no material enviado. Quando a IA tem dúvida, ela registra em
``review_notes`` — e a nota aparece para quem revisa, em vez de sumir.

*O token é pago uma vez.* A impressão digital inclui o conteúdo-base e a versão
do contrato do mapa; gerar o mesmo mapa duas vezes não chama a API.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage, CompletionRequest
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.mindmap import (
    MAP_VERSION,
    MAX_PANELS,
    MIN_PANELS,
    PANELS,
    MapValidationError,
    to_dict,
    validate_content,
)
from app.models.ai import AIFeature
from app.models.audit import AuditAction
from app.models.mindmap import MindMap, MindMapStatus
from app.models.user import User
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

PROMPT_VERSION = "v1"

#: O prompt mestre, reduzido ao que é **regra verificável**.
#:
#: A parte de identidade visual do pedido não vem para cá de propósito: a arte é
#: desenhada pela plataforma, não descrita para um gerador de imagem. O que a IA
#: precisa saber é o que entra em cada painel e o que ela não pode inventar.
SYSTEM_PROMPT = (
    "Você é especialista em preparação para concursos públicos e em design "
    "educacional. Sua tarefa é transformar o conteúdo recebido em um mapa "
    "mental estruturado, em português do Brasil.\n\n"
    "REGRAS INEGOCIÁVEIS:\n"
    "1. Não invente lei, artigo, súmula, data, prazo, autor ou definição. Use "
    "apenas o que estiver no conteúdo enviado ou o que for consenso técnico da "
    "matéria.\n"
    "2. Se tiver dúvida sobre um dado, não o escreva como certo: registre a "
    "dúvida em review_notes para revisão humana.\n"
    "3. Preencha o campo source apenas quando a fonte estiver no material "
    "enviado. Fora isso, deixe-o vazio.\n"
    "4. Texto curto e objetivo. Cada item é uma linha de mapa mental, não um "
    "parágrafo.\n"
    "5. Separe regra geral de exceção. Marque o tom de cada item: NEUTRO, "
    "CORRETO (exemplo certo, regra que vale), INCORRETO (erro, proibição) ou "
    "ALERTA (pegadinha de banca).\n"
    "6. Crie apenas os painéis que o assunto realmente pede. Painel sem "
    "conteúdo relevante é poluição.\n\n"
    "Responda SOMENTE com JSON válido, sem markdown, no formato:\n"
    '{"center_label": "...", "panels": [{"kind": "...", "title": "...", '
    '"items": [{"text": "...", "tone": "NEUTRO", "source": ""}]}], '
    '"review_notes": ["..."]}\n\n'
    "Tipos de painel disponíveis (use o kind exatamente assim):\n"
)


def _panel_catalogue() -> str:
    return "\n".join(f"- {item.kind}: {item.guidance}" for item in PANELS)


def _prompt(lesson: MindMap) -> list[ChatMessage]:
    context: dict[str, Any] = {
        "materia": lesson.subject,
        "assunto": lesson.topic,
        "nivel": lesson.level,
        "max_paineis": lesson.max_panels,
        "conteudo": lesson.source_content or "",
    }
    return [
        ChatMessage(role="system", content=SYSTEM_PROMPT + _panel_catalogue()),
        ChatMessage(role="user", content=json.dumps(context, ensure_ascii=False)),
    ]


class MindMapService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str, *, published_only: bool = False) -> MindMap:
        stmt = select(MindMap).where(MindMap.public_id == public_id)
        if published_only:
            stmt = stmt.where(MindMap.status == MindMapStatus.PUBLISHED)
        found = (await self.session.execute(stmt)).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Mapa mental não encontrado.")
        return found

    async def list(
        self, *, limit: int, offset: int, published_only: bool = False
    ) -> tuple[list[MindMap], int]:
        stmt = select(MindMap)
        if published_only:
            stmt = stmt.where(MindMap.status == MindMapStatus.PUBLISHED)
        rows = list(
            (
                await self.session.execute(
                    stmt.order_by(MindMap.created_at.desc()).limit(limit).offset(offset)
                )
            )
            .scalars()
            .all()
        )
        total = len(list((await self.session.execute(stmt)).scalars().all()))
        return rows, total

    # ------------------------------------------------------------------ #
    # Escrita
    # ------------------------------------------------------------------ #
    async def create(
        self,
        actor: User,
        context: RequestContext,
        *,
        subject: str,
        topic: str,
        level: str,
        max_panels: int,
        source_content: str | None,
    ) -> MindMap:
        if not subject.strip() or not topic.strip():
            raise ValidationError(
                "Matéria e assunto são obrigatórios.", code="mindmap_missing_subject"
            )

        lesson = MindMap(
            created_by_user_id=actor.id,
            subject=subject.strip()[:140],
            topic=topic.strip()[:240],
            title=topic.strip()[:200],
            level=level,
            max_panels=max(MIN_PANELS, min(MAX_PANELS, max_panels)),
            source_content=(source_content or "").strip() or None,
            status=MindMapStatus.DRAFT,
        )
        self.session.add(lesson)
        await self.audit.record(
            AuditAction.TRAINING_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="mind_map",
            resource_id=lesson.public_id,
        )
        await self.session.commit()
        return await self.get(lesson.public_id)

    async def generate(self, lesson: MindMap, actor: User, context: RequestContext) -> MindMap:
        """Pede o mapa à IA, valida e deixa pronto **para revisão**."""
        lesson.status = MindMapStatus.GENERATING
        lesson.generation_error = None
        await self.session.commit()

        cached = None
        try:
            # A resolução do provedor entra no try junto com a chamada: sem IA
            # configurada ela falha aqui, e um mapa travado em GENERATING para
            # sempre seria pior do que o erro — ninguém saberia que parou.
            resolved = await AISettingsService(self.session).resolve_feature(
                AIFeature.MINDMAP_GENERATION
            )
            messages = _prompt(lesson)
            cache_key = fingerprint(
                feature=AIFeature.MINDMAP_GENERATION,
                model_slug=resolved.model_slug,
                prompt_version=f"{PROMPT_VERSION}-{MAP_VERSION}",
                payload={"messages": [message.content for message in messages]},
            )
            cache = AICacheService(self.session)
            cached = await cache.get(cache_key)

            if cached:
                content = cached.payload["content"]
                input_tokens = cached.input_tokens
                output_tokens = cached.output_tokens
                latency_ms = 0
            else:
                completion = await resolved.provider.complete(
                    CompletionRequest(
                        model=resolved.model_slug,
                        messages=messages,
                        temperature=float(resolved.binding.temperature),
                        max_output_tokens=resolved.binding.max_output_tokens or 4000,
                        json_response=True,
                    )
                )
                content = to_dict(
                    validate_content(
                        json.loads(completion.content),
                        subject=lesson.subject,
                        topic=lesson.topic,
                    )
                )
                input_tokens = completion.usage.input_tokens
                output_tokens = completion.usage.output_tokens
                latency_ms = completion.latency_ms
                await cache.store(
                    cache_key=cache_key,
                    feature=AIFeature.MINDMAP_GENERATION,
                    provider_slug=resolved.provider_slug,
                    model_slug=resolved.model_slug,
                    payload={"content": content},
                    prompt_version=f"{PROMPT_VERSION}-{MAP_VERSION}",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    ttl_hours=resolved.binding.cache_ttl_hours,
                )
        except MapValidationError as exc:
            lesson.status = MindMapStatus.DRAFT
            lesson.generation_error = str(exc)[:1000]
            await self.session.commit()
            raise ValidationError(str(exc), code="mindmap_invalid_content") from exc
        except Exception as exc:
            lesson.status = MindMapStatus.DRAFT
            lesson.generation_error = str(exc)[:1000]
            await self.session.commit()
            raise

        lesson.content = content
        # READY, não PUBLISHED: mapa mental é material de memorização, e nada
        # chega a quem estuda sem passar por uma pessoa.
        lesson.status = MindMapStatus.READY
        lesson.model_slug = resolved.model_slug
        lesson.input_tokens = input_tokens
        lesson.output_tokens = output_tokens
        lesson.latency_ms = latency_ms
        lesson.generated_at = datetime.now(UTC)

        await self.audit.record(
            AuditAction.TRAINING_GENERATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="mind_map",
            resource_id=lesson.public_id,
            meta={"panels": len(content.get("panels", []))},
        )
        await self.session.commit()
        logger.info(
            "mindmap.generated",
            map=lesson.public_id,
            panels=len(content.get("panels", [])),
            cached=bool(cached),
        )
        return await self.get(lesson.public_id)

    async def save_content(
        self, lesson: MindMap, actor: User, context: RequestContext, *, title: str, content: Any
    ) -> MindMap:
        """Grava a revisão humana. A validação é a mesma da geração."""
        try:
            validated = to_dict(
                validate_content(content, subject=lesson.subject, topic=lesson.topic)
            )
        except MapValidationError as exc:
            raise ValidationError(str(exc), code="mindmap_invalid_content") from exc

        lesson.title = title.strip()[:200] or lesson.title
        lesson.content = validated
        if lesson.status == MindMapStatus.DRAFT:
            lesson.status = MindMapStatus.READY
        await self.audit.record(
            AuditAction.TRAINING_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="mind_map",
            resource_id=lesson.public_id,
        )
        await self.session.commit()
        return await self.get(lesson.public_id)

    async def publish(self, lesson: MindMap, actor: User, context: RequestContext) -> MindMap:
        if not lesson.content.get("panels"):
            raise ConflictError(
                "Um mapa sem painéis não vai para quem estuda.", code="mindmap_empty"
            )
        lesson.status = MindMapStatus.PUBLISHED
        lesson.published_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.TRAINING_PUBLISHED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="mind_map",
            resource_id=lesson.public_id,
        )
        await self.session.commit()
        return await self.get(lesson.public_id)
