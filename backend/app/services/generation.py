"""Geração em massa por tópico do edital.

Quatro regras governam este serviço:

*Ninguém dispara no escuro.* O plano é montado e mostrado com a estimativa
antes de rodar, e só roda depois que **uma pessoa confirma**. A estimativa sai
do custo medido das execuções anteriores — sem amostra, ela diz que não dá para
estimar, em vez de inventar um número.

*O que já existe não é gerado de novo.* O vínculo é com o tópico canônico, que
atravessa concursos: uma aula de "Crase" feita para um concurso já serve a
qualquer outro que cobre o mesmo tópico.

*O teto manda.* Antes de cada item o orçamento é consultado. Estourou, os itens
restantes ficam barrados com o motivo escrito — e uma passada futura tenta de
novo, porque o teto pode ter mudado.

*Nada é publicado aqui.* O conteúdo gerado nasce rascunho. O portão da Fase 3
barra conteúdo de IA que nenhuma pessoa conferiu, e este serviço não tem
permissão para contornar isso: o que ele entrega é fila de revisão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.generation import (
    FEATURE_OF,
    MAX_ITEMS,
    CostSample,
    Decision,
    ExistingContent,
    GenerationKind,
    ItemStatus,
    PlanStatus,
    TopicRef,
    estimate_plan,
    median,
    plan_items,
    plan_status,
    summarize,
)
from app.models.ai import AIUsage
from app.models.audit import AuditAction
from app.models.catalog import Competition, Subject, Topic
from app.models.generation import GenerationItem, GenerationPlan
from app.models.mindmap import MindMap
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.training import TrainingLesson
from app.models.user import User
from app.services.ai_budget import AIBudgetService, BudgetExceededError
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)

#: Quantas execuções passadas entram na mediana. Mais que isso vira memória
#: de preço antigo; menos, amostra frágil.
SAMPLE_WINDOW = 50

#: Itens por passada. A geração roda fora do ciclo HTTP, mas em blocos: assim o
#: acompanhamento ao vivo tem o que mostrar e o teto é consultado com frequência.
BATCH_SIZE = 10


@dataclass(frozen=True, slots=True)
class RunOutcome:
    generated: int
    reused: int
    failed: int
    blocked: int
    remaining: int


class GenerationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)
        self.budget = AIBudgetService(session)

    # ------------------------------------------------------------------ #
    # Insumos do plano
    # ------------------------------------------------------------------ #
    async def _programme(self, competition_id: int) -> list[TopicRef]:
        """Tópicos do edital analisado que já estão ligados ao catálogo.

        Tópico sem vínculo com o catálogo fica de fora: gerar conteúdo para um
        rótulo solto produziria aula que nenhum aluno encontra.
        """
        rows = (
            await self.session.execute(
                select(Topic.id, Topic.name, Subject.id, Subject.name, NoticeTopic.order_index)
                .join(NoticeTopic, NoticeTopic.topic_id == Topic.id)
                .join(NoticeSubject, NoticeTopic.notice_subject_id == NoticeSubject.id)
                .join(Notice, NoticeSubject.notice_id == Notice.id)
                .join(Subject, Topic.subject_id == Subject.id)
                .where(Notice.competition_id == competition_id)
                .order_by(Subject.name, NoticeTopic.order_index)
            )
        ).all()

        vistos: set[int] = set()
        topicos: list[TopicRef] = []
        for topic_id, topic_name, subject_id, subject_name, _ in rows:
            if topic_id in vistos:
                continue
            vistos.add(topic_id)
            topicos.append(
                TopicRef(
                    topic_id=topic_id,
                    topic_name=topic_name,
                    subject_id=subject_id,
                    subject_name=subject_name,
                )
            )
        return topicos

    async def _existing(
        self, topic_ids: list[int], *, competition_id: int, kinds: list[str]
    ) -> list[ExistingContent]:
        """Conteúdo que já cobre os tópicos — em qualquer estado menos arquivado.

        Rascunho conta: gerar de novo porque o rascunho ainda não foi publicado
        seria pagar duas vezes pelo mesmo texto.
        """
        if not topic_ids:
            return []
        achados: list[ExistingContent] = []

        if GenerationKind.TRAINING_LESSON in kinds:
            aulas = (
                (
                    await self.session.execute(
                        select(TrainingLesson).where(
                            TrainingLesson.topic_id.in_(topic_ids),
                            TrainingLesson.status != "ARCHIVED",
                        )
                    )
                )
                .scalars()
                .all()
            )
            achados.extend(
                ExistingContent(
                    topic_id=aula.topic_id,
                    kind=GenerationKind.TRAINING_LESSON,
                    public_id=aula.public_id,
                    from_other_competition=aula.competition_id != competition_id,
                )
                for aula in aulas
                if aula.topic_id is not None
            )

        if GenerationKind.MIND_MAP in kinds:
            mapas = (
                (
                    await self.session.execute(
                        select(MindMap).where(
                            MindMap.topic_id.in_(topic_ids), MindMap.status != "ARCHIVED"
                        )
                    )
                )
                .scalars()
                .all()
            )
            achados.extend(
                # O mapa se liga ao tópico, não ao concurso: a origem fica como
                # desconhecida em vez de ser chutada.
                ExistingContent(
                    topic_id=mapa.topic_id,
                    kind=GenerationKind.MIND_MAP,
                    public_id=mapa.public_id,
                    from_other_competition=None,
                )
                for mapa in mapas
                if mapa.topic_id is not None
            )

        return achados

    async def _samples(self, features: list[str]) -> dict[str, CostSample]:
        """Custo medido das execuções anteriores, por funcionalidade.

        Só entra o que foi **medido de verdade**: chamada bem-sucedida, fora do
        cache e com preço conhecido. Custo zero aqui quer dizer modelo sem preço
        cadastrado — contá-lo puxaria a mediana para baixo e faria a estimativa
        prometer barato.
        """
        amostras: dict[str, CostSample] = {}
        for feature in features:
            valores = (
                (
                    await self.session.execute(
                        select(AIUsage.cost_cents)
                        .where(
                            AIUsage.feature == feature,
                            AIUsage.status == "SUCCESS",
                            AIUsage.cached.is_(False),
                            AIUsage.cost_cents > 0,
                        )
                        .order_by(AIUsage.created_at.desc())
                        .limit(SAMPLE_WINDOW)
                    )
                )
                .scalars()
                .all()
            )
            custos = [Decimal(valor) for valor in valores]
            amostras[feature] = CostSample(
                feature=feature, count=len(custos), median_cents=median(custos)
            )
        return amostras

    # ------------------------------------------------------------------ #
    # Montagem
    # ------------------------------------------------------------------ #
    async def create_plan(
        self,
        *,
        competition_public_id: str,
        kinds: list[str],
        options: dict[str, object],
        actor: User,
        context: RequestContext,
        max_items: int = MAX_ITEMS,
    ) -> GenerationPlan:
        tipos = [kind for kind in kinds if kind in FEATURE_OF]
        if not tipos:
            raise ValidationError(
                "Escolha ao menos um tipo de conteúdo para gerar.", code="generation_no_kinds"
            )

        competition = (
            await self.session.execute(
                select(Competition).where(Competition.public_id == competition_public_id)
            )
        ).scalar_one_or_none()
        if competition is None:
            raise NotFoundError("Concurso não encontrado.")

        topicos = await self._programme(competition.id)
        if not topicos:
            raise ConflictError(
                "O concurso não tem edital analisado com tópicos ligados ao catálogo. "
                "Sem conteúdo programático não há o que gerar.",
                code="generation_no_programme",
            )

        existentes = await self._existing(
            [topic.topic_id for topic in topicos], competition_id=competition.id, kinds=tipos
        )
        planejados = plan_items(topicos, tipos, existentes, max_items=max_items)
        estimativa = estimate_plan(
            planejados, await self._samples(sorted({FEATURE_OF[kind] for kind in tipos}))
        )

        plan = GenerationPlan(
            competition_id=competition.id,
            status=PlanStatus.DRAFT,
            kinds=list(tipos),
            options=dict(options),
            estimate_cents=estimativa.cents,
            estimate_is_known=estimativa.is_known,
            estimate_basis={
                "features": estimativa.basis,
                "unknown_features": list(estimativa.unknown_features),
            },
            created_by_user_id=actor.id,
        )
        for item in planejados:
            plan.items.append(
                GenerationItem(
                    topic_id=item.topic_id,
                    subject_id=item.subject_id,
                    topic_name=item.topic_name[:200],
                    subject_name=item.subject_name[:140],
                    kind=item.kind,
                    decision=item.decision,
                    status=ItemStatus.PENDING,
                    reason=item.reason,
                    target_public_id=item.existing_public_id,
                )
            )
        self.session.add(plan)
        await self.audit.record(
            AuditAction.GENERATION_PLANNED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="generation_plan",
            resource_id=plan.public_id,
            meta={"items": len(planejados), "kinds": tipos},
        )
        await self.session.commit()
        return await self.get(plan.public_id)

    async def confirm(
        self, plan: GenerationPlan, actor: User, context: RequestContext
    ) -> GenerationPlan:
        """Sem esta confirmação, nada dispara."""
        if plan.status not in {PlanStatus.DRAFT, PlanStatus.CANCELED}:
            raise ConflictError(
                "Este plano já foi confirmado.", code="generation_already_confirmed"
            )
        plan.status = PlanStatus.CONFIRMED
        plan.confirmed_by_user_id = actor.id
        plan.confirmed_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.GENERATION_CONFIRMED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="generation_plan",
            resource_id=plan.public_id,
            meta={
                "estimate_cents": str(plan.estimate_cents),
                "estimate_is_known": plan.estimate_is_known,
            },
        )
        await self.session.commit()
        return await self.get(plan.public_id)

    async def cancel(
        self, plan: GenerationPlan, actor: User, context: RequestContext
    ) -> GenerationPlan:
        for item in plan.items:
            if item.status == ItemStatus.PENDING:
                item.status = ItemStatus.CANCELED
                item.reason = "A passada foi cancelada antes de chegar neste item."
        plan.status = PlanStatus.CANCELED
        plan.finished_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.GENERATION_CANCELED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="generation_plan",
            resource_id=plan.public_id,
        )
        await self.session.commit()
        return await self.get(plan.public_id)

    # ------------------------------------------------------------------ #
    # Execução
    # ------------------------------------------------------------------ #
    async def _generate_lesson(
        self, plan: GenerationPlan, item: GenerationItem, actor: User, context: RequestContext
    ) -> str:
        from app.services.training import TrainingService

        opcoes = plan.options or {}
        service = TrainingService(self.session)
        lesson = await service.create(
            actor,
            {
                "subject": item.subject_name,
                "topic": item.topic_name,
                "subject_id": item.subject_id,
                "topic_id": item.topic_id,
                "character_name": str(opcoes.get("character_name") or "Mestre"),
                "level": str(opcoes.get("level") or "INTERMEDIARIO"),
                "style": str(opcoes.get("style") or "AULA"),
                "target_duration_minutes": int(opcoes.get("target_duration_minutes") or 10),
                "competition_public_id": None,
            },
            context,
        )
        # O vínculo com o concurso é feito aqui porque o plano sabe dele.
        lesson.competition_id = plan.competition_id
        await service.generate(lesson, actor, context)
        return lesson.public_id

    async def _generate_mind_map(
        self, plan: GenerationPlan, item: GenerationItem, actor: User, context: RequestContext
    ) -> str:
        from app.services.mindmap import MindMapService

        opcoes = plan.options or {}
        service = MindMapService(self.session)
        mapa = await service.create(
            actor,
            context,
            subject=item.subject_name,
            topic=item.topic_name,
            level=str(opcoes.get("level") or "INTERMEDIARIO"),
            max_panels=int(opcoes.get("max_panels") or 6),
            source_content=None,
        )
        # Vínculo com o catálogo: sem ele o mapa não é encontrado pelo tópico, e
        # a próxima passada o geraria de novo.
        mapa.subject_id = item.subject_id
        mapa.topic_id = item.topic_id
        await service.generate(mapa, actor, context)
        return mapa.public_id

    async def run(
        self,
        plan: GenerationPlan,
        actor: User,
        context: RequestContext,
        *,
        batch_size: int = BATCH_SIZE,
    ) -> RunOutcome:
        """Roda uma passada do plano. Retomar não refaz o que já deu certo."""
        if plan.status == PlanStatus.DRAFT:
            raise ConflictError(
                "O plano precisa ser confirmado antes de rodar.",
                code="generation_not_confirmed",
            )
        if plan.status == PlanStatus.CANCELED:
            raise ConflictError("Este plano foi cancelado.", code="generation_canceled")

        # Barrado pelo teto não é definitivo: o teto pode ter mudado desde então.
        for item in plan.items:
            if item.status == ItemStatus.BUDGET_BLOCKED:
                item.status = ItemStatus.PENDING

        plan.status = PlanStatus.RUNNING
        await self.session.commit()

        gerados = reaproveitados = falhos = barrados = 0
        pendentes = [item for item in plan.items if item.status == ItemStatus.PENDING]
        barrou = False

        for item in pendentes[:batch_size]:
            if item.decision == Decision.REUSE:
                item.status = ItemStatus.REUSED
                item.finished_at = datetime.now(UTC)
                reaproveitados += 1
                continue

            feature = FEATURE_OF[item.kind]
            try:
                await self.budget.guard(feature=feature, spent_run_cents=plan.spent_cents)
            except BudgetExceededError as exc:
                item.status = ItemStatus.BUDGET_BLOCKED
                item.reason = str(getattr(exc, "message", exc))
                item.finished_at = datetime.now(UTC)
                barrados += 1
                barrou = True
                break

            gasto_antes = (await self.budget.overview()).spent_month_cents
            try:
                if item.kind == GenerationKind.TRAINING_LESSON:
                    item.target_public_id = await self._generate_lesson(plan, item, actor, context)
                else:
                    item.target_public_id = await self._generate_mind_map(
                        plan, item, actor, context
                    )
            except Exception as exc:  # o item falha, a passada segue
                item.status = ItemStatus.FAILED
                item.reason = str(exc)[:1000]
                falhos += 1
                logger.warning(
                    "generation.item_failed", plan=plan.public_id, kind=item.kind, error=str(exc)
                )
            else:
                item.status = ItemStatus.DONE
                item.reason = "Rascunho gerado, aguardando revisão humana."
                gerados += 1
            # O custo do item é a diferença do gasto medido: o plano não conta
            # token, ele lê o que a camada de medição registrou.
            gasto_depois = (await self.budget.overview()).spent_month_cents
            item.cost_cents = max(Decimal("0"), gasto_depois - gasto_antes)
            item.finished_at = datetime.now(UTC)
            await self.session.commit()

        if barrou:
            # Barrado o primeiro, os seguintes não passariam: dizer isso de uma
            # vez é melhor que consultar o teto item por item para nada.
            for item in plan.items:
                if item.status == ItemStatus.PENDING:
                    item.status = ItemStatus.BUDGET_BLOCKED
                    item.reason = "O teto de gasto com IA foi atingido antes deste item."
                    item.finished_at = datetime.now(UTC)
                    barrados += 1

        plan.spent_cents = sum((Decimal(item.cost_cents or 0) for item in plan.items), Decimal("0"))
        plan.status = plan_status([item.status for item in plan.items])
        if plan.status == PlanStatus.DONE:
            plan.finished_at = datetime.now(UTC)
        await self.session.commit()

        restantes = sum(1 for item in plan.items if item.status == ItemStatus.PENDING)
        return RunOutcome(
            generated=gerados,
            reused=reaproveitados,
            failed=falhos,
            blocked=barrados,
            remaining=restantes,
        )

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str) -> GenerationPlan:
        found = (
            await self.session.execute(
                select(GenerationPlan).where(GenerationPlan.public_id == public_id)
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Plano de geração não encontrado.")
        return found

    async def list(self, *, limit: int, offset: int) -> tuple[list[GenerationPlan], int]:
        base = select(GenerationPlan).order_by(GenerationPlan.id.desc())
        rows = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        total = int(
            (
                await self.session.execute(select(func.count()).select_from(GenerationPlan))
            ).scalar_one()
        )
        return rows, total

    def progress(self, plan: GenerationPlan) -> object:
        return summarize([item.status for item in plan.items])
