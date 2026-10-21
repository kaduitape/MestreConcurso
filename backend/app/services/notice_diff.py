"""Retificação de edital: o que mudou, e o que isso atinge.

O serviço só **coleta e grava**: a comparação em si é pura e vive no domínio.
Aqui se busca as duas análises, se monta o retrato de cada uma e se guarda o
resultado — incluindo o impacto no conteúdo que já existe.

Nada é apagado e nada é regenerado automaticamente. Tópico que saiu do edital
deixa a aula **órfã**, com o motivo escrito; tópico que entrou vira item do
próximo plano de geração, que já sabe pular o que existe. Quem decide o que
fazer com cada um é uma pessoa.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.notice_diff import (
    ContentRef,
    EventEntry,
    FactEntry,
    ProgrammeSnapshot,
    SubjectEntry,
    TopicEntry,
    diff,
    impacts,
    summarize,
)
from app.models.audit import AuditAction
from app.models.catalog import Competition
from app.models.mindmap import MindMap
from app.models.notice import Notice
from app.models.notice_analysis import NoticeEvent, NoticeFact, NoticeSubject, NoticeTopic
from app.models.notice_diff import NoticeDiff
from app.models.training import TrainingLesson
from app.models.user import User
from app.services.audit import AuditService
from app.services.auth import RequestContext

logger = get_logger(__name__)


def _valor(bruto: object) -> str:
    """O valor do dado em texto, para comparar duas versões.

    A análise guarda ``{"raw": ...}``; o resto é serializado de forma estável
    para que a ordem das chaves não vire uma mudança que não existiu.
    """
    if isinstance(bruto, dict) and "raw" in bruto:
        bruto = bruto["raw"]
    if isinstance(bruto, str):
        return bruto
    return json.dumps(bruto, sort_keys=True, ensure_ascii=False)


class NoticeDiffService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Retrato de uma análise
    # ------------------------------------------------------------------ #
    async def _snapshot(self, notice_id: int) -> ProgrammeSnapshot:
        disciplinas = (
            (
                await self.session.execute(
                    select(NoticeSubject)
                    .where(NoticeSubject.notice_id == notice_id)
                    .order_by(NoticeSubject.order_index)
                )
            )
            .scalars()
            .all()
        )
        subjects = tuple(
            SubjectEntry(
                raw_label=item.raw_label,
                subject_id=item.subject_id,
                weight=str(item.weight) if item.weight is not None else None,
                questions_count=item.questions_count,
            )
            for item in disciplinas
        )

        rotulo_por_id = {item.id: item.raw_label for item in disciplinas}
        topicos = (
            (
                await self.session.execute(
                    select(NoticeTopic)
                    .where(NoticeTopic.notice_subject_id.in_([item.id for item in disciplinas]))
                    .order_by(NoticeTopic.order_index)
                )
            )
            .scalars()
            .all()
            if disciplinas
            else []
        )
        topics = tuple(
            TopicEntry(
                raw_label=item.raw_label,
                subject_label=rotulo_por_id.get(item.notice_subject_id, ""),
                topic_id=item.topic_id,
            )
            for item in topicos
        )

        eventos = (
            (
                await self.session.execute(
                    select(NoticeEvent)
                    .where(NoticeEvent.notice_id == notice_id)
                    .order_by(NoticeEvent.date_start)
                )
            )
            .scalars()
            .all()
        )
        events = tuple(
            EventEntry(
                kind=item.kind,
                title=item.title,
                date_start=item.date_start,
                date_end=item.date_end,
                evidence_level=item.evidence_level,
            )
            for item in eventos
        )

        dados = (
            (
                await self.session.execute(
                    select(NoticeFact).where(NoticeFact.notice_id == notice_id)
                )
            )
            .scalars()
            .all()
        )
        facts = tuple(
            FactEntry(
                field_path=item.field_path,
                label=item.label,
                value=_valor(item.value),
                evidence_level=item.evidence_level,
            )
            for item in dados
        )

        return ProgrammeSnapshot(subjects=subjects, topics=topics, events=events, facts=facts)

    async def _content_by_topic(self, topic_ids: list[int]) -> dict[int, list[ContentRef]]:
        """Conteúdo vivo ligado a cada tópico — rascunho inclusive."""
        if not topic_ids:
            return {}
        achados: dict[int, list[ContentRef]] = {}

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
        for aula in aulas:
            if aula.topic_id is None:
                continue
            achados.setdefault(aula.topic_id, []).append(
                ContentRef(
                    kind="TRAINING_LESSON",
                    public_id=aula.public_id,
                    title=aula.title,
                    topic_id=aula.topic_id,
                )
            )

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
        for mapa in mapas:
            if mapa.topic_id is None:
                continue
            achados.setdefault(mapa.topic_id, []).append(
                ContentRef(
                    kind="MIND_MAP",
                    public_id=mapa.public_id,
                    title=mapa.title,
                    topic_id=mapa.topic_id,
                )
            )
        return achados

    # ------------------------------------------------------------------ #
    # Comparação
    # ------------------------------------------------------------------ #
    async def _analysed_notices(self, competition_id: int) -> list[Notice]:
        """Editais do concurso que têm conteúdo programático analisado.

        Edital sem análise não entra: comparar com o vazio diria que o edital
        inteiro é novidade, o que seria falso.
        """
        editais = (
            (
                await self.session.execute(
                    select(Notice)
                    .where(Notice.competition_id == competition_id)
                    .order_by(Notice.created_at)
                )
            )
            .scalars()
            .all()
        )
        analisados: list[Notice] = []
        for edital in editais:
            total = int(
                (
                    await self.session.execute(
                        select(func.count())
                        .select_from(NoticeSubject)
                        .where(NoticeSubject.notice_id == edital.id)
                    )
                ).scalar_one()
            )
            if total:
                analisados.append(edital)
        return analisados

    async def compare(
        self,
        *,
        competition_public_id: str,
        from_public_id: str | None,
        to_public_id: str | None,
        actor: User,
        context: RequestContext,
    ) -> NoticeDiff:
        competition = (
            await self.session.execute(
                select(Competition).where(Competition.public_id == competition_public_id)
            )
        ).scalar_one_or_none()
        if competition is None:
            raise NotFoundError("Concurso não encontrado.")

        if from_public_id and to_public_id:
            anterior = await self._notice(from_public_id)
            atual = await self._notice(to_public_id)
        else:
            analisados = await self._analysed_notices(competition.id)
            if len(analisados) < 2:
                raise ConflictError(
                    "O concurso precisa de duas versões de edital analisadas para comparar. "
                    f"Hoje há {len(analisados)}.",
                    code="notice_diff_not_enough_versions",
                )
            anterior, atual = analisados[-2], analisados[-1]

        if anterior.id == atual.id:
            raise ConflictError(
                "As duas versões escolhidas são o mesmo edital.", code="notice_diff_same_notice"
            )

        antes = await self._snapshot(anterior.id)
        depois = await self._snapshot(atual.id)
        mudancas = diff(antes, depois)

        topic_ids = sorted({item.topic_id for item in mudancas if item.topic_id is not None})
        atingidos = impacts(mudancas, await self._content_by_topic(topic_ids))
        resumo = summarize(mudancas, atingidos)

        registro = NoticeDiff(
            competition_id=competition.id,
            from_notice_id=anterior.id,
            to_notice_id=atual.id,
            from_notice_title=anterior.title[:255],
            to_notice_title=atual.title[:255],
            changes=[asdict(item) for item in mudancas],
            impacts=[asdict(item) for item in atingidos],
            summary=asdict(resumo),
            created_by_user_id=actor.id,
        )
        self.session.add(registro)
        await self.audit.record(
            AuditAction.NOTICE_DIFF_CREATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice_diff",
            resource_id=registro.public_id,
            meta={"changes": len(mudancas), "impacts": len(atingidos)},
        )
        await self.session.commit()
        logger.info(
            "notice_diff.created",
            competition=competition_public_id,
            changes=len(mudancas),
            orphaned=resumo.orphaned,
        )
        return await self.get(registro.public_id)

    async def _notice(self, public_id: str) -> Notice:
        found = (
            await self.session.execute(select(Notice).where(Notice.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Edital não encontrado.")
        return found

    # ------------------------------------------------------------------ #
    # Leitura e revisão
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str) -> NoticeDiff:
        found = (
            await self.session.execute(select(NoticeDiff).where(NoticeDiff.public_id == public_id))
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Comparação não encontrada.")
        return found

    async def list(
        self, *, competition_public_id: str | None, limit: int, offset: int
    ) -> tuple[list[NoticeDiff], int]:
        base = select(NoticeDiff).order_by(NoticeDiff.id.desc())
        contagem = select(func.count()).select_from(NoticeDiff)
        if competition_public_id:
            competition = (
                await self.session.execute(
                    select(Competition).where(Competition.public_id == competition_public_id)
                )
            ).scalar_one_or_none()
            alvo = competition.id if competition else -1
            base = base.where(NoticeDiff.competition_id == alvo)
            contagem = contagem.where(NoticeDiff.competition_id == alvo)
        rows = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        return rows, int((await self.session.execute(contagem)).scalar_one())

    async def mark_reviewed(
        self, registro: NoticeDiff, actor: User, context: RequestContext
    ) -> NoticeDiff:
        registro.reviewed_by_user_id = actor.id
        registro.reviewed_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.NOTICE_DIFF_REVIEWED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="notice_diff",
            resource_id=registro.public_id,
        )
        await self.session.commit()
        return await self.get(registro.public_id)
