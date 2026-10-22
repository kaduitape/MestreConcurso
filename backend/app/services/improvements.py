"""Analista de melhorias (Agente 8) — coleta, grava achado, não aplica nada.

Desenho aprovado em [docs/36-agente-8-desenho.md], com as três decisões do dono
do produto: **opção A** (sem acesso ao repositório), **credencial restrita
junto** e **quatro detectores** no primeiro corte.

Os seis limites do desenho, e onde cada um vive no código:

*L1 — sem escrita em lugar nenhum.* Este serviço escreve em
``improvement_findings`` e ``improvement_detector_settings``. Nenhuma outra
tabela, nenhuma chamada a serviço de configuração — nem para aplicar o que ele
mesmo propôs.

*L2 — sem acesso ao repositório.* Não há leitura de arquivo aqui, e o achado
propõe a mudança em texto. Opção A da decisão D1.

*L3 — nada se aplica sozinho.* Todo achado nasce ``OPEN``.

*L4 — credencial somente-leitura.* Quando ``MYSQL_READONLY_USER`` e
``MYSQL_READONLY_PASSWORD`` estão configuradas, a varredura roda nelas. Se
estiverem configuradas e não conectarem, a varredura **falha** — não há volta
silenciosa para a credencial cheia, porque isso usaria o poder que o desenho
tirou enquanto o painel diria que está isolado.

*L5 — sem amostra, sem achado.* Cada detector devolve ``NOT_ENOUGH_DATA`` com o
que falta, e isso fica gravado na ficha dele. E detector que não pôde rodar
**não fecha** achado antigo: ausência de medição não é ausência de problema.

*L6 — economia só com número medido.* ``measured_waste_cents`` só é preenchido
a partir de ``ai_usage``.

Nenhuma IA participa deste serviço.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Integer, case, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.session import get_restricted_session_factory, get_session_factory
from app.domain.ai_features import FEATURE_BY_SLUG
from app.domain.improvements import (
    DETECTOR_BY_KEY,
    DETECTORS,
    CompetitionGaps,
    DetectorKey,
    DetectorOutcome,
    DetectorStatus,
    FeatureErrors,
    Finding,
    FindingStatus,
    QuestionStats,
    RefusalGroup,
    RouteActivity,
    TopicGap,
    inert_routes,
    model_error_rates,
    refused_resources,
    suspect_answer_keys,
    topics_without_material,
)
from app.models.ai import AIModelRoute, AIRoutingDecision, AIUsage
from app.models.audit import AuditAction
from app.models.catalog import Competition, Subject
from app.models.improvement import ImprovementDetectorSetting, ImprovementFinding
from app.models.mindmap import MindMap
from app.models.notice import Notice
from app.models.notice_analysis import NoticeSubject, NoticeTopic
from app.models.question import Alternative, Question, QuestionAttempt
from app.models.refusal import ResourceRefusal
from app.models.training import TrainingLesson
from app.models.user import User
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.knowledge_tree import topic_subtrees

logger = get_logger(__name__)


class IsolationMode(StrEnum):
    """Quanto da garantia L4 está de fato valendo nesta instalação."""

    #: Usuário de banco restrito: o banco recusa escrita fora das duas tabelas.
    DB_READONLY = "DB_READONLY"
    #: Sem usuário restrito: a garantia é só do código, e o painel diz isso.
    CODE_ONLY = "CODE_ONLY"


class RestrictedCredentialError(AppError):
    """A credencial restrita está configurada e não conecta."""

    status_code = 503
    code = "improvements_restricted_credential_unavailable"
    message = (
        "A credencial somente-leitura do analista está configurada e não conectou. "
        "A varredura não roda com a credencial da aplicação: isso usaria justamente o "
        "poder que o desenho tirou dela."
    )


@dataclass(frozen=True, slots=True)
class DetectorReport:
    key: str
    label: str
    status: str
    detail: str
    found: int


@dataclass(frozen=True, slots=True)
class RunReport:
    """O que a varredura fez, incluindo o que ela não pôde ver."""

    isolation: str
    detectors: tuple[DetectorReport, ...] = ()
    opened: int = 0
    updated: int = 0
    resolved: int = 0
    reopened: int = 0
    muted: int = 0


@dataclass(frozen=True, slots=True)
class DetectorView:
    spec: Any
    row: ImprovementDetectorSetting | None = None
    config: dict[str, Any] = field(default_factory=dict)


def _cutoff(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=max(1, days))


def _aware(value: datetime | None) -> datetime | None:
    """SQLite devolve datetime ingênuo; comparar com agora exige fuso."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class ImprovementService:
    """Varredura e decisão. A sessão do construtor é a da requisição.

    A varredura em si usa a credencial restrita quando ela existe — ver
    ``_scan_session``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Detectores: ficha e limiares
    # ------------------------------------------------------------------ #
    async def detectors(self) -> list[DetectorView]:
        rows = {
            row.key: row
            for row in (await self.session.execute(select(ImprovementDetectorSetting)))
            .scalars()
            .all()
        }
        views: list[DetectorView] = []
        for spec in DETECTORS:
            row = rows.get(spec.key)
            config = dict(spec.defaults)
            if row is not None:
                config.update(row.config or {})
            views.append(DetectorView(spec=spec, row=row, config=config))
        return views

    async def set_detector(
        self,
        key: str,
        *,
        is_enabled: bool | None,
        config: dict[str, int] | None,
        actor: User,
        context: RequestContext,
    ) -> DetectorView:
        spec = DETECTOR_BY_KEY.get(key)
        if spec is None:
            raise NotFoundError("Detector desconhecido.")

        row = (
            await self.session.execute(
                select(ImprovementDetectorSetting).where(ImprovementDetectorSetting.key == key)
            )
        ).scalar_one_or_none()
        if row is None:
            row = ImprovementDetectorSetting(key=key, config={})
            self.session.add(row)

        if is_enabled is not None:
            row.is_enabled = is_enabled
        if config is not None:
            desconhecidos = set(config) - set(spec.defaults)
            if desconhecidos:
                raise ValidationError(
                    "Limiar desconhecido para este detector: " + ", ".join(sorted(desconhecidos)),
                    code="improvement_unknown_threshold",
                    details={"available": sorted(spec.defaults)},
                )
            if any(valor < 0 for valor in config.values()):
                raise ValidationError(
                    "Limiar negativo não descreve amostra nenhuma.",
                    code="improvement_invalid_threshold",
                )
            row.config = {**(row.config or {}), **config}

        await self.audit.record(
            AuditAction.IMPROVEMENT_DETECTOR_UPDATED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="improvement_detector",
            resource_id=key,
            meta={"is_enabled": row.is_enabled, "config": row.config},
        )
        await self.session.commit()
        encontrado = next(item for item in await self.detectors() if item.spec.key == key)
        return encontrado

    # ------------------------------------------------------------------ #
    # Achados
    # ------------------------------------------------------------------ #
    async def findings(
        self, *, status: str | None = None, detector: str | None = None, limit: int = 50
    ) -> list[ImprovementFinding]:
        stmt = select(ImprovementFinding)
        if status:
            stmt = stmt.where(ImprovementFinding.status == status)
        if detector:
            stmt = stmt.where(ImprovementFinding.detector == detector)
        # Severidade primeiro, depois o que foi visto mais vezes: o que insiste
        # em aparecer merece a atenção antes do que apareceu uma vez.
        ordem = case({"HIGH": 0, "MEDIUM": 1, "LOW": 2}, value=ImprovementFinding.severity, else_=3)
        stmt = stmt.order_by(ordem, ImprovementFinding.seen_count.desc()).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def decide(
        self,
        public_id: str,
        *,
        status: str,
        reason: str | None,
        actor: User,
        context: RequestContext,
    ) -> ImprovementFinding:
        """Aceita ou recusa um achado. **Não aplica nada** (limite L3).

        ``RESOLVED`` não é aceito aqui de propósito: um achado só fecha quando o
        detector deixa de achá-lo. Deixar uma pessoa declarar resolvido faria o
        painel mostrar um problema fechado que continua no ar.
        """
        if status not in {FindingStatus.ACCEPTED, FindingStatus.REJECTED, FindingStatus.OPEN}:
            raise ValidationError(
                "Um achado só fecha quando o detector deixa de achá-lo. "
                "Aceite (vai ser feito) ou recuse (com motivo).",
                code="improvement_status_not_decidable",
            )
        if status == FindingStatus.REJECTED and not (reason and reason.strip()):
            raise ValidationError(
                "Recusa exige motivo: recusar sem motivo não ensina nada a ninguém.",
                code="improvement_reason_required",
            )

        row = (
            await self.session.execute(
                select(ImprovementFinding).where(ImprovementFinding.public_id == public_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Achado não encontrado.")

        agora = datetime.now(UTC)
        row.status = status
        row.decided_by_user_id = actor.id
        row.decided_at = agora
        row.decision_reason = (reason or "").strip() or None
        if status == FindingStatus.REJECTED:
            dias = int((await self._config_of(row.detector)).get("mute_days", 90))
            row.muted_until = agora + timedelta(days=max(0, dias))
        else:
            row.muted_until = None

        await self.audit.record(
            AuditAction.IMPROVEMENT_FINDING_DECIDED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="improvement_finding",
            resource_id=public_id,
            meta={"status": status, "detector": row.detector},
        )
        await self.session.commit()
        return row

    async def _config_of(self, detector: str) -> dict[str, Any]:
        for item in await self.detectors():
            if item.spec.key == detector:
                return item.config
        return {}

    # ------------------------------------------------------------------ #
    # Varredura
    # ------------------------------------------------------------------ #
    def _scan_factory(self) -> tuple[Any, str]:
        restrita = get_restricted_session_factory()
        if restrita is not None:
            return restrita, IsolationMode.DB_READONLY
        return get_session_factory(), IsolationMode.CODE_ONLY

    async def run(self) -> RunReport:
        """Roda os detectores ligados e reconcilia os achados."""
        factory, isolation = self._scan_factory()
        configuracoes = {item.spec.key: item for item in await self.detectors()}

        try:
            async with factory() as scan:
                if isolation == IsolationMode.DB_READONLY:
                    # Prova que a credencial restrita conecta antes de começar.
                    await scan.execute(select(1))
                resultados = await self._detect(scan, configuracoes)
                relatorio = await self._reconcile(scan, resultados, configuracoes)
        except SQLAlchemyError as exc:
            if isolation == IsolationMode.DB_READONLY:
                logger.warning("improvements.restricted_credential_failed", error=str(exc))
                raise RestrictedCredentialError() from exc
            raise

        return RunReport(
            isolation=isolation,
            detectors=relatorio[0],
            opened=relatorio[1]["opened"],
            updated=relatorio[1]["updated"],
            resolved=relatorio[1]["resolved"],
            reopened=relatorio[1]["reopened"],
            muted=relatorio[1]["muted"],
        )

    async def _detect(
        self, scan: AsyncSession, configuracoes: dict[str, DetectorView]
    ) -> list[DetectorOutcome]:
        resultados: list[DetectorOutcome] = []
        for key, view in configuracoes.items():
            if view.row is not None and not view.row.is_enabled:
                resultados.append(
                    DetectorOutcome(key, DetectorStatus.DISABLED, "detector desligado")
                )
                continue
            if key == DetectorKey.SUSPECT_ANSWER_KEY:
                resultados.append(await self._run_answer_keys(scan, view.config))
            elif key == DetectorKey.TOPIC_WITHOUT_MATERIAL:
                resultados.append(await self._run_topic_gaps(scan, view.config))
            elif key == DetectorKey.MODEL_ERROR_RATE:
                resultados.append(await self._run_model_errors(scan, view.config))
            elif key == DetectorKey.ROUTE_INERT:
                resultados.append(await self._run_inert_routes(scan, view.config))
            elif key == DetectorKey.REFUSED_RESOURCE:
                resultados.append(await self._run_refusals(scan, view.config))
        return resultados

    async def _reconcile(
        self,
        scan: AsyncSession,
        resultados: list[DetectorOutcome],
        configuracoes: dict[str, DetectorView],
    ) -> tuple[tuple[DetectorReport, ...], dict[str, int]]:
        agora = datetime.now(UTC)
        contagem = {"opened": 0, "updated": 0, "resolved": 0, "reopened": 0, "muted": 0}

        existentes = {
            row.fingerprint: row
            for row in (await scan.execute(select(ImprovementFinding))).scalars().all()
        }

        for resultado in resultados:
            for achado in resultado.findings:
                row = existentes.get(achado.fingerprint)
                if row is None:
                    scan.add(self._new_row(achado, agora))
                    contagem["opened"] += 1
                    continue

                silenciado = _aware(row.muted_until)
                if row.status == FindingStatus.REJECTED and silenciado and silenciado > agora:
                    # Recusado e dentro do prazo: nem atualiza. Insistir num
                    # achado recusado faria o administrador parar de recusar.
                    contagem["muted"] += 1
                    continue

                self._refresh_row(row, achado, agora)
                if row.status == FindingStatus.RESOLVED:
                    row.status = FindingStatus.OPEN
                    row.resolved_at = None
                    row.reopened_count += 1
                    contagem["reopened"] += 1
                elif row.status == FindingStatus.REJECTED:
                    row.status = FindingStatus.OPEN
                    row.muted_until = None
                contagem["updated"] += 1

        # Fechamento automático: só para detector que de fato rodou. Detector
        # sem amostra não fecha nada — ausência de medição não é ausência de
        # problema, e fechar aqui esconderia o problema junto com a lacuna.
        achados_vistos = {
            achado.fingerprint for resultado in resultados for achado in resultado.findings
        }
        rodaram = {
            resultado.detector
            for resultado in resultados
            if resultado.status in {DetectorStatus.FOUND, DetectorStatus.CLEAN}
        }
        for row in existentes.values():
            if row.detector not in rodaram:
                continue
            if row.fingerprint in achados_vistos:
                continue
            if row.status in {FindingStatus.OPEN, FindingStatus.ACCEPTED}:
                row.status = FindingStatus.RESOLVED
                row.resolved_at = agora
                contagem["resolved"] += 1

        fichas: list[DetectorReport] = []
        for resultado in resultados:
            view = configuracoes[resultado.detector]
            # Nome próprio: `row` acima é um achado, e reaproveitá-lo aqui para a
            # ficha do detector confundia dois tipos no mesmo método.
            ficha = (
                await scan.execute(
                    select(ImprovementDetectorSetting).where(
                        ImprovementDetectorSetting.key == resultado.detector
                    )
                )
            ).scalar_one_or_none()
            if ficha is None:
                ficha = ImprovementDetectorSetting(key=resultado.detector, config={})
                scan.add(ficha)
            ficha.last_run_at = agora
            ficha.last_status = resultado.status
            ficha.last_detail = resultado.detail[:500]
            ficha.last_found = len(resultado.findings)
            fichas.append(
                DetectorReport(
                    key=resultado.detector,
                    label=view.spec.label,
                    status=resultado.status,
                    detail=resultado.detail,
                    found=len(resultado.findings),
                )
            )

        await scan.commit()
        return tuple(fichas), contagem

    @staticmethod
    def _new_row(achado: Finding, agora: datetime) -> ImprovementFinding:
        return ImprovementFinding(
            detector=achado.detector,
            status=FindingStatus.OPEN,
            severity=achado.severity,
            destination=achado.destination,
            fingerprint=achado.fingerprint,
            title=achado.title[:255],
            detail=achado.detail,
            proposal=achado.proposal,
            evidence=achado.evidence,
            target_kind=achado.target_kind,
            target_public_id=achado.target_public_id,
            measured_waste_cents=achado.measured_waste_cents,
            first_seen_at=agora,
            last_seen_at=agora,
            seen_count=1,
        )

    @staticmethod
    def _refresh_row(row: ImprovementFinding, achado: Finding, agora: datetime) -> None:
        row.severity = achado.severity
        row.title = achado.title[:255]
        row.detail = achado.detail
        row.proposal = achado.proposal
        row.evidence = achado.evidence
        row.measured_waste_cents = achado.measured_waste_cents
        row.last_seen_at = agora
        row.seen_count += 1

    # ------------------------------------------------------------------ #
    # Detector 1 — gabarito suspeito
    # ------------------------------------------------------------------ #
    async def _run_answer_keys(self, scan: AsyncSession, config: dict[str, Any]) -> DetectorOutcome:
        minimo = int(config.get("min_attempts", 30))
        divisor = int(config.get("chance_divisor", 2))

        agregado = list(
            (
                await scan.execute(
                    select(
                        QuestionAttempt.question_id,
                        func.count(),
                        func.coalesce(func.sum(func.cast(QuestionAttempt.is_correct, Integer)), 0),
                    )
                    .where(QuestionAttempt.is_blank.is_(False))
                    .group_by(QuestionAttempt.question_id)
                )
            ).all()
        )
        considerados = len(agregado)
        elegiveis = {
            int(linha[0]): (int(linha[1]), int(linha[2]))
            for linha in agregado
            if int(linha[1]) >= minimo
        }
        if not elegiveis:
            return suspect_answer_keys(
                [], min_attempts=minimo, chance_divisor=divisor, considered=considerados
            )

        ids = set(elegiveis)
        questoes = {
            int(linha[0]): (str(linha[1]), str(linha[2]), linha[3])
            for linha in (
                await scan.execute(
                    select(Question.id, Question.public_id, Question.statement, Subject.name)
                    .join(Subject, Subject.id == Question.subject_id, isouter=True)
                    .where(Question.id.in_(ids))
                )
            ).all()
        }
        alternativas = {
            int(linha[0]): (int(linha[1]), linha[2])
            for linha in (
                await scan.execute(
                    select(
                        Alternative.question_id,
                        func.count(),
                        func.max(case((Alternative.is_correct.is_(True), Alternative.letter))),
                    )
                    .where(Alternative.question_id.in_(ids))
                    .group_by(Alternative.question_id)
                )
            ).all()
        }
        escolhas: dict[int, tuple[str, int]] = {}
        for linha in (
            await scan.execute(
                select(QuestionAttempt.question_id, QuestionAttempt.selected_letter, func.count())
                .where(
                    QuestionAttempt.question_id.in_(ids),
                    QuestionAttempt.is_blank.is_(False),
                    QuestionAttempt.selected_letter.is_not(None),
                )
                .group_by(QuestionAttempt.question_id, QuestionAttempt.selected_letter)
            )
        ).all():
            qid, letra, total = int(linha[0]), str(linha[1]), int(linha[2])
            atual = escolhas.get(qid)
            if atual is None or total > atual[1]:
                escolhas[qid] = (letra, total)

        linhas: list[QuestionStats] = []
        for qid, (tentativas, acertos) in elegiveis.items():
            dados = questoes.get(qid)
            if dados is None:
                continue
            total_alt, letra_correta = alternativas.get(qid, (0, None))
            escolhida = escolhas.get(qid)
            linhas.append(
                QuestionStats(
                    public_id=dados[0],
                    statement=dados[1],
                    attempts=tentativas,
                    correct=acertos,
                    alternatives=total_alt,
                    answer_letter=str(letra_correta) if letra_correta else None,
                    most_chosen_letter=escolhida[0] if escolhida else None,
                    most_chosen_count=escolhida[1] if escolhida else 0,
                    subject_name=str(dados[2]) if dados[2] else None,
                )
            )

        return suspect_answer_keys(
            linhas, min_attempts=minimo, chance_divisor=divisor, considered=considerados
        )

    # ------------------------------------------------------------------ #
    # Detector 2 — tópico do edital sem material
    # ------------------------------------------------------------------ #
    async def _run_topic_gaps(self, scan: AsyncSession, config: dict[str, Any]) -> DetectorOutcome:
        minimo = int(config.get("min_topics", 1))
        topo = int(config.get("top_topics", 10))

        # Disciplinas analisadas de concursos publicados, do edital mais
        # recente de cada concurso.
        linhas = list(
            (
                await scan.execute(
                    select(
                        Competition.id,
                        Competition.public_id,
                        Competition.name,
                        Notice.id,
                        Notice.title,
                        Notice.created_at,
                        NoticeSubject.id,
                        NoticeSubject.raw_label,
                        NoticeSubject.weight,
                        NoticeSubject.questions_count,
                    )
                    .join(Notice, Notice.competition_id == Competition.id)
                    .join(NoticeSubject, NoticeSubject.notice_id == Notice.id)
                    .where(Competition.is_published.is_(True))
                    .order_by(Competition.id, Notice.created_at.desc())
                )
            ).all()
        )
        if not linhas:
            return topics_without_material([], min_topics=minimo, top_topics=topo)

        edital_do_concurso: dict[int, int] = {}
        for linha in linhas:
            competition_id, notice_id = int(linha[0]), int(linha[3])
            edital_do_concurso.setdefault(competition_id, notice_id)

        disciplinas = [
            linha for linha in linhas if int(linha[3]) == edital_do_concurso[int(linha[0])]
        ]
        subject_ids = [int(linha[6]) for linha in disciplinas]

        topicos = list(
            (
                await scan.execute(
                    select(
                        NoticeTopic.notice_subject_id, NoticeTopic.topic_id, NoticeTopic.raw_label
                    ).where(
                        NoticeTopic.notice_subject_id.in_(subject_ids),
                        NoticeTopic.topic_id.is_not(None),
                    )
                )
            ).all()
        )
        if not topicos:
            return topics_without_material([], min_topics=minimo, top_topics=topo)

        subarvores = await topic_subtrees(
            scan, {int(linha[1]) for linha in topicos if linha[1] is not None}
        )
        alcance = {item for ids in subarvores.values() for item in ids}
        com_material = await self._topics_with_material(scan, alcance)

        por_concurso: dict[int, CompetitionGaps] = {}
        lacunas: dict[int, list[TopicGap]] = {}
        vinculados: dict[int, int] = {}
        for linha in disciplinas:
            competition_id = int(linha[0])
            por_concurso.setdefault(
                competition_id,
                CompetitionGaps(
                    competition_public_id=str(linha[1]),
                    competition_name=str(linha[2]),
                    notice_title=str(linha[4]),
                    gaps=(),
                    linked_topics=0,
                ),
            )
            for topico in topicos:
                if topico[1] is None or int(topico[0]) != int(linha[6] or 0):
                    continue
                vinculados[competition_id] = vinculados.get(competition_id, 0) + 1
                ids = subarvores.get(int(topico[1]), set())
                if ids & com_material:
                    continue
                lacunas.setdefault(competition_id, []).append(
                    TopicGap(
                        label=str(topico[2]),
                        subject_label=str(linha[7]),
                        weight=Decimal(linha[8]) if linha[8] is not None else None,
                        questions_count=int(linha[9]) if linha[9] is not None else None,
                    )
                )

        concursos = [
            CompetitionGaps(
                competition_public_id=item.competition_public_id,
                competition_name=item.competition_name,
                notice_title=item.notice_title,
                gaps=tuple(lacunas.get(competition_id, [])),
                linked_topics=vinculados.get(competition_id, 0),
            )
            for competition_id, item in por_concurso.items()
            if vinculados.get(competition_id, 0) > 0
        ]
        return topics_without_material(concursos, min_topics=minimo, top_topics=topo)

    @staticmethod
    async def _topics_with_material(scan: AsyncSession, topic_ids: set[int]) -> set[int]:
        """Tópicos que têm pelo menos uma questão, aula ou mapa mental.

        Flashcard não entra: ele é do candidato, não do acervo. Contá-lo faria
        um tópico parecer coberto porque uma pessoa fez cartões dele.
        """
        if not topic_ids:
            return set()
        com_material: set[int] = set()
        for coluna in (Question.topic_id, TrainingLesson.topic_id, MindMap.topic_id):
            com_material.update(
                int(linha[0])
                for linha in (
                    await scan.execute(select(coluna).where(coluna.in_(topic_ids)).distinct())
                ).all()
                if linha[0] is not None
            )
        return com_material

    # ------------------------------------------------------------------ #
    # Detector 3 — modelo errando acima do limiar
    # ------------------------------------------------------------------ #
    async def _run_model_errors(
        self, scan: AsyncSession, config: dict[str, Any]
    ) -> DetectorOutcome:
        janela = int(config.get("window_days", 7))
        minimo = int(config.get("min_calls", 20))
        limite = int(config.get("error_rate_percent", 10))
        corte = _cutoff(janela)

        erro = case((AIUsage.status == "ERROR", 1), else_=0)
        agregado = list(
            (
                await scan.execute(
                    select(
                        AIUsage.feature,
                        AIUsage.model_slug,
                        AIUsage.provider_slug,
                        func.count(),
                        func.coalesce(func.sum(erro), 0),
                        func.coalesce(
                            func.sum(
                                case((AIUsage.status == "ERROR", AIUsage.cost_cents), else_=0)
                            ),
                            0,
                        ),
                    )
                    .where(AIUsage.created_at >= corte)
                    .group_by(AIUsage.feature, AIUsage.model_slug, AIUsage.provider_slug)
                )
            ).all()
        )
        codigos: dict[tuple[str, str], tuple[str, int]] = {}
        for linha in (
            await scan.execute(
                select(AIUsage.feature, AIUsage.model_slug, AIUsage.error_code, func.count())
                .where(
                    AIUsage.created_at >= corte,
                    AIUsage.status == "ERROR",
                    AIUsage.error_code.is_not(None),
                )
                .group_by(AIUsage.feature, AIUsage.model_slug, AIUsage.error_code)
            )
        ).all():
            chave = (str(linha[0]), str(linha[1]))
            atual = codigos.get(chave)
            if atual is None or int(linha[3]) > atual[1]:
                codigos[chave] = (str(linha[2]), int(linha[3]))

        linhas = [
            FeatureErrors(
                feature=str(linha[0]),
                feature_label=(
                    FEATURE_BY_SLUG[str(linha[0])].label
                    if str(linha[0]) in FEATURE_BY_SLUG
                    else str(linha[0])
                ),
                model_slug=str(linha[1]),
                provider_slug=str(linha[2]),
                calls=int(linha[3]),
                errors=int(linha[4]),
                error_cost_cents=Decimal(linha[5] or 0),
                top_error_code=(codigos.get((str(linha[0]), str(linha[1])), (None, 0))[0] or None),
            )
            for linha in agregado
        ]
        return model_error_rates(
            linhas, window_days=janela, min_calls=minimo, error_rate_percent=limite
        )

    # ------------------------------------------------------------------ #
    # Detector 4 — regra de roteamento inerte
    # ------------------------------------------------------------------ #
    async def _run_inert_routes(
        self, scan: AsyncSession, config: dict[str, Any]
    ) -> DetectorOutcome:
        janela = int(config.get("window_days", 30))
        minimo = int(config.get("min_decisions", 50))
        teto = int(config.get("max_rows", 2000))
        corte = _cutoff(janela)

        regras = list(
            (await scan.execute(select(AIModelRoute).where(AIModelRoute.is_enabled.is_(True))))
            .scalars()
            .all()
        )
        if not regras:
            return inert_routes(
                [], window_days=janela, min_decisions=minimo, rows_read=0, max_rows=teto
            )

        decisoes = list(
            (
                await scan.execute(
                    select(AIRoutingDecision.trace)
                    .where(AIRoutingDecision.created_at >= corte)
                    .order_by(AIRoutingDecision.id.desc())
                    .limit(teto)
                )
            ).all()
        )
        avaliadas: dict[int, dict[str, Any]] = {}
        for linha in decisoes:
            for entrada in linha[0] or []:
                rule_id = entrada.get("rule_id")
                if rule_id is None:
                    continue
                dados = avaliadas.setdefault(
                    int(rule_id),
                    {"evaluated": 0, "matched": 0, "not_evaluated": 0, "missing": set()},
                )
                dados["evaluated"] += 1
                resultado = entrada.get("outcome")
                if resultado == "MATCHED":
                    dados["matched"] += 1
                elif resultado == "NOT_EVALUATED":
                    dados["not_evaluated"] += 1
                    dados["missing"].update(entrada.get("missing_signals") or [])

        linhas = [
            RouteActivity(
                route_id=regra.id,
                label=regra.label,
                feature=regra.feature,
                feature_label=(
                    FEATURE_BY_SLUG[regra.feature].label
                    if regra.feature in FEATURE_BY_SLUG
                    else regra.feature
                ),
                model_slug=regra.model.slug if regra.model else None,
                evaluated=int(avaliadas.get(regra.id, {}).get("evaluated", 0)),
                matched=int(avaliadas.get(regra.id, {}).get("matched", 0)),
                not_evaluated=int(avaliadas.get(regra.id, {}).get("not_evaluated", 0)),
                missing_signals=tuple(sorted(avaliadas.get(regra.id, {}).get("missing", set()))),
            )
            for regra in regras
        ]
        return inert_routes(
            linhas,
            window_days=janela,
            min_decisions=minimo,
            rows_read=len(decisoes),
            max_rows=teto,
        )

    # ------------------------------------------------------------------ #
    # Detector 5 — recurso recusado por falta de acervo
    # ------------------------------------------------------------------ #
    async def _run_refusals(self, scan: AsyncSession, config: dict[str, Any]) -> DetectorOutcome:
        janela = int(config.get("window_days", 30))
        minimo = int(config.get("min_refusals", 5))
        corte = _cutoff(janela)

        # A idade do registro: sem ela, "nenhuma recusa na janela" soa como
        # acervo completo quando pode significar instrumentação recém-ligada.
        primeira = _aware(
            (await scan.execute(select(func.min(ResourceRefusal.created_at)))).scalar_one_or_none()
        )
        record_days = max(0, (datetime.now(UTC) - primeira).days) if primeira is not None else None

        linhas = list(
            (
                await scan.execute(
                    select(
                        ResourceRefusal.kind,
                        ResourceRefusal.variant,
                        Subject.name,
                        Competition.name,
                        func.count(),
                        func.count(func.distinct(ResourceRefusal.user_id)),
                        func.max(ResourceRefusal.requested),
                        func.min(ResourceRefusal.available),
                        func.min(ResourceRefusal.detail),
                    )
                    .join(Subject, Subject.id == ResourceRefusal.subject_id, isouter=True)
                    .join(
                        Competition,
                        Competition.id == ResourceRefusal.competition_id,
                        isouter=True,
                    )
                    .where(ResourceRefusal.created_at >= corte)
                    .group_by(
                        ResourceRefusal.kind,
                        ResourceRefusal.variant,
                        Subject.name,
                        Competition.name,
                    )
                )
            ).all()
        )
        grupos = [
            RefusalGroup(
                kind=str(linha[0]),
                variant=str(linha[1]) if linha[1] else None,
                subject_label=str(linha[2]) if linha[2] else None,
                competition_name=str(linha[3]) if linha[3] else None,
                total=int(linha[4]),
                distinct_users=int(linha[5] or 0),
                worst_requested=int(linha[6]) if linha[6] is not None else None,
                worst_available=int(linha[7]) if linha[7] is not None else None,
                sample_detail=(str(linha[8])[:200] if linha[8] else None),
            )
            for linha in linhas
        ]
        return refused_resources(
            grupos, window_days=janela, min_refusals=minimo, record_days=record_days
        )
