"""Mestre IA: recupera, calcula em Python, redige com o modelo e confere a origem.

A ordem importa e é sempre a mesma:

1. **prepara** a pergunta (normalização e siglas por dicionário, não por LLM);
2. **recupera** trechos da base do candidato — sem trecho próximo o bastante, para aqui;
3. **calcula** em Python o que for estatística (desempenho, incidência, prioridade)
   e injeta pronto no prompt, proibindo o modelo de recalcular;
4. **pede a redação** ao modelo, em afirmações separadas com citação literal;
5. **confere** cada citação contra o texto recuperado;
6. **grava** a resposta com as afirmações, as origens e o que ficou sem origem.

O passo 5 é o que separa este módulo de um chat comum: uma afirmação factual que
não se sustenta é marcada, e uma resposta inteiramente insustentada vira recusa.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    ChatMessage as ProviderMessage,
)
from app.ai.base import (
    CompletionRequest,
    ProviderError,
)
from app.ai.prompts import get_prompt, latest_version
from app.ai.vector_store import VectorStore
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.tutor import (
    ClaimKind,
    Intent,
    Passage,
    RawClaim,
    VerifiedAnswer,
    prepare,
    verify_answer,
)
from app.models.ai import AIFeature
from app.models.catalog import Competition, Subject
from app.models.intelligence import TopicIncidence, UserPriority
from app.models.notice import Notice
from app.models.question import QuestionAttempt
from app.models.study import StudyPlan, StudyPlanStatus
from app.models.tutor import ChatMode, Conversation, Message, MessageRole, VideoResource
from app.models.user import User
from app.repositories.tutor import ConversationRepository, VideoResourceRepository
from app.services.ai_cache import AICacheService
from app.services.ai_settings import AISettingsService
from app.services.retrieval import RetrievalService

logger = get_logger(__name__)

TUTOR_PROMPT = "tutor_answer"
TEACHER_PROMPT = "tutor_teacher"

MAX_QUESTION_LENGTH = 2000
# Quantas mensagens anteriores entram no contexto da conversa.
HISTORY_TURNS = 6
MAX_VIDEOS = 3


@dataclass(frozen=True, slots=True)
class TutorStage:
    """Um passo do processamento, transmitido ao vivo para a interface."""

    key: str
    label: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class TutorReply:
    message: Message
    answer: VerifiedAnswer
    passages: list[Passage] = field(default_factory=list)
    computed: dict[str, Any] = field(default_factory=dict)
    videos: list[VideoResource] = field(default_factory=list)
    suggested_terms: list[dict[str, str]] = field(default_factory=list)


class TutorService:
    def __init__(self, session: AsyncSession, vector_store: VectorStore | None = None) -> None:
        self.session = session
        self.conversations = ConversationRepository(session)
        self.videos = VideoResourceRepository(session)
        self.retrieval = RetrievalService(session, vector_store)
        self.ai_settings = AISettingsService(session)
        self.cache = AICacheService(session)

    # ------------------------------------------------------------------ #
    # Conversas
    # ------------------------------------------------------------------ #
    async def create_conversation(
        self,
        user: User,
        *,
        title: str | None = None,
        mode: str = ChatMode.TUTOR,
        notice_public_id: str | None = None,
        subject_public_id: str | None = None,
    ) -> Conversation:
        notice_id = None
        if notice_public_id:
            notice_id = (
                await self.session.execute(
                    select(Notice.id).where(Notice.public_id == notice_public_id)
                )
            ).scalar_one_or_none()
            if notice_id is None:
                raise NotFoundError("Edital não encontrado.")

        subject_id = None
        if subject_public_id:
            subject_id = (
                await self.session.execute(
                    select(Subject.id).where(Subject.public_id == subject_public_id)
                )
            ).scalar_one_or_none()
            if subject_id is None:
                raise NotFoundError("Disciplina não encontrada.")

        conversation = Conversation(
            user_id=user.id,
            title=(title or "Nova conversa")[:200],
            mode=mode,
            notice_id=int(notice_id) if notice_id else None,
            subject_id=int(subject_id) if subject_id else None,
        )
        self.session.add(conversation)
        await self.session.commit()
        reloaded = await self.conversations.get_by_public_id(conversation.public_id, user.id)
        assert reloaded is not None
        return reloaded

    async def get_conversation(self, user: User, public_id: str) -> Conversation:
        conversation = await self.conversations.get_by_public_id(public_id, user.id)
        if conversation is None:
            raise NotFoundError("Conversa não encontrada.")
        return conversation

    async def list_conversations(self, user: User, *, limit: int = 30) -> list[Conversation]:
        return list(await self.conversations.list_for_user(user.id, limit=limit))

    async def archive(self, user: User, public_id: str) -> Conversation:
        conversation = await self.get_conversation(user, public_id)
        conversation.is_archived = True
        await self.session.commit()
        return conversation

    # ------------------------------------------------------------------ #
    # Contexto calculado em Python
    # ------------------------------------------------------------------ #
    async def _computed_context(self, user: User, intents: list[Intent]) -> dict[str, Any]:
        """Números prontos para o prompt. O modelo redige; ele não calcula."""
        computed: dict[str, Any] = {}

        if Intent.PERFORMANCE in intents:
            rows = (
                await self.session.execute(
                    select(
                        Subject.name,
                        func.count(),
                        func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0),
                    )
                    .join(Subject, Subject.id == QuestionAttempt.subject_id)
                    .where(QuestionAttempt.user_id == user.id)
                    .group_by(Subject.name)
                    .order_by(func.count().desc())
                )
            ).all()
            computed["desempenho"] = [
                {
                    "disciplina": str(row[0]),
                    "respostas": int(row[1]),
                    "acertos": int(row[2]),
                    "taxa_de_acerto": round(float(row[2]) / float(row[1]), 4),
                }
                for row in rows
                if int(row[1]) > 0
            ] or "sem respostas registradas"

        if Intent.PRIORITY in intents:
            priorities = list(
                (
                    await self.session.execute(
                        select(UserPriority)
                        .where(UserPriority.user_id == user.id)
                        .order_by(UserPriority.score.desc())
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )
            computed["prioridades"] = [
                {"disciplina": row.label, "priority_score": row.score} for row in priorities
            ] or "Priority Score ainda não calculado"

        if Intent.BOARD in intents:
            board_id = await self._board_id(user)
            if board_id is None:
                computed["incidencia"] = "o plano ativo não tem banca definida"
            else:
                incidence = list(
                    (
                        await self.session.execute(
                            select(TopicIncidence)
                            .where(TopicIncidence.exam_board_id == board_id)
                            .order_by(TopicIncidence.incidence_pct.desc())
                            .limit(8)
                        )
                    )
                    .scalars()
                    .all()
                )
                computed["incidencia"] = [
                    {
                        "disciplina": item.subject_name,
                        "incidencia": float(item.incidence_pct),
                        "amostra_questoes": item.questions_count,
                    }
                    for item in incidence
                ] or "sem mapa de incidência calculado para esta banca"

        return computed

    async def _board_id(self, user: User) -> int | None:
        plan = (
            (
                await self.session.execute(
                    select(StudyPlan)
                    .where(StudyPlan.user_id == user.id, StudyPlan.status == StudyPlanStatus.ACTIVE)
                    .order_by(StudyPlan.created_at.desc())
                )
            )
            .scalars()
            .first()
        )
        if plan is None or plan.competition_id is None:
            return None
        row = (
            await self.session.execute(
                select(Competition.exam_board_id).where(Competition.id == plan.competition_id)
            )
        ).scalar_one_or_none()
        return int(row) if row else None

    async def _tenant(self, user: User) -> str:
        return f"user:{user.id}"

    # ------------------------------------------------------------------ #
    # Pergunta e resposta
    # ------------------------------------------------------------------ #
    async def ask(self, user: User, conversation_public_id: str, question: str) -> TutorReply:
        stages: list[TutorStage] = []
        reply: TutorReply | None = None
        async for event in self.ask_stream(user, conversation_public_id, question):
            if isinstance(event, TutorStage):
                stages.append(event)
            else:
                reply = event
        assert reply is not None
        return reply

    async def ask_stream(
        self, user: User, conversation_public_id: str, question: str
    ) -> AsyncIterator[TutorStage | TutorReply]:
        """Executa o pipeline emitindo cada etapa.

        O candidato vê o caminho da resposta, não uma caixa preta.
        """
        text = question.strip()
        if not text:
            raise ValidationError("Escreva uma pergunta.", code="empty_question")
        if len(text) > MAX_QUESTION_LENGTH:
            raise ValidationError(
                f"A pergunta excede {MAX_QUESTION_LENGTH} caracteres.", code="question_too_long"
            )

        conversation = await self.get_conversation(user, conversation_public_id)
        await self._store_message(conversation, user, MessageRole.USER, text)

        yield TutorStage("prepare", "Entendendo a pergunta")
        prepared = prepare(text)

        yield TutorStage("retrieve", "Procurando na sua base")
        retrieval = await self.retrieval.search(
            prepared,
            tenant=await self._tenant(user),
            notice_id=None,
        )
        outcome = retrieval.outcome

        yield TutorStage("compute", "Reunindo os seus números")
        computed = await self._computed_context(user, prepared.intents)

        if not outcome.has_base:
            # Sem base, a resposta é a recusa — e ela também fica registrada.
            answer = verify_answer([], [], refusal=outcome.blocked_reason)
            message = await self._store_answer(
                conversation, user, answer, [], computed, model=None, version=None
            )
            yield TutorStage("verify", "Sem base para responder", outcome.blocked_reason)
            yield TutorReply(
                message=message, answer=answer, passages=[], computed=computed, videos=[]
            )
            return

        yield TutorStage(
            "generate",
            "Redigindo com base nos trechos",
            f"{len(outcome.passages)} trecho(s) recuperado(s)",
        )
        resolved = await self.ai_settings.resolve_feature(AIFeature.CHAT_TUTOR)
        version = latest_version(
            TEACHER_PROMPT if conversation.mode == ChatMode.TEACHER else TUTOR_PROMPT
        )
        prompt = get_prompt(
            TEACHER_PROMPT if conversation.mode == ChatMode.TEACHER else TUTOR_PROMPT, version
        )

        history = await self.conversations.recent_messages(conversation.id, limit=HISTORY_TURNS)
        messages = [ProviderMessage(role="system", content=prompt.template)]
        for item in history:
            messages.append(
                ProviderMessage(
                    role="user" if item.role == MessageRole.USER else "assistant",
                    content=item.content,
                )
            )
        messages.append(
            ProviderMessage(
                role="user",
                content=self._user_prompt(text, outcome.passages, computed),
            )
        )

        try:
            completion = await resolved.provider.complete(
                CompletionRequest(
                    messages=messages,
                    model=resolved.model_slug,
                    temperature=float(resolved.binding.temperature or 0),
                    json_response=True,
                )
            )
            payload = json.loads(completion.content)
        except ProviderError:
            raise
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValidationError(
                "A resposta do modelo não seguiu o formato esperado.",
                code="invalid_ai_response",
            ) from exc

        yield TutorStage("verify", "Conferindo cada citação")
        raw_claims = [
            RawClaim(
                text=str(item.get("text", "")),
                kind=str(item.get("kind", ClaimKind.FACT)),
                quote=item.get("quote"),
            )
            for item in (payload.get("claims") or [])
            if isinstance(item, dict)
        ]
        answer = verify_answer(raw_claims, outcome.passages, refusal=payload.get("refusal") or None)

        videos = await self._videos_for(conversation)
        message = await self._store_answer(
            conversation,
            user,
            answer,
            outcome.passages,
            computed,
            model=resolved.model_slug,
            version=version,
            usage=(completion.usage.input_tokens, completion.usage.output_tokens),
            latency_ms=completion.latency_ms,
        )

        coverage = answer.coverage()
        logger.info(
            "tutor.answered",
            user=user.public_id,
            claims=coverage["claims"],
            resolved=coverage["resolved"],
            unsourced=coverage["unsourced"],
            refusal=answer.is_refusal,
        )
        yield TutorStage(
            "done",
            "Pronto",
            f"{coverage['resolved']} de {coverage['facts']} afirmação(ões) com origem conferida",
        )
        yield TutorReply(
            message=message,
            answer=answer,
            passages=outcome.passages,
            computed=computed,
            videos=videos,
            suggested_terms=[
                {"term": str(item.get("term", "")), "definition": str(item.get("definition", ""))}
                for item in (payload.get("suggested_terms") or [])
                if isinstance(item, dict) and item.get("term")
            ][:5],
        )

    def _user_prompt(self, question: str, passages: list[Passage], computed: dict[str, Any]) -> str:
        blocks = [
            "<contexto>",
            *[
                f"[trecho {index + 1} | documento: {item.document_title} "
                f"| página {item.page_number}]\n{item.content}"
                for index, item in enumerate(passages)
            ],
            "</contexto>",
        ]
        if computed:
            blocks += [
                "",
                "<dados_calculados>",
                json.dumps(computed, ensure_ascii=False, indent=2),
                "</dados_calculados>",
                "Use estes números exatamente como estão. Não recalcule nem arredonde.",
            ]
        blocks += ["", "<pergunta>", question, "</pergunta>"]
        return "\n".join(blocks)

    async def _videos_for(self, conversation: Conversation) -> list[VideoResource]:
        if conversation.subject_id is None:
            return []
        return list(
            await self.videos.verified_for_subject(conversation.subject_id, limit=MAX_VIDEOS)
        )

    # ------------------------------------------------------------------ #
    # Persistência
    # ------------------------------------------------------------------ #
    async def _store_message(
        self, conversation: Conversation, user: User, role: str, content: str
    ) -> Message:
        message = Message(
            conversation_id=conversation.id, user_id=user.id, role=role, content=content
        )
        self.session.add(message)
        conversation.message_count += 1
        conversation.last_message_at = datetime.now(UTC)
        if conversation.title == "Nova conversa" and role == MessageRole.USER:
            conversation.title = content[:80]
        await self.session.commit()
        return message

    async def _store_answer(
        self,
        conversation: Conversation,
        user: User,
        answer: VerifiedAnswer,
        passages: list[Passage],
        computed: dict[str, Any],
        *,
        model: str | None,
        version: str | None,
        usage: tuple[int, int] = (0, 0),
        latency_ms: int = 0,
    ) -> Message:
        coverage = answer.coverage()
        message = Message(
            conversation_id=conversation.id,
            user_id=user.id,
            role=MessageRole.ASSISTANT,
            content=answer.refusal_reason if answer.is_refusal else answer.text,
            claims=[
                {
                    "text": claim.text,
                    "kind": claim.kind,
                    "status": claim.status,
                    "quote": claim.quote,
                    "chunk_id": claim.chunk_id,
                    "page_number": claim.page_number,
                    "document_title": claim.document_title,
                    "note": claim.note,
                }
                for claim in answer.claims
            ],
            sources=[
                {
                    "chunk_id": item.chunk_id,
                    "document_title": item.document_title,
                    "page_number": item.page_number,
                    "score": round(item.score, 4),
                    "excerpt": item.content[:400],
                }
                for item in passages
            ],
            computed_context=computed,
            is_refusal=answer.is_refusal,
            refusal_reason=answer.refusal_reason,
            grounding_ratio=Decimal(str(coverage["ratio"])),
            model_slug=model,
            prompt_version=version,
            input_tokens=usage[0],
            output_tokens=usage[1],
            latency_ms=latency_ms,
        )
        self.session.add(message)
        conversation.message_count += 1
        conversation.last_message_at = datetime.now(UTC)
        await self.session.commit()
        return message
