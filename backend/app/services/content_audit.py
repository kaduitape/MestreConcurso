"""O auditor de conteúdo: o portão que roda antes de publicar.

Três responsabilidades, e nenhuma delas é opinar:

1. **Montar o que o domínio precisa.** As regras são puras; buscar o edital, as
   questões parecidas e o estado da revisão é trabalho daqui.
2. **Guardar o laudo.** Cada conferência vira uma linha nova em
   ``content_audits``. O histórico de correções é a sequência de laudos do
   mesmo conteúdo — o defeito aparecendo numa linha e sumindo na seguinte.
3. **Barrar a publicação** quando houver bloqueio, dizendo quais.

O laudo guarda também o **alcance** da conferência: quantas questões entraram
na comparação de duplicata e se havia edital para comparar. Sem isso, "nada
encontrado" viraria uma garantia que o auditor não deu.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.db.session import get_session_factory
from app.domain.catalog_match import score_pair
from app.domain.content_audit import (
    DEFAULT_SETTINGS,
    RULE_BY_KEY,
    RULES,
    AuditableAlternative,
    AuditableMaterial,
    AuditableQuestion,
    DuplicateCandidate,
    Finding,
    RuleKey,
    RuleSetting,
    RuleSpec,
    Severity,
    TargetKind,
    Verdict,
    audit_material,
    audit_question,
    blockers,
    not_checked,
    verdict_of,
)
from app.models.audit import AuditAction
from app.models.content_audit import ContentAudit, ContentAuditRule
from app.models.deck import DeckSourceKind, OfficialDeck
from app.models.flashcard import Flashcard
from app.models.mindmap import MindMap
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.question import Question
from app.models.training import TrainingLesson
from app.models.user import User
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)


class Trigger:
    PUBLISH = "PUBLISH"
    MANUAL = "MANUAL"
    AGENT = "AGENT"


@dataclass(frozen=True, slots=True)
class RuleView:
    """A regra como a tela precisa vê-la: o padrão do código e o que vale hoje."""

    key: str
    label: str
    description: str
    applies_to: tuple[str, ...]
    default_severity: str
    severity: str
    is_enabled: bool
    config: dict[str, object]


@dataclass(frozen=True, slots=True)
class SweepResult:
    """O que o auditor achou ao varrer um concurso inteiro.

    ``notes`` diz o que **ficou de fora** da varredura. Um relatório que não
    declara o próprio alcance vira uma aprovação que ninguém deu.
    """

    audited: int
    blocked: int
    warned: int
    clean: int
    not_checked: int
    notes: tuple[str, ...] = ()


class ContentAuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Regras
    # ------------------------------------------------------------------ #
    async def settings(self) -> dict[str, RuleSetting]:
        """O padrão do código, sobrescrito pelo que estiver no banco."""
        atual = dict(DEFAULT_SETTINGS)
        rows = (await self.session.execute(select(ContentAuditRule))).scalars().all()
        for row in rows:
            if row.key not in RULE_BY_KEY:
                # Regra que saiu do código: a linha fica no banco, mas não manda
                # em nada. Apagar aqui esconderia a decisão de quem a desligou.
                continue
            atual[row.key] = RuleSetting(
                key=row.key,
                is_enabled=row.is_enabled,
                severity=row.severity,
                config=dict(row.config or {}),
            )
        return atual

    async def rules(self) -> list[RuleView]:
        vigentes = await self.settings()
        return [
            RuleView(
                key=spec.key,
                label=spec.label,
                description=spec.description,
                applies_to=spec.applies_to,
                default_severity=spec.severity,
                severity=vigentes[spec.key].severity,
                is_enabled=vigentes[spec.key].is_enabled,
                config=dict(vigentes[spec.key].config),
            )
            for spec in RULES
        ]

    async def set_rule(
        self,
        key: str,
        *,
        is_enabled: bool,
        severity: str,
        config: dict[str, object] | None,
        actor: User,
        context: RequestContext,
    ) -> RuleView:
        spec: RuleSpec | None = RULE_BY_KEY.get(key)
        if spec is None:
            raise NotFoundError("Regra de auditoria desconhecida.")
        if severity not in {Severity.BLOCKER, Severity.WARNING}:
            # NOT_CHECKED não é escolha de configuração: é o que o auditor diz
            # quando faltou insumo para julgar.
            raise ConflictError(
                "A severidade precisa ser BLOCKER ou WARNING.", code="invalid_severity"
            )

        row = (
            await self.session.execute(select(ContentAuditRule).where(ContentAuditRule.key == key))
        ).scalar_one_or_none()
        if row is None:
            row = ContentAuditRule(key=key)
            self.session.add(row)
        row.is_enabled = is_enabled
        row.severity = severity
        row.config = {**dict(spec.config), **(config or {})}
        row.updated_by_user_id = actor.id

        await self.audit.record(
            AuditAction.CONTENT_AUDIT_RULE_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="content_audit_rule",
            resource_id=key,
            meta={"is_enabled": is_enabled, "severity": severity},
        )
        await self.session.commit()
        vigentes = await self.rules()
        return next(item for item in vigentes if item.key == key)

    # ------------------------------------------------------------------ #
    # Insumos
    # ------------------------------------------------------------------ #
    async def _programme_topics(self, competition_id: int | None) -> set[int] | None:
        """Tópicos canônicos que o edital analisado cobra.

        ``None`` quer dizer que **não há com o que comparar** — sem edital, sem
        análise, ou com um programa que nenhuma pessoa ligou ao catálogo. Quem
        recebe None vira NOT_CHECKED, nunca aprovação.
        """
        if competition_id is None:
            return None
        rows = (
            await self.session.execute(
                select(NoticeTopic.topic_id)
                .join(NoticeSubject, NoticeTopic.notice_subject_id == NoticeSubject.id)
                .join(Notice, NoticeSubject.notice_id == Notice.id)
                .where(Notice.competition_id == competition_id)
            )
        ).all()
        ids = {row[0] for row in rows if row[0] is not None}
        return ids or None

    def _topic_verdict(self, topic_id: int | None, programme: set[int] | None) -> bool | None:
        if topic_id is None or programme is None:
            return None
        return topic_id in programme

    async def _duplicates(
        self, question: Question, setting: RuleSetting
    ) -> tuple[tuple[DuplicateCandidate, ...], int]:
        """Questões parecidas da mesma disciplina, e quantas entraram na comparação."""
        if not setting.is_enabled or question.subject_id is None:
            return (), 0
        limite = int(
            setting.config.get(
                "max_comparisons", RULE_BY_KEY[RuleKey.NEAR_DUPLICATE].config["max_comparisons"]
            )
        )
        rows = (
            (
                await self.session.execute(
                    select(Question)
                    .where(
                        Question.subject_id == question.subject_id,
                        Question.id != question.id,
                    )
                    .order_by(Question.created_at.desc())
                    .limit(limite)
                )
            )
            .scalars()
            .all()
        )
        candidatos = []
        for outra in rows:
            score, _ = score_pair(question.statement, outra.statement)
            if score > 0:
                candidatos.append(DuplicateCandidate(public_id=outra.public_id, score=score))
        candidatos.sort(key=lambda item: item.score, reverse=True)
        return tuple(candidatos[:5]), len(rows)

    # ------------------------------------------------------------------ #
    # Conferência
    # ------------------------------------------------------------------ #
    async def _record(
        self,
        *,
        target_kind: str,
        target_public_id: str,
        findings: Sequence[Finding],
        summary: dict[str, object],
        trigger: str,
        actor: User | None,
        competition_id: int | None,
        durable: bool,
    ) -> ContentAudit:
        veredito = verdict_of(findings)
        row = ContentAudit(
            target_kind=target_kind,
            target_public_id=target_public_id,
            verdict=veredito,
            trigger=trigger,
            blocked_publication=veredito == Verdict.BLOCKED and trigger == Trigger.PUBLISH,
            findings=[asdict(item) for item in findings],
            summary={
                **summary,
                "blockers": len(blockers(findings)),
                "warnings": sum(1 for item in findings if item.severity == Severity.WARNING),
                "not_checked": len(not_checked(findings)),
            },
            competition_id=competition_id,
            created_by_user_id=actor.id if actor else None,
        )
        if not durable:
            self.session.add(row)
            await self.session.flush()
            return row

        # O laudo do portão mora numa sessão própria. A recusa desfaz a
        # transação de quem chamou — e o laudo que **explica** a recusa não
        # pode ir embora junto com ela. É a mesma razão pela qual o consumo de
        # IA é gravado fora da transação do chamador.
        factory = get_session_factory()
        async with factory() as session:
            session.add(row)
            await session.commit()
        return row

    async def evaluate_question(
        self, question: Question, *, competition_id: int | None = None
    ) -> tuple[list[Finding], dict[str, object]]:
        """Confere sem gravar laudo.

        É o que a **criação** e a **importação** usam: o conteúdo recusado ali
        nunca chega a existir, e um laudo apontando para uma questão que não
        foi criada só sujaria o histórico. O motivo da recusa vai na resposta.
        """
        vigentes = await self.settings()
        programme = await self._programme_topics(competition_id)
        parecidas, comparadas = await self._duplicates(question, vigentes[RuleKey.NEAR_DUPLICATE])
        alvo = AuditableQuestion(
            public_id=question.public_id,
            kind=question.kind,
            origin=question.origin,
            statement=question.statement,
            explanation=question.explanation,
            alternatives=tuple(
                AuditableAlternative(
                    letter=item.letter, text=item.content, is_correct=item.is_correct
                )
                for item in question.alternatives
            ),
            subject_id=question.subject_id,
            topic_id=question.topic_id,
            generated_by_ai=question.origin == "AI_GENERATED",
            human_reviewed=question.reviewed_by_user_id is not None,
            duplicates=parecidas,
            topic_in_notice=self._topic_verdict(question.topic_id, programme),
        )
        findings = audit_question(alvo, vigentes)
        return findings, {
            "compared_questions": comparadas,
            "programme_topics": len(programme) if programme else 0,
        }

    async def audit_question_row(
        self,
        question: Question,
        *,
        trigger: str = Trigger.MANUAL,
        actor: User | None = None,
        competition_id: int | None = None,
        durable: bool = False,
    ) -> ContentAudit:
        findings, summary = await self.evaluate_question(question, competition_id=competition_id)
        return await self._record(
            target_kind=TargetKind.QUESTION,
            target_public_id=question.public_id,
            findings=findings,
            summary=summary,
            trigger=trigger,
            actor=actor,
            competition_id=competition_id,
            durable=durable,
        )

    async def audit_material_row(
        self,
        *,
        kind: str,
        public_id: str,
        title: str,
        body_count: int,
        subject_id: int | None,
        topic_id: int | None,
        generated_by_ai: bool,
        human_reviewed: bool,
        competition_id: int | None,
        trigger: str = Trigger.MANUAL,
        actor: User | None = None,
        durable: bool = False,
    ) -> ContentAudit:
        vigentes = await self.settings()
        programme = await self._programme_topics(competition_id)
        alvo = AuditableMaterial(
            public_id=public_id,
            kind=kind,
            title=title,
            body_count=body_count,
            subject_id=subject_id,
            topic_id=topic_id,
            generated_by_ai=generated_by_ai,
            human_reviewed=human_reviewed,
            topic_in_notice=self._topic_verdict(topic_id, programme),
        )
        findings = audit_material(alvo, vigentes)
        return await self._record(
            target_kind=kind,
            target_public_id=public_id,
            findings=findings,
            summary={"programme_topics": len(programme) if programme else 0},
            trigger=trigger,
            actor=actor,
            competition_id=competition_id,
            durable=durable,
        )

    # ------------------------------------------------------------------ #
    # O portão
    # ------------------------------------------------------------------ #
    @staticmethod
    def refuse_from(findings: Sequence[Finding]) -> None:
        """Recusa sem laudo gravado — usada onde o conteúdo nem chega a existir."""
        motivos = [item.message for item in blockers(findings)]
        if not motivos:
            return
        raise ConflictError(
            "A auditoria barrou a publicação: " + " ".join(motivos),
            code="content_audit_blocked",
            details={"blockers": motivos},
        )

    @staticmethod
    def _refuse(record: ContentAudit) -> None:
        motivos = [
            str(item["message"])
            for item in record.findings
            if item.get("severity") == Severity.BLOCKER
        ]
        raise ConflictError(
            "A auditoria barrou a publicação: " + " ".join(motivos),
            code="content_audit_blocked",
            details={"audit": record.public_id, "blockers": motivos},
        )

    async def gate_question(
        self, question: Question, *, actor: User, competition_id: int | None = None
    ) -> ContentAudit:
        record = await self.audit_question_row(
            question,
            trigger=Trigger.PUBLISH,
            actor=actor,
            competition_id=competition_id,
            durable=True,
        )
        if record.verdict == Verdict.BLOCKED:
            logger.warning("content_audit.blocked", target=question.public_id, kind="QUESTION")
            self._refuse(record)
        return record

    async def gate_lesson(self, lesson: TrainingLesson, *, actor: User) -> ContentAudit:
        record = await self.audit_material_row(
            kind=TargetKind.TRAINING_LESSON,
            public_id=lesson.public_id,
            title=lesson.title,
            body_count=len((lesson.script or {}).get("scenes") or []),
            subject_id=lesson.subject_id,
            topic_id=lesson.topic_id,
            generated_by_ai=lesson.generated_at is not None,
            # Quem publica é uma pessoa, e é isso que a regra cobra.
            human_reviewed=True,
            competition_id=lesson.competition_id,
            trigger=Trigger.PUBLISH,
            actor=actor,
            durable=True,
        )
        if record.verdict == Verdict.BLOCKED:
            logger.warning("content_audit.blocked", target=record.target_public_id)
            self._refuse(record)
        return record

    async def gate_deck(self, deck: OfficialDeck, *, actor: User, cards: int) -> ContentAudit:
        """O portão do baralho oficial, na publicação.

        ``human_reviewed`` é verdadeiro porque quem publica é uma pessoa — e é
        exatamente isso que a regra de "IA sem conferência humana" cobra. O
        baralho não tem concurso: ele se liga ao tópico, como o mapa mental, e
        por isso a conferência de "tópico fora do edital" sai como **não
        verificada** em vez de inventar um edital de referência.
        """
        record = await self.audit_material_row(
            kind=TargetKind.FLASHCARD_DECK,
            public_id=deck.public_id,
            title=deck.title,
            body_count=cards,
            subject_id=deck.subject_id,
            topic_id=deck.topic_id,
            generated_by_ai=deck.source_kind != DeckSourceKind.EDITORIAL,
            human_reviewed=True,
            competition_id=None,
            trigger=Trigger.PUBLISH,
            actor=actor,
            durable=True,
        )
        if record.verdict == Verdict.BLOCKED:
            logger.warning("content_audit.blocked", target=record.target_public_id)
            self._refuse(record)
        return record

    async def gate_mind_map(self, mind_map: MindMap, *, actor: User) -> ContentAudit:
        record = await self.audit_material_row(
            kind=TargetKind.MIND_MAP,
            public_id=mind_map.public_id,
            title=mind_map.title,
            body_count=len((mind_map.content or {}).get("panels") or []),
            subject_id=mind_map.subject_id,
            topic_id=mind_map.topic_id,
            generated_by_ai=mind_map.generated_at is not None,
            human_reviewed=True,
            competition_id=None,
            trigger=Trigger.PUBLISH,
            actor=actor,
            durable=True,
        )
        if record.verdict == Verdict.BLOCKED:
            logger.warning("content_audit.blocked", target=record.target_public_id)
            self._refuse(record)
        return record

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str) -> ContentAudit:
        found = (
            await self.session.execute(
                select(ContentAudit).where(ContentAudit.public_id == public_id)
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Laudo não encontrado.")
        return found

    async def history(
        self, *, target_kind: str | None, target_public_id: str | None, limit: int, offset: int
    ) -> tuple[list[ContentAudit], int]:
        # Ordena por id: dois laudos no mesmo segundo empatariam por created_at,
        # e o histórico precisa mostrar a ordem real dos fatos.
        base = select(ContentAudit).order_by(ContentAudit.id.desc())
        contagem = select(func.count()).select_from(ContentAudit)
        if target_kind:
            base = base.where(ContentAudit.target_kind == target_kind)
            contagem = contagem.where(ContentAudit.target_kind == target_kind)
        if target_public_id:
            base = base.where(ContentAudit.target_public_id == target_public_id)
            contagem = contagem.where(ContentAudit.target_public_id == target_public_id)
        rows = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        total = int((await self.session.execute(contagem)).scalar_one())
        return rows, total

    async def audit_target(
        self, *, kind: str, public_id: str, actor: User, context: RequestContext
    ) -> ContentAudit:
        """Confere um conteúdo porque uma pessoa pediu.

        Não publica nem barra nada: só produz o laudo. É o que permite conferir
        antes de tentar publicar, e conferir de novo depois de corrigir.
        """
        if kind == TargetKind.QUESTION:
            questao = (
                await self.session.execute(select(Question).where(Question.public_id == public_id))
            ).scalar_one_or_none()
            if questao is None:
                raise NotFoundError("Questão não encontrada.")
            record = await self.audit_question_row(questao, trigger=Trigger.MANUAL, actor=actor)
        elif kind == TargetKind.TRAINING_LESSON:
            aula = (
                await self.session.execute(
                    select(TrainingLesson).where(TrainingLesson.public_id == public_id)
                )
            ).scalar_one_or_none()
            if aula is None:
                raise NotFoundError("Aula não encontrada.")
            record = await self.audit_material_row(
                kind=TargetKind.TRAINING_LESSON,
                public_id=aula.public_id,
                title=aula.title,
                body_count=len((aula.script or {}).get("scenes") or []),
                subject_id=aula.subject_id,
                topic_id=aula.topic_id,
                generated_by_ai=aula.generated_at is not None,
                human_reviewed=aula.published_at is not None,
                competition_id=aula.competition_id,
                trigger=Trigger.MANUAL,
                actor=actor,
            )
        elif kind == TargetKind.MIND_MAP:
            mapa = (
                await self.session.execute(select(MindMap).where(MindMap.public_id == public_id))
            ).scalar_one_or_none()
            if mapa is None:
                raise NotFoundError("Mapa mental não encontrado.")
            record = await self.audit_material_row(
                kind=TargetKind.MIND_MAP,
                public_id=mapa.public_id,
                title=mapa.title,
                body_count=len((mapa.content or {}).get("panels") or []),
                subject_id=mapa.subject_id,
                topic_id=mapa.topic_id,
                generated_by_ai=mapa.generated_at is not None,
                human_reviewed=mapa.published_at is not None,
                competition_id=None,
                trigger=Trigger.MANUAL,
                actor=actor,
            )
        elif kind == TargetKind.FLASHCARD_DECK:
            baralho = (
                await self.session.execute(
                    select(OfficialDeck).where(OfficialDeck.public_id == public_id)
                )
            ).scalar_one_or_none()
            if baralho is None:
                raise NotFoundError("Baralho não encontrado.")
            ativos = (
                await self.session.execute(
                    select(func.count())
                    .select_from(Flashcard)
                    .where(Flashcard.deck_id == baralho.id, Flashcard.is_active.is_(True))
                )
            ).scalar_one()
            record = await self.audit_material_row(
                kind=TargetKind.FLASHCARD_DECK,
                public_id=baralho.public_id,
                title=baralho.title,
                body_count=int(ativos),
                subject_id=baralho.subject_id,
                topic_id=baralho.topic_id,
                generated_by_ai=baralho.source_kind != DeckSourceKind.EDITORIAL,
                # Aqui é conferência avulsa, não publicação: o revisado é o que
                # o estado diz, não o que a ação pede.
                human_reviewed=baralho.published_at is not None,
                competition_id=None,
                trigger=Trigger.MANUAL,
                actor=actor,
            )
        else:
            raise NotFoundError("Tipo de conteúdo desconhecido.")

        await self.audit.record(
            AuditAction.CONTENT_AUDITED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type=kind.lower(),
            resource_id=public_id,
            meta={"verdict": record.verdict},
        )
        await self.session.commit()
        return record

    # ------------------------------------------------------------------ #
    # Varredura (é o que o agente auditor chama)
    # ------------------------------------------------------------------ #
    async def sweep_competition(
        self, competition_id: int, *, actor: User | None = None
    ) -> SweepResult:
        """Confere o conteúdo **publicado** ligado a um concurso.

        Publicado, e não rascunho, de propósito: o rascunho ainda vai passar
        pelo portão quando alguém tentar publicá-lo. O que o auditor precisa
        vasculhar é o que já chegou a quem estuda.
        """
        programme = await self._programme_topics(competition_id)
        notas: list[str] = []
        laudos: list[ContentAudit] = []

        if programme is None:
            notas.append(
                "O concurso não tem edital analisado com tópicos ligados ao catálogo: "
                "questões e mapas não entraram na varredura, e o tópico não foi conferido."
            )
        else:
            questoes = (
                (
                    await self.session.execute(
                        select(Question).where(
                            Question.topic_id.in_(programme),
                            Question.status == "PUBLISHED",
                        )
                    )
                )
                .scalars()
                .all()
            )
            for questao in questoes:
                laudos.append(
                    await self.audit_question_row(
                        questao,
                        trigger=Trigger.AGENT,
                        actor=actor,
                        competition_id=competition_id,
                    )
                )

            mapas = (
                (
                    await self.session.execute(
                        select(MindMap).where(
                            MindMap.topic_id.in_(programme),
                            MindMap.status == "PUBLISHED",
                        )
                    )
                )
                .scalars()
                .all()
            )
            for mapa in mapas:
                laudos.append(
                    await self.audit_material_row(
                        kind=TargetKind.MIND_MAP,
                        public_id=mapa.public_id,
                        title=mapa.title,
                        body_count=len((mapa.content or {}).get("panels") or []),
                        subject_id=mapa.subject_id,
                        topic_id=mapa.topic_id,
                        generated_by_ai=mapa.generated_at is not None,
                        human_reviewed=mapa.published_at is not None,
                        competition_id=competition_id,
                        trigger=Trigger.AGENT,
                        actor=actor,
                    )
                )

        aulas = (
            (
                await self.session.execute(
                    select(TrainingLesson).where(
                        TrainingLesson.competition_id == competition_id,
                        TrainingLesson.status == "PUBLISHED",
                    )
                )
            )
            .scalars()
            .all()
        )
        for aula in aulas:
            laudos.append(
                await self.audit_material_row(
                    kind=TargetKind.TRAINING_LESSON,
                    public_id=aula.public_id,
                    title=aula.title,
                    body_count=len((aula.script or {}).get("scenes") or []),
                    subject_id=aula.subject_id,
                    topic_id=aula.topic_id,
                    generated_by_ai=aula.generated_at is not None,
                    human_reviewed=aula.published_at is not None,
                    competition_id=competition_id,
                    trigger=Trigger.AGENT,
                    actor=actor,
                )
            )

        await self.session.commit()
        return SweepResult(
            audited=len(laudos),
            blocked=sum(1 for item in laudos if item.verdict == Verdict.BLOCKED),
            warned=sum(1 for item in laudos if item.verdict == Verdict.WARNED),
            clean=sum(1 for item in laudos if item.verdict == Verdict.CLEAN),
            not_checked=sum(int(item.summary.get("not_checked", 0)) for item in laudos),
            notes=tuple(notas),
        )
