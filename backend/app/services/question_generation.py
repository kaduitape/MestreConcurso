"""Geração de questões inéditas, com o gabarito conferido na origem.

Era a última peça que faltava para o agente *mestre de batalhas*: a plataforma
**classificava** questão por IA desde a Fase 5, mas não **escrevia** nenhuma.

Quatro regras governam este serviço, e todas as quatro existem porque uma
questão errada ensina errado — e, diferente de um texto ruim, ela ainda registra
o candidato como tendo acertado ou errado algo que não era verdade.

*Material conferido, não qualquer material.* A questão sai de um texto que
alguém já leu: uma aula publicada, ou um material colado por quem cura. Rascunho
de IA não serve de fonte para questão de IA.

*O que é demonstravelmente ruim morre antes de nascer.* As conferências
determinísticas de ``app.domain.question_generation`` jogam fora o rascunho sem
gabarito único, com alternativa repetida, com citação que não existe no material
ou que se apresenta como questão de banca. Nada disso chega à revisão humana —
e nada disso é guardado "com aviso".

*Nenhuma questão gerada se passa por oficial.* Ela nasce com ``origin``
``AI_GENERATED`` e **sem** banca, sem ano e sem prova: inventar essa procedência
seria exatamente a fabricação que o projeto proíbe.

*Nenhuma questão gerada chega a candidato sem conferência humana.* Ela nasce
``DRAFT``; publicar é ação de pessoa, com o portão da Fase 3 no caminho.

O que este serviço **não** garante — e nenhum código garantiria — é que o
gabarito esteja *certo*. A citação prova respaldo declarado no material, não
leitura correta dele. É por isso que a revisão humana continua obrigatória, e é
por isso que o painel diz isso com estas palavras.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import ChatMessage, CompletionRequest, ProviderError
from app.ai.prompts import get_prompt, latest_version
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.content_audit import RuleKey, Severity
from app.domain.model_routing import Signals as RoutingSignals
from app.domain.question_generation import (
    DraftAlternative,
    DraftQuestion,
    Verdict,
    summarize,
    validate,
)
from app.models.ai import AIFeature
from app.models.audit import AuditAction
from app.models.catalog import ExamBoard, Subject, Topic
from app.models.question import (
    Alternative,
    Question,
    QuestionDifficulty,
    QuestionOrigin,
    QuestionStats,
    QuestionStatus,
)
from app.models.user import User
from app.repositories.question import QuestionRepository
from app.services.ai_cache import AICacheService, fingerprint
from app.services.ai_settings import AISettingsService
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.content_audit import ContentAuditService
from app.services.question_bank import statement_checksum

logger = get_logger(__name__)

GENERATE_PROMPT = "question_generate"

#: Quantas questões por chamada. Acima disso a revisão humana vira mutirão, e
#: mutirão de revisão é onde o cuidado se perde.
MAX_PER_CALL = 10
MAX_MATERIAL_CHARS = 8000
MIN_MATERIAL_CHARS = 200

#: Esta regra **não** descarta o rascunho: ela é a razão de ele nascer rascunho.
#: Barrar aqui por "IA sem conferência humana" jogaria fora exatamente a questão
#: que está esperando a conferência humana que a regra exige.
_PUBLICATION_ONLY_RULES = frozenset({RuleKey.AI_WITHOUT_HUMAN_REVIEW})

_DIFFICULTIES = {item.value for item in QuestionDifficulty}


@dataclass(frozen=True, slots=True)
class Discarded:
    """Um rascunho que não entrou, com o motivo em português."""

    statement: str
    reason: str


@dataclass(frozen=True, slots=True)
class QuestionGenerationResult:
    created: list[Question] = field(default_factory=list)
    discarded: list[Discarded] = field(default_factory=list)
    #: Quantos rascunhos cada motivo derrubou — derivado dos vereditos.
    reasons: dict[str, int] = field(default_factory=dict)
    #: Questão igual a uma que já existe no banco não é defeito de geração.
    duplicated: int = 0
    skipped_reason: str | None = None
    model: str | None = None
    prompt_version: str | None = None

    @property
    def asked_review(self) -> int:
        return len(self.created)


class QuestionGenerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.questions = QuestionRepository(session)
        self.ai_settings = AISettingsService(session)
        self.cache = AICacheService(session)
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # A chamada
    # ------------------------------------------------------------------ #
    async def _board_names(self) -> list[str]:
        """Nomes e siglas das bancas do catálogo.

        Servem para barrar o enunciado que se apresenta como questão de banca.
        Saem do banco porque a lista cresce: uma lista fixa no código
        envelheceria no primeiro concurso novo.
        """
        rows = (await self.session.execute(select(ExamBoard.name, ExamBoard.short_name))).all()
        nomes: list[str] = []
        for name, short_name in rows:
            nomes.extend(item for item in (name, short_name) if item)
        return nomes

    async def _drafts(self, *, material: str, quantity: int) -> tuple[list[DraftQuestion], Any]:
        """Pede as questões ao modelo. Devolve os rascunhos crus e o resolvido."""
        resolved = await self.ai_settings.resolve_feature(
            AIFeature.QUESTION_GENERATION,
            signals=RoutingSignals(input_chars=len(material), needs_json=True),
        )
        version = latest_version(GENERATE_PROMPT)
        prompt = get_prompt(GENERATE_PROMPT, version)

        cache_key = fingerprint(
            feature=AIFeature.QUESTION_GENERATION,
            model_slug=resolved.model_slug,
            prompt_version=version,
            payload={"material": statement_checksum(material), "quantity": quantity},
        )
        cached = await self.cache.get(cache_key)
        if cached is not None:
            payload = dict(cached.payload)
        else:
            request = CompletionRequest(
                messages=[
                    ChatMessage(role="system", content=prompt.template),
                    ChatMessage(
                        role="user",
                        content=(
                            f"Gere até {quantity} questões.\n\n<material>\n{material}\n</material>"
                        ),
                    ),
                ],
                model=resolved.model_slug,
                temperature=float(resolved.binding.temperature or 0),
                json_response=True,
            )
            try:
                completion = await resolved.provider.complete(request)
                payload = json.loads(completion.content)
            except ProviderError:
                raise
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValidationError(
                    "A resposta do modelo não seguiu o formato esperado.",
                    code="invalid_ai_response",
                ) from exc

            await self.cache.store(
                cache_key=cache_key,
                feature=AIFeature.QUESTION_GENERATION,
                provider_slug=resolved.provider_slug,
                model_slug=resolved.model_slug,
                payload=payload,
                prompt_version=version,
                input_tokens=completion.usage.input_tokens,
                output_tokens=completion.usage.output_tokens,
                ttl_hours=resolved.binding.cache_ttl_hours,
            )

        rascunhos: list[DraftQuestion] = []
        for item in (payload.get("questions") or [])[:quantity]:
            if not isinstance(item, dict):
                continue
            alternativas = tuple(
                DraftAlternative(
                    letter=str(alt.get("letter") or "").strip(),
                    content=str(alt.get("content") or "").strip(),
                    is_correct=bool(alt.get("is_correct")),
                    feedback=(str(alt.get("feedback")).strip() if alt.get("feedback") else None),
                )
                for alt in (item.get("alternatives") or [])
                if isinstance(alt, dict)
            )
            dificuldade = str(item.get("difficulty") or "").strip().upper()
            rascunhos.append(
                DraftQuestion(
                    statement=str(item.get("statement") or "").strip(),
                    alternatives=alternativas,
                    explanation=str(item.get("explanation") or "").strip(),
                    quote=str(item.get("quote") or "").strip(),
                    difficulty=(
                        dificuldade if dificuldade in _DIFFICULTIES else QuestionDifficulty.MEDIUM
                    ),
                )
            )
        return rascunhos, (payload.get("skipped_reason"), resolved, version)

    # ------------------------------------------------------------------ #
    # A gravação
    # ------------------------------------------------------------------ #
    async def _subject_and_topic(
        self, *, subject_public_id: str | None, topic_public_id: str | None
    ) -> tuple[int | None, int | None]:
        subject_id: int | None = None
        topic_id: int | None = None
        if topic_public_id:
            topic = (
                await self.session.execute(select(Topic).where(Topic.public_id == topic_public_id))
            ).scalar_one_or_none()
            if topic is None:
                raise NotFoundError("Tópico não encontrado.")
            topic_id, subject_id = topic.id, topic.subject_id
        if subject_public_id:
            found = (
                await self.session.execute(
                    select(Subject.id).where(Subject.public_id == subject_public_id)
                )
            ).scalar_one_or_none()
            if found is None:
                raise NotFoundError("Disciplina não encontrada.")
            subject_id = int(found)
        return subject_id, topic_id

    async def _persist(
        self,
        verdict: Verdict,
        *,
        subject_id: int | None,
        topic_id: int | None,
        source_note: str | None,
        model_slug: str | None,
        prompt_version: str | None,
    ) -> Question | None:
        """Cria a questão como rascunho. ``None`` quando ela já existe no banco."""
        draft = verdict.draft
        checksum = statement_checksum(draft.statement)
        if await self.questions.get_by_checksum(checksum) is not None:
            return None

        question = Question(
            checksum=checksum,
            subject_id=subject_id,
            topic_id=topic_id,
            # Sem banca, sem ano e sem prova: a questão é inédita, e preencher
            # esses campos a faria passar por questão aplicada.
            exam_id=None,
            exam_board_id=None,
            year=None,
            statement=draft.statement,
            difficulty=draft.difficulty,
            origin=QuestionOrigin.AI_GENERATED,
            status=QuestionStatus.DRAFT,
            explanation=draft.explanation,
            source_note=source_note,
            ai_suggestion={
                "generated": True,
                "model": model_slug,
                "prompt_version": prompt_version,
                "quote": draft.quote,
            },
        )
        question.alternatives = [
            Alternative(
                letter=item.letter.upper()[:2],
                content=item.content,
                is_correct=item.is_correct,
                feedback=item.feedback,
            )
            for item in draft.alternatives
        ]
        question.stats = QuestionStats(attempts=0, correct_attempts=0, total_time_seconds=0)
        self.session.add(question)
        await self.session.flush()
        return question

    async def _audit_blockers(self, question: Question) -> list[str]:
        """Bloqueios do auditor da Fase 3 que valem **na origem**.

        O portão de publicação é outro e continua valendo. Aqui só interessa o
        que já condena a questão como conteúdo — gabarito ambíguo, alternativa
        repetida, quase-duplicata de outra do banco. A regra de conferência
        humana fica de fora de propósito: ela é a razão de a questão nascer
        rascunho, não motivo para descartá-la.
        """
        findings, _ = await ContentAuditService(self.session).evaluate_question(question)
        return [
            item.message
            for item in findings
            if item.severity == Severity.BLOCKER and item.rule not in _PUBLICATION_ONLY_RULES
        ]

    async def generate(
        self,
        actor: User,
        context: RequestContext,
        *,
        material: str,
        quantity: int = 5,
        subject_public_id: str | None = None,
        topic_public_id: str | None = None,
        source_note: str | None = None,
    ) -> QuestionGenerationResult:
        """Gera questões rascunho a partir de um material, conferindo cada uma."""
        texto = material.strip()
        if len(texto) < MIN_MATERIAL_CHARS:
            raise ValidationError(
                "O material é curto demais para sustentar questão: "
                f"são necessários pelo menos {MIN_MATERIAL_CHARS} caracteres.",
                code="material_too_short",
            )
        texto = texto[:MAX_MATERIAL_CHARS]
        quantos = max(1, min(quantity, MAX_PER_CALL))

        subject_id, topic_id = await self._subject_and_topic(
            subject_public_id=subject_public_id, topic_public_id=topic_public_id
        )
        rascunhos, (skipped_reason, resolved, version) = await self._drafts(
            material=texto, quantity=quantos
        )
        bancas = await self._board_names()

        vereditos = [validate(item, material=texto, board_names=bancas) for item in rascunhos]
        criadas: list[Question] = []
        descartadas = [
            Discarded(statement=item.draft.statement[:160], reason=item.summary)
            for item in vereditos
            if not item.accepted
        ]
        repetidas = 0

        for verdict in (item for item in vereditos if item.accepted):
            question = await self._persist(
                verdict,
                subject_id=subject_id,
                topic_id=topic_id,
                source_note=source_note,
                model_slug=resolved.model_slug,
                prompt_version=version,
            )
            if question is None:
                repetidas += 1
                continue
            bloqueios = await self._audit_blockers(question)
            if bloqueios:
                # Reprovada pelo auditor: ela não fica guardada com aviso.
                await self.session.delete(question)
                await self.session.flush()
                descartadas.append(
                    Discarded(
                        statement=verdict.draft.statement[:160],
                        reason="auditoria de conteúdo: " + " ".join(bloqueios),
                    )
                )
                continue
            criadas.append(question)

        await self.audit.record(
            AuditAction.QUESTION_GENERATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question",
            resource_id=None,
            meta={
                "created": len(criadas),
                "discarded": len(descartadas),
                "duplicated": repetidas,
                "model": resolved.model_slug,
                "topic": topic_public_id,
            },
        )
        await self.session.commit()

        logger.info(
            "questions.generated",
            created=len(criadas),
            discarded=len(descartadas),
            duplicated=repetidas,
        )
        return QuestionGenerationResult(
            created=[
                item
                for item in [
                    await self.questions.get_by_public_id(question.public_id)
                    for question in criadas
                ]
                if item is not None
            ],
            discarded=descartadas,
            reasons=summarize(vereditos),
            duplicated=repetidas,
            skipped_reason=skipped_reason,
            model=resolved.model_slug,
            prompt_version=version,
        )

    # ------------------------------------------------------------------ #
    # Revisão
    # ------------------------------------------------------------------ #
    async def mark_reviewed(self, actor: User, context: RequestContext, public_id: str) -> Question:
        """Registra que uma pessoa conferiu a questão gerada.

        É o que destrava a publicação: o portão da Fase 3 barra conteúdo de IA
        sem conferência humana, e esta é a marca que ele cobra. Quem confere não
        pode ser quem gerou — e, como geração é ação de máquina, quem confere é
        sempre uma pessoa, registrada com nome e hora.
        """
        from datetime import UTC, datetime

        question = await self.questions.get_by_public_id(public_id)
        if question is None:
            raise NotFoundError("Questão não encontrada.")
        if question.origin != QuestionOrigin.AI_GENERATED:
            raise ConflictError(
                "Esta marca existe para questão gerada por IA.",
                code="question_not_generated",
            )
        question.reviewed_by_user_id = actor.id
        question.reviewed_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.QUESTION_REVIEWED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="question",
            resource_id=question.public_id,
        )
        await self.session.commit()
        stored = await self.questions.get_by_public_id(public_id)
        assert stored is not None
        return stored
