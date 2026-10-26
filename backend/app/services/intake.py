"""Cadastrar um concurso a partir do edital — por endereço ou por arquivo.

Duas entradas, um caminho só. Ou a pessoa cola o endereço da página do concurso
(e o serviço escolhe, entre os PDFs de lá, qual é o edital de abertura), ou ela
**sobe o PDF** — e aí não há o que escolher. Dali para frente é o mesmo: o
edital é criado, o PDF é guardado com checksum, a análise da Fase 3 roda, e cada
campo sai com a citação literal que o sustenta e a página onde ela está.

**O cadastro acontece sozinho**, e é isso que foi pedido: "subo o edital e o
sistema cadastra todos os dados do concurso". O que o automático preenche é
**exatamente** o que o edital sustenta por citação conferida caractere a
caractere — concurso, cargo, vagas, salário, escolaridade, datas, e a grade de
disciplinas com peso e número de questões. O que o edital não sustenta **fica
em branco e é nomeado** na lista de lacunas, item por item.

Essa é a linha, e ela não é burocracia: preencher um campo que a IA deduziu
seria assinar no lugar de alguém, e um candidato estudaria a matéria errada para
a prova errada. Deixar o campo vazio com o motivo escrito custa um clique a
quem cadastra; preencher com palpite custa um concurso inteiro a quem estuda.
Por isso "cadastrado" nunca quer dizer "completo" aqui — a tela mostra as duas
contas lado a lado.

Quatro coisas seguram o automático e devolvem a decisão para uma pessoa, com o
motivo escrito: edital sem nome de concurso conferido; sem nenhuma data oficial
de onde tirar o ano; concurso de mesmo nome e ano já no catálogo; e análise que
falhou. Nesses casos o estado para em ``AWAITING_REVIEW`` e o formulário de
revisão continua ali, inteiro.

O que é reaproveitado, inteiro: o pipeline de análise de edital (Fase 3), com a
conferência literal de cada citação; o armazenamento de PDF com checksum; o
catálogo e suas rotinas de criação; o casamento determinístico de disciplina
(``app.domain.catalog_match``); a medição e o teto de gasto de IA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.domain.catalog_match import CatalogEntry, MatchReason, suggest
from app.domain.intake import AddressRefusedError, choose_notice, ensure_fetchable, pdf_links
from app.models.audit import AuditAction
from app.models.catalog import (
    Competition,
    ExamBoard,
    Organization,
    Position,
    PositionSubject,
    Subject,
)
from app.models.intake import CompetitionIntake, IntakeSourceKind, IntakeStatus
from app.models.notice import NoticeKind
from app.models.notice_analysis import (
    EvidenceLevel,
    NoticeFact,
    NoticePosition,
    NoticeSubject,
)
from app.models.user import User
from app.services.audit import AuditService
from app.services.auth import RequestContext
from app.services.storage import validate_pdf
from app.services.web_fetch import FetchedResource, FetchRefusedError, fetch

logger = get_logger(__name__)

#: Campos que o cadastro usa da ficha extraída, e para onde cada um vai.
#: O que não está aqui continua guardado no edital (e visível na tela dele),
#: mas não entra no cadastro do concurso — inventar destino para um campo
#: produziria ficha preenchida com dado que ninguém pediu ali.
FIELD_TO_COMPETITION: dict[str, str] = {
    "competition.name": "name",
    "position.education_level": "education_level",
    "position.vacancies": "vacancies_total",
    "position.salary_cents": "salary_max_cents",
    "registration.start_date": "registration_start",
    "registration.end_date": "registration_end",
    "exam.date": "exam_date",
}

#: Campos do cargo, e para onde cada um vai em ``positions``. O cargo é parte
#: de "todos os dados do concurso": sem ele a grade de disciplinas não tem onde
#: morar, e sem grade o estudo não sabe o que cai.
FIELD_TO_POSITION: dict[str, str] = {
    "position.name": "name",
    "position.education_level": "education_level",
    "position.salary_cents": "salary_cents",
    "position.vacancies": "vacancies",
    "exam.questions_count": "questions_count",
    "exam.duration_minutes": "exam_duration_minutes",
}

#: De onde o ano do concurso é derivado, em ordem de preferência. O ano **não é
#: um campo do edital** — nenhum edital escreve "ano: 2026" —, então ele sai da
#: data oficial mais específica que houver. Derivar de data conferida é
#: aritmética sobre dado do edital; chutar o ano corrente seria invenção, e é
#: por isso que a falta de qualquer data segura o cadastro automático.
YEAR_SOURCES: tuple[str, ...] = (
    "exam.date",
    "registration.start_date",
    "registration.end_date",
)

#: Níveis de evidência que podem ser aplicados sem alguém digitar o valor de
#: novo. Inferido e não localizado chegam à tela **em branco**, com o motivo.
APPLICABLE_LEVELS = frozenset({EvidenceLevel.OFFICIAL, EvidenceLevel.CONFIRMED})

#: Só casamento de **nome idêntico** vira grade sozinho. O módulo de casamento
#: diz, no próprio docstring, por que: casar "Direito Constitucional" com
#: "Direito Administrativo" porque as duas começam igual é pior que não casar —
#: o aluno estudaria a disciplina errada achando que está no lugar certo. As
#: notas por continência e por palavras em comum continuam só sugerindo.
AUTO_LINK_REASONS = frozenset({MatchReason.EXACT})


class GapCode(StrEnum):
    """O que o cadastro automático não preencheu. Sempre dito, nunca só contado."""

    FIELD_WITHOUT_EVIDENCE = "FIELD_WITHOUT_EVIDENCE"
    POSITION_NOT_FOUND = "POSITION_NOT_FOUND"
    POSITION_WITHOUT_EVIDENCE = "POSITION_WITHOUT_EVIDENCE"
    POSITION_DUPLICATED = "POSITION_DUPLICATED"
    SUBJECT_WITHOUT_CATALOG = "SUBJECT_WITHOUT_CATALOG"
    GRADE_EMPTY = "GRADE_EMPTY"
    SHORT_NAME_DERIVED = "SHORT_NAME_DERIVED"
    BOARD_NOT_FOUND = "BOARD_NOT_FOUND"


class AutoApplyBlock(StrEnum):
    """Por que o cadastro automático parou e devolveu a decisão para alguém."""

    NO_COMPETITION_NAME = "NO_COMPETITION_NAME"
    NO_ORGANIZATION = "NO_ORGANIZATION"
    NO_YEAR = "NO_YEAR"
    DUPLICATE = "DUPLICATE"


BLOCK_LABEL: dict[str, str] = {
    AutoApplyBlock.NO_COMPETITION_NAME: (
        "o nome do concurso não foi encontrado no edital com citação conferida — "
        "sem nome não há o que cadastrar"
    ),
    AutoApplyBlock.NO_ORGANIZATION: (
        "o órgão do concurso não foi encontrado no edital com citação conferida, e "
        "não há órgão no catálogo que combine — um concurso é sempre de alguém"
    ),
    AutoApplyBlock.NO_YEAR: (
        "nenhuma data oficial (prova ou inscrições) foi conferida no edital, e o ano "
        "do concurso sai dela — chutar o ano corrente seria inventar"
    ),
    AutoApplyBlock.DUPLICATE: (
        "já existe um concurso com este nome e ano no catálogo — cadastrar de novo "
        "criaria duplicata"
    ),
}


@dataclass(frozen=True, slots=True)
class Gap:
    """Uma coisa que ficou faltando, com nome e motivo."""

    code: str
    label: str
    detail: str | None = None

    def as_json(self) -> dict[str, Any]:
        return {"code": self.code, "label": self.label, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """O PDF do edital, de onde quer que ele tenha vindo.

    Existe para que o caminho depois da obtenção seja **um só**: o endereço
    colado e o arquivo subido chegam aqui no mesmo formato, e dali para frente
    nada no serviço sabe a diferença.
    """

    content: bytes
    filename: str
    declared_mime: str | None
    #: Nulo quando o arquivo foi subido: não houve endereço envolvido.
    source_url: str | None
    title: str


@dataclass(frozen=True, slots=True)
class ProposedField:
    """Um campo da proposta, com a procedência à vista."""

    field_path: str
    label: str
    value: Any
    evidence_level: str
    quote: str | None = None
    page_number: int | None = None
    #: Para onde este campo vai na ficha do concurso, quando vai.
    target: str | None = None
    #: Para onde ele vai no cargo. Um campo pode ir para os dois (escolaridade
    #: fica na ficha e no cargo), para um só, ou para nenhum.
    position_target: str | None = None

    @property
    def applicable(self) -> bool:
        return self.value is not None and self.evidence_level in APPLICABLE_LEVELS

    @property
    def lands_somewhere(self) -> bool:
        return self.target is not None or self.position_target is not None

    def as_json(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "label": self.label,
            "value": self.value,
            "evidence_level": self.evidence_level,
            "quote": self.quote,
            "page_number": self.page_number,
            "target": self.target,
            "position_target": self.position_target,
            "applicable": self.applicable,
        }


class CompetitionIntakeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    async def get(self, public_id: str) -> CompetitionIntake:
        found = (
            await self.session.execute(
                select(CompetitionIntake).where(CompetitionIntake.public_id == public_id)
            )
        ).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Cadastro por URL não encontrado.")
        return found

    async def list_intakes(
        self, *, limit: int, offset: int, status: str | None = None
    ) -> tuple[list[CompetitionIntake], int]:
        base = select(CompetitionIntake).order_by(CompetitionIntake.id.desc())
        contagem = select(func.count()).select_from(CompetitionIntake)
        if status:
            base = base.where(CompetitionIntake.status == status)
            contagem = contagem.where(CompetitionIntake.status == status)
        rows = list((await self.session.execute(base.limit(limit).offset(offset))).scalars().all())
        total = int((await self.session.execute(contagem)).scalar_one())
        return rows, total

    # ------------------------------------------------------------------ #
    # 1. Buscar e escolher
    # ------------------------------------------------------------------ #
    async def start_from_upload(
        self,
        *,
        content: bytes,
        filename: str,
        declared_mime: str | None,
        auto_apply: bool,
        actor: User,
        context: RequestContext,
    ) -> CompetitionIntake:
        """Sobe o PDF do edital e cadastra o concurso.

        É a entrada mais curta que existe: não há página para ler nem link para
        escolher, porque a pessoa já disse qual é o documento. O arquivo passa
        pela mesma validação de conteúdo do upload de edital (que confere se o
        PDF é PDF de verdade, e não um executável renomeado) antes de qualquer
        outra coisa.
        """
        validate_pdf(content, declared_mime=declared_mime)

        intake = CompetitionIntake(
            source_kind=IntakeSourceKind.UPLOAD,
            source_url=None,
            source_name=filename[:255],
            status=IntakeStatus.ANALYZING,
            created_by_user_id=actor.id,
            # Nada a escolher: o documento veio apontado.
            candidates=[],
            choice_reason="o arquivo foi enviado direto",
        )
        self.session.add(intake)
        await self.audit.record(
            AuditAction.INTAKE_STARTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="competition_intake",
            resource_id=intake.public_id,
            meta={"upload": filename[:255], "auto_apply": auto_apply},
        )
        await self.session.commit()

        return await self._analyze(
            intake,
            SourceDocument(
                content=content,
                filename=filename[:255],
                declared_mime=declared_mime,
                source_url=None,
                title=_title_from(filename),
            ),
            auto_apply=auto_apply,
            actor=actor,
            context=context,
        )

    async def start(
        self,
        *,
        url: str,
        auto_apply: bool = True,
        actor: User,
        context: RequestContext,
    ) -> CompetitionIntake:
        """Busca o endereço e, quando dá para decidir, segue até a proposta."""
        # A recusa que se decide só pelo texto do endereço acontece antes de
        # gravar: endereço interno ou esquema que não é HTTP é erro de pedido,
        # não passagem que falhou. O que depende de rede (nome que resolve para
        # a rede interna, site fora do ar, arquivo que não é PDF) já é
        # passagem, e fica registrado como FAILED com o motivo.
        try:
            url = ensure_fetchable(url)
        except AddressRefusedError as exc:
            raise FetchRefusedError(str(exc)) from exc

        intake = CompetitionIntake(
            source_kind=IntakeSourceKind.URL,
            source_url=url[:500],
            status=IntakeStatus.FETCHING,
            created_by_user_id=actor.id,
        )
        self.session.add(intake)
        await self.audit.record(
            AuditAction.INTAKE_STARTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="competition_intake",
            resource_id=intake.public_id,
            meta={"url": url[:500], "auto_apply": auto_apply},
        )
        await self.session.commit()

        try:
            recurso = await fetch(url)
        except FetchRefusedError as exc:
            return await self._fail(intake, exc.message)

        if recurso.looks_like_pdf:
            # O endereço já é o PDF: não há o que escolher, e dizer isso é
            # melhor que inventar uma pontuação para um candidato único.
            intake.candidates = []
            intake.chosen_url = recurso.final_url[:500]
            intake.choice_reason = "o endereço informado já é o PDF do edital"
            await self.session.commit()
            return await self._analyze(
                intake,
                _document_from(recurso),
                auto_apply=auto_apply,
                actor=actor,
                context=context,
            )

        if not recurso.looks_like_html:
            return await self._fail(
                intake,
                "O endereço não devolveu página HTML nem PDF "
                f"(tipo recebido: {recurso.content_type or 'desconhecido'}).",
            )

        candidatos = pdf_links(
            recurso.content.decode("utf-8", errors="replace"), base_url=recurso.final_url
        )
        escolha = choose_notice(candidatos)
        intake.candidates = [
            {
                "url": item.candidate.url,
                "text": item.candidate.text,
                "score": item.score,
                "explanation": item.explanation,
            }
            for item in escolha.ranked
        ]

        if escolha.refused:
            # Recusa é resultado, não falha: a página foi lida, os candidatos
            # estão listados com a pontuação, e falta uma pessoa apontar qual.
            intake.status = IntakeStatus.AWAITING_CHOICE
            intake.choice_reason = escolha.refusal
            intake.detail = escolha.refusal
            await self.session.commit()
            logger.info("intake.awaiting_choice", intake=intake.public_id, reason=escolha.refusal)
            return intake

        assert escolha.chosen is not None
        intake.chosen_url = escolha.chosen.candidate.url[:500]
        intake.choice_reason = escolha.chosen.explanation
        await self.session.commit()
        return await self.choose(
            intake,
            url=escolha.chosen.candidate.url,
            auto_apply=auto_apply,
            actor=actor,
            context=context,
        )

    async def choose(
        self,
        intake: CompetitionIntake,
        *,
        url: str,
        auto_apply: bool = True,
        actor: User,
        context: RequestContext,
    ) -> CompetitionIntake:
        """Busca o PDF escolhido — pelo serviço ou por uma pessoa — e analisa."""
        if intake.status in {IntakeStatus.APPLIED, IntakeStatus.REJECTED}:
            raise ConflictError("Este cadastro já foi concluído.", code="intake_already_finished")
        try:
            recurso = await fetch(url)
        except FetchRefusedError as exc:
            return await self._fail(intake, exc.message)

        if not recurso.looks_like_pdf:
            return await self._fail(intake, "O endereço escolhido não devolveu um PDF.")

        if intake.chosen_url != url[:500]:
            intake.chosen_url = url[:500]
            intake.choice_reason = "endereço apontado por uma pessoa"
        await self.session.commit()
        return await self._analyze(
            intake,
            _document_from(recurso),
            auto_apply=auto_apply,
            actor=actor,
            context=context,
        )

    # ------------------------------------------------------------------ #
    # 2. Analisar e propor
    # ------------------------------------------------------------------ #
    async def _analyze(
        self,
        intake: CompetitionIntake,
        document: SourceDocument,
        *,
        auto_apply: bool,
        actor: User,
        context: RequestContext,
    ) -> CompetitionIntake:
        """Cria o edital, roda o pipeline da Fase 3 e monta a proposta."""
        from app.services.notice import NoticeService
        from app.services.notice_analysis import NoticeAnalysisService

        intake.status = IntakeStatus.ANALYZING
        await self.session.commit()

        notices = NoticeService(self.session)
        try:
            notice = await notices.create_notice(
                {
                    "title": document.title,
                    "kind": NoticeKind.MAIN,
                    "source_url": document.source_url,
                },
                competition_public_id=None,
                actor=actor,
                context=context,
            )
            file = await notices.upload_file(
                notice.public_id,
                content=document.content,
                original_name=document.filename,
                declared_mime=document.declared_mime,
                actor=actor,
                context=context,
            )
        except AppError as exc:
            return await self._fail(intake, exc.message)

        # A relação é atribuída, não só a chave estrangeira: com
        # ``expire_on_commit=False`` o carregamento tardio depois do commit
        # acontece fora do laço assíncrono e estoura.
        intake.notice = notice
        await self.session.commit()
        logger.info(
            "intake.notice_created",
            intake=intake.public_id,
            notice=notice.public_id,
            size=file.size_bytes,
        )

        # O PDF foi anexado depois de o edital já estar carregado nesta sessão;
        # sem recarregar a coleção, a análise olharia um edital sem arquivos.
        await self.session.refresh(notice, ["files"])
        try:
            await NoticeAnalysisService(self.session).analyze(notice, actor=actor, context=context)
        except AppError as exc:
            # O edital e o PDF ficam gravados: a análise pode ser repetida sem
            # baixar de novo, e o motivo da falha não se perde.
            return await self._fail(intake, f"A análise do edital falhou: {exc.message}")

        return await self._build_proposal(
            intake, auto_apply=auto_apply, actor=actor, context=context
        )

    async def _build_proposal(
        self,
        intake: CompetitionIntake,
        *,
        auto_apply: bool,
        actor: User,
        context: RequestContext,
    ) -> CompetitionIntake:
        """Monta a ficha do concurso a partir dos fatos conferidos no PDF."""
        fatos = (
            (
                await self.session.execute(
                    select(NoticeFact).where(NoticeFact.notice_id == intake.notice_id)
                )
            )
            .scalars()
            .all()
        )

        campos = [
            ProposedField(
                field_path=fato.field_path,
                label=fato.label,
                # A análise guarda o valor em ``{"raw": ...}``.
                value=(fato.value or {}).get("raw"),
                evidence_level=fato.evidence_level,
                quote=fato.quote,
                page_number=fato.page_number,
                target=FIELD_TO_COMPETITION.get(fato.field_path),
                position_target=FIELD_TO_POSITION.get(fato.field_path),
            )
            for fato in fatos
        ]
        campos.sort(key=lambda item: (not item.lands_somewhere, item.field_path))

        intake.proposal = {
            "fields": [item.as_json() for item in campos],
            "applicable": sum(1 for item in campos if item.applicable),
            "needs_typing": sum(1 for item in campos if not item.applicable),
        }
        intake.matches = await self._matches(campos)
        intake.status = IntakeStatus.AWAITING_REVIEW
        intake.detail = None
        await self.audit.record(
            AuditAction.INTAKE_PROPOSED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="competition_intake",
            resource_id=intake.public_id,
            meta={
                "fields": len(campos),
                "applicable": intake.proposal["applicable"],
                "notice": intake.notice.public_id if intake.notice else None,
            },
        )
        await self.session.commit()

        if auto_apply:
            return await self._auto_apply(intake, campos, actor=actor, context=context)
        return intake

    async def _matches(self, campos: list[ProposedField]) -> dict[str, Any]:
        """O que já existe no catálogo e combina com a proposta.

        Serve para não cadastrar o mesmo concurso duas vezes — e para reaproveitar
        órgão e banca que já estão lá, em vez de criar duplicata com nome quase
        igual.
        """
        por_campo = {item.field_path: item for item in campos}

        def valor(path: str) -> str | None:
            campo = por_campo.get(path)
            if campo is None or campo.value is None:
                return None
            return str(campo.value).strip() or None

        achados: dict[str, Any] = {}

        nome_orgao = valor("organization.name")
        if nome_orgao:
            orgao = (
                (
                    await self.session.execute(
                        select(Organization).where(Organization.name.ilike(nome_orgao))
                    )
                )
                .scalars()
                .first()
            )
            achados["organization"] = (
                {"public_id": orgao.public_id, "name": orgao.name} if orgao else None
            )

        nome_banca = valor("exam_board.name")
        if nome_banca:
            banca = (
                (
                    await self.session.execute(
                        select(ExamBoard).where(ExamBoard.name.ilike(nome_banca))
                    )
                )
                .scalars()
                .first()
            )
            achados["exam_board"] = (
                {"public_id": banca.public_id, "name": banca.name} if banca else None
            )

        nome_concurso = valor("competition.name")
        if nome_concurso:
            parecidos = (
                (
                    await self.session.execute(
                        select(Competition)
                        .where(Competition.name.ilike(f"%{nome_concurso[:60]}%"))
                        .limit(5)
                    )
                )
                .scalars()
                .all()
            )
            achados["competitions"] = [
                {"public_id": item.public_id, "name": item.name, "year": item.year}
                for item in parecidos
            ]
        return achados

    # ------------------------------------------------------------------ #
    # 3. Cadastrar — sozinho quando o edital basta, com gente quando não
    # ------------------------------------------------------------------ #
    async def _auto_apply(
        self,
        intake: CompetitionIntake,
        campos: list[ProposedField],
        *,
        actor: User,
        context: RequestContext,
    ) -> CompetitionIntake:
        """Cadastra o concurso sem ninguém digitar nada.

        Usa **só** o que o edital sustenta por citação conferida. O que ele não
        sustenta não é preenchido com palpite: fica em branco e vai nomeado na
        lista de lacunas, que a tela mostra ao lado do "cadastrado".
        """
        from app.services.catalog import CatalogService

        aplicaveis = {item.field_path: item for item in campos if item.applicable}

        nome = _texto(aplicaveis.get("competition.name"))
        if not nome:
            return await self._hold(intake, AutoApplyBlock.NO_COMPETITION_NAME)

        ano = _year_from(aplicaveis)
        if ano is None:
            return await self._hold(intake, AutoApplyBlock.NO_YEAR)

        if await self._duplicate(nome, ano):
            return await self._hold(intake, AutoApplyBlock.DUPLICATE)

        lacunas: list[Gap] = [
            Gap(
                code=GapCode.FIELD_WITHOUT_EVIDENCE,
                label=f"{item.label}: ficou em branco",
                detail=(
                    "a citação não foi localizada no PDF"
                    if item.evidence_level == EvidenceLevel.INFERRED
                    else "o campo não foi encontrado no edital"
                ),
            )
            for item in campos
            if item.lands_somewhere and not item.applicable
        ]

        catalog = CatalogService(self.session)

        # Órgão: reaproveita o que já existe antes de criar outro com nome quase
        # igual — duplicata de órgão espalha o mesmo concurso em duas fichas.
        orgao_existente = (intake.matches or {}).get("organization")
        if orgao_existente:
            organizacao = await catalog.get_organization(orgao_existente["public_id"])
        else:
            nome_orgao = _texto(aplicaveis.get("organization.name"))
            if not nome_orgao:
                return await self._hold(intake, AutoApplyBlock.NO_ORGANIZATION)
            sigla = _derived_short_name(nome_orgao)
            organizacao = await catalog.create_organization(
                {"name": nome_orgao[:200], "short_name": sigla, "sphere": "FEDERAL"},
                actor=actor,
                context=context,
            )
            lacunas.append(
                Gap(
                    code=GapCode.SHORT_NAME_DERIVED,
                    label=f"A sigla do órgão foi derivada do nome: {sigla}",
                    detail=(
                        "o edital não traz campo de sigla, e a coluna exige um valor. "
                        "A esfera entrou como FEDERAL por padrão — confira as duas."
                    ),
                )
            )

        # Banca: só vincula a que já existe. Criar banca a partir do nome escrito
        # num edital encheria o catálogo de variações da mesma banca.
        banca_existente = (intake.matches or {}).get("exam_board")
        banca_id = banca_existente["public_id"] if banca_existente else None
        if banca_id is None and (nome_banca := _texto(aplicaveis.get("exam_board.name"))):
            lacunas.append(
                Gap(
                    code=GapCode.BOARD_NOT_FOUND,
                    label=f"A banca '{nome_banca}' não está no catálogo",
                    detail="cadastre-a em Bancas e vincule o concurso — ele ficou sem banca",
                )
            )

        await self._register(
            intake,
            name=nome,
            year=ano,
            organization=organizacao,
            exam_board_public_id=banca_id,
            competition_fields=_targeted(aplicaveis, FIELD_TO_COMPETITION),
            # Vazio de propósito: no automático os cargos vêm da **lista** que a
            # análise extraiu (``notice_positions``), não dos campos escalares
            # ``position.*`` — que descrevem só o cargo principal.
            position_fields={},
            gaps=lacunas,
            automatic=True,
            actor=actor,
            context=context,
        )
        return intake

    async def apply(
        self,
        intake: CompetitionIntake,
        *,
        name: str,
        year: int,
        organization_public_id: str | None,
        organization_name: str | None,
        organization_short_name: str | None,
        exam_board_public_id: str | None,
        fields: dict[str, Any],
        position: dict[str, Any] | None = None,
        actor: User,
        context: RequestContext,
    ) -> Competition:
        """Cria o concurso com os valores que uma pessoa revisou.

        Este é o caminho de quando o automático parou — nome não conferido, ano
        sem data de origem, possível duplicata — ou de quando alguém quer
        corrigir antes de cadastrar. Os valores vêm **do pedido**, não da
        proposta: a proposta é o rascunho que a pessoa conferiu, e quem assina é
        quem envia.
        """
        from app.services.catalog import CatalogService

        if intake.status != IntakeStatus.AWAITING_REVIEW:
            raise ConflictError(
                "Só é possível aplicar um cadastro que terminou a análise.",
                code="intake_not_ready",
            )
        if not name.strip():
            raise ValidationError("O concurso precisa de nome.", code="intake_name_required")

        catalog = CatalogService(self.session)
        if organization_public_id:
            organizacao = await catalog.get_organization(organization_public_id)
        else:
            if not (organization_name and organization_short_name):
                raise ValidationError(
                    "Escolha o órgão existente ou informe nome e sigla para cadastrá-lo.",
                    code="intake_organization_required",
                )
            organizacao = await catalog.create_organization(
                {
                    "name": organization_name.strip()[:200],
                    "short_name": organization_short_name.strip()[:40],
                    "sphere": fields.get("sphere") or "FEDERAL",
                },
                actor=actor,
                context=context,
            )

        return await self._register(
            intake,
            name=name,
            year=year,
            organization=organizacao,
            exam_board_public_id=exam_board_public_id,
            competition_fields={
                chave: valor
                for chave, valor in fields.items()
                if chave in set(FIELD_TO_COMPETITION.values()) and valor is not None
            },
            position_fields={
                chave: valor
                for chave, valor in (position or {}).items()
                if chave in set(FIELD_TO_POSITION.values()) and valor is not None
            },
            gaps=[],
            automatic=False,
            actor=actor,
            context=context,
        )

    async def _register(
        self,
        intake: CompetitionIntake,
        *,
        name: str,
        year: int,
        organization: Organization,
        exam_board_public_id: str | None,
        competition_fields: dict[str, Any],
        position_fields: dict[str, Any],
        gaps: list[Gap],
        automatic: bool,
        actor: User,
        context: RequestContext,
    ) -> Competition:
        """Grava o concurso, o cargo e a grade. É o único lugar que cria.

        Os dois caminhos — automático e revisado — passam por aqui. Ter um só
        criador é o que garante que o cadastro saia igual nos dois casos: a
        diferença entre eles é **de onde vêm os valores**, não do que acontece
        com eles.
        """
        from app.services.catalog import CatalogService

        catalog = CatalogService(self.session)

        dados: dict[str, Any] = {"name": name.strip()[:200], "year": year}
        for chave, valor in competition_fields.items():
            dados[chave] = _coerced(chave, valor)
        dados["source_url"] = intake.source_url
        # Concurso novo não vai ao ar sozinho: entra na esteira editorial como
        # qualquer outro. O cadastro automático encurta o trabalho, não a
        # conferência que decide o que o candidato vê.
        dados.setdefault("is_published", False)

        competicao = await catalog.create_competition(
            dados,
            organization_public_id=organization.public_id,
            exam_board_public_id=exam_board_public_id,
            actor=actor,
            context=context,
        )

        # Automático cadastra todos os cargos do edital; revisado cadastra o que
        # a pessoa digitou. A grade de cada um sai junto.
        if automatic:
            await self._create_positions(competicao, intake, gaps, actor=actor, context=context)
        else:
            await self._create_positions_from_form(
                competicao, intake, position_fields, gaps, actor=actor, context=context
            )

        # O edital passa a pertencer ao concurso: é o vínculo que faz o
        # orquestrador (e o conteúdo programático já analisado) encontrarem um
        # ao outro.
        if intake.notice is not None:
            intake.notice.competition_id = competicao.id

        intake.competition = competicao
        intake.status = IntakeStatus.APPLIED
        intake.auto_applied = automatic
        intake.gaps = [item.as_json() for item in gaps]
        intake.detail = None
        intake.applied_by_user_id = actor.id
        intake.applied_at = datetime.now(UTC)
        await self.audit.record(
            AuditAction.INTAKE_APPLIED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="competition_intake",
            resource_id=intake.public_id,
            meta={
                "competition": competicao.public_id,
                "fields": sorted(dados),
                "automatic": automatic,
                "gaps": len(gaps),
            },
        )
        await self.session.commit()
        logger.info(
            "intake.applied",
            intake=intake.public_id,
            competition=competicao.public_id,
            automatic=automatic,
            gaps=len(gaps),
        )
        return competicao

    async def _create_positions(
        self,
        competition: Competition,
        intake: CompetitionIntake,
        gaps: list[Gap],
        *,
        actor: User,
        context: RequestContext,
    ) -> list[Position]:
        """Cria **um cargo por cargo do edital**, cada um com a sua grade.

        Edital de concurso raramente tem um cargo só: tem vinte, cada um com
        escolaridade, vagas e salário próprios. Cadastrar um e descartar
        dezenove apagaria da plataforma todo candidato que estuda para os
        outros — que é o oposto do que este cadastro existe para fazer.

        Só entra cargo com **citação conferida**. Cargo que a IA deduziu, ou
        cujo nome o modelo inventou, fica de fora e é nomeado nas lacunas: um
        cargo que não está no edital apareceria na tela do candidato como se
        fosse informação.
        """
        from app.services.catalog import CatalogService

        extraidos = (
            (
                await self.session.execute(
                    select(NoticePosition)
                    .where(NoticePosition.notice_id == intake.notice_id)
                    .order_by(NoticePosition.order_index)
                )
            )
            .scalars()
            .all()
        )

        aplicaveis = [item for item in extraidos if item.evidence_level in APPLICABLE_LEVELS]
        for recusado in extraidos:
            if recusado.evidence_level not in APPLICABLE_LEVELS:
                gaps.append(
                    Gap(
                        code=GapCode.POSITION_WITHOUT_EVIDENCE,
                        label=f"Cargo não cadastrado: {recusado.raw_label}",
                        detail=(
                            "a citação que comprovaria este cargo não foi localizada no PDF. "
                            "Cadastre-o em Concursos depois de conferir no edital."
                        ),
                    )
                )

        if not aplicaveis:
            gaps.append(
                Gap(
                    code=GapCode.POSITION_NOT_FOUND,
                    label="Nenhum cargo foi cadastrado",
                    detail=(
                        "nenhum cargo do edital saiu com citação conferida. Sem cargo não há "
                        "grade de disciplinas — cadastre-o em Concursos."
                    ),
                )
            )
            return []

        catalog = CatalogService(self.session)
        criados: list[Position] = []
        vistos: set[str] = set()
        for extraido in aplicaveis:
            chave = extraido.raw_label.strip().casefold()
            if chave in vistos:
                # Duas linhas com o mesmo nome violariam o índice do cargo no
                # concurso; a segunda fica declarada em vez de estourar.
                gaps.append(
                    Gap(
                        code=GapCode.POSITION_DUPLICATED,
                        label=f"Cargo repetido no edital: {extraido.raw_label}",
                        detail="já havia entrado por outra linha da extração",
                    )
                )
                continue
            vistos.add(chave)

            cargo = await catalog.create_position(
                competition.public_id,
                {
                    "name": extraido.raw_label[:160],
                    **{
                        coluna: valor
                        for coluna, valor in (
                            ("education_level", extraido.education_level),
                            ("salary_cents", extraido.salary_cents),
                            ("vacancies", extraido.vacancies),
                            ("cr_vacancies", extraido.cr_vacancies),
                            ("workload_hours", extraido.workload_hours),
                            ("requirements", extraido.requirements),
                            ("questions_count", extraido.questions_count),
                            ("exam_duration_minutes", extraido.exam_duration_minutes),
                        )
                        if valor is not None
                    },
                },
                actor=actor,
                context=context,
            )
            # O cargo extraído passa a apontar para o cargo do catálogo: é o que
            # permite a uma retificação saber qual cargo mudou.
            extraido.position_id = cargo.id
            criados.append(cargo)
            await self._build_grade(cargo, intake, gaps, position_label=extraido.raw_label)

        return criados

    async def _create_positions_from_form(
        self,
        competition: Competition,
        intake: CompetitionIntake,
        position_fields: dict[str, Any],
        gaps: list[Gap],
        *,
        actor: User,
        context: RequestContext,
    ) -> list[Position]:
        """Cria o cargo que uma pessoa digitou no formulário de revisão.

        O caminho revisado cadastra **um** cargo — o que está no formulário —,
        porque é o que a pessoa conferiu. Os outros cargos do edital continuam
        na ficha do edital e podem ser cadastrados em Concursos, ou pelo
        caminho automático.
        """
        from app.services.catalog import CatalogService

        nome = str(position_fields.get("name") or "").strip()
        if not nome:
            gaps.append(
                Gap(
                    code=GapCode.POSITION_NOT_FOUND,
                    label="Nenhum cargo foi cadastrado",
                    detail=(
                        "o formulário veio sem nome de cargo. Sem cargo não há grade de "
                        "disciplinas — cadastre-o em Concursos."
                    ),
                )
            )
            return []

        dados: dict[str, Any] = {"name": nome[:160]}
        for chave, valor in position_fields.items():
            if chave != "name" and valor is not None:
                dados[chave] = _coerced_position(chave, valor)

        cargo = await CatalogService(self.session).create_position(
            competition.public_id, dados, actor=actor, context=context
        )
        await self._build_grade(cargo, intake, gaps, position_label=nome)
        return [cargo]

    async def _build_grade(
        self,
        position: Position,
        intake: CompetitionIntake,
        gaps: list[Gap],
        *,
        position_label: str,
    ) -> None:
        """Monta a grade de um cargo a partir das disciplinas do edital.

        A disciplina do edital diz de qual cargo ela é (``position_label``).
        Quando não diz, a grade é comum a todos os cargos — o caso mais
        frequente — e vale para este também. Então as disciplinas deste cargo
        são: as que o nomeiam, mais as comuns.

        O peso e o número de questões vêm do edital, conferidos pela mesma regra
        de citação dos outros campos. O **nome** da disciplina precisa casar com
        o catálogo, e aqui só casamento de nome idêntico vale: a disciplina
        errada na grade manda o aluno estudar a coisa errada achando que está no
        lugar certo. Disciplina sem par exato no catálogo não entra — e é
        nomeada na lista de lacunas, uma por uma.
        """
        todas = (
            (
                await self.session.execute(
                    select(NoticeSubject)
                    .where(NoticeSubject.notice_id == intake.notice_id)
                    .order_by(NoticeSubject.order_index)
                )
            )
            .scalars()
            .all()
        )
        alvo = position_label.strip().casefold()
        proprias = [
            item
            for item in todas
            if item.position_label and item.position_label.strip().casefold() == alvo
        ]
        comuns = [item for item in todas if not item.position_label]
        disciplinas_edital = proprias + comuns

        if not disciplinas_edital:
            gaps.append(
                Gap(
                    code=GapCode.GRADE_EMPTY,
                    label=f"O cargo '{position.name}' ficou sem grade de disciplinas",
                    detail=(
                        "a análise não extraiu nenhuma disciplina para este cargo neste edital"
                    ),
                )
            )
            return

        disciplinas_catalogo = (
            (await self.session.execute(select(Subject).where(Subject.is_active.is_(True))))
            .scalars()
            .all()
        )
        catalogo = [
            CatalogEntry(public_id=item.public_id, name=item.name) for item in disciplinas_catalogo
        ]
        por_public_id = {item.public_id: item for item in disciplinas_catalogo}

        vinculadas = 0
        usadas: set[int] = set()
        for disciplina in disciplinas_edital:
            melhor = suggest(disciplina.raw_label, catalogo).best
            if melhor is None or melhor.reason not in AUTO_LINK_REASONS:
                gaps.append(
                    Gap(
                        code=GapCode.SUBJECT_WITHOUT_CATALOG,
                        label=f"Disciplina fora da grade: {disciplina.raw_label}",
                        detail=(
                            "não existe disciplina com este nome no catálogo. "
                            + (
                                f"O mais próximo é '{melhor.entry.name}' ({melhor.reason_label}), "
                                "mas parecido não basta para entrar sozinho."
                                if melhor is not None
                                else "O catálogo não tem nada parecido."
                            )
                        ),
                    )
                )
                continue

            canonica = por_public_id[melhor.entry.public_id]
            if canonica.id in usadas:
                # Duas linhas do edital casando na mesma disciplina violariam a
                # unicidade da grade; a segunda fica declarada.
                gaps.append(
                    Gap(
                        code=GapCode.SUBJECT_WITHOUT_CATALOG,
                        label=f"Disciplina repetida na grade: {disciplina.raw_label}",
                        detail=f"'{canonica.name}' já havia entrado por outra linha do edital",
                    )
                )
                continue

            usadas.add(canonica.id)
            self.session.add(
                PositionSubject(
                    position_id=position.id,
                    subject_id=canonica.id,
                    weight=disciplina.weight if disciplina.weight is not None else Decimal("1.00"),
                    questions_count=disciplina.questions_count,
                    source="NOTICE",
                    extra={
                        "notice_subject": disciplina.public_id,
                        "raw_label": disciplina.raw_label,
                        "evidence_level": disciplina.evidence_level,
                        "page_number": disciplina.page_number,
                    },
                )
            )
            vinculadas += 1

        await self.session.flush()
        if vinculadas == 0:
            gaps.append(
                Gap(
                    code=GapCode.GRADE_EMPTY,
                    label=f"O cargo '{position.name}' ficou sem grade de disciplinas",
                    detail=(
                        f"nenhuma das {len(disciplinas_edital)} disciplinas do edital tem nome "
                        "idêntico a uma disciplina do catálogo"
                    ),
                )
            )

    async def _duplicate(self, name: str, year: int) -> Competition | None:
        """O mesmo concurso, mesmo ano, já cadastrado."""
        return (
            (
                await self.session.execute(
                    select(Competition).where(
                        Competition.name.ilike(name.strip()), Competition.year == year
                    )
                )
            )
            .scalars()
            .first()
        )

    async def _hold(self, intake: CompetitionIntake, reason: str) -> CompetitionIntake:
        """Segura o cadastro automático e devolve a decisão, com o motivo escrito.

        Não é falha: a ficha está montada e o formulário de revisão continua
        ali. É o automático dizendo o que não conseguiu decidir sozinho.
        """
        intake.detail = BLOCK_LABEL[reason]
        intake.gaps = [Gap(code=reason, label=BLOCK_LABEL[reason]).as_json()]
        await self.session.commit()
        logger.info("intake.auto_apply_held", intake=intake.public_id, reason=reason)
        return intake

    async def reject(
        self, intake: CompetitionIntake, *, reason: str, actor: User, context: RequestContext
    ) -> CompetitionIntake:
        """Descarta a proposta. O motivo é obrigatório, como nas melhorias."""
        if not reason.strip():
            raise ValidationError(
                "Diga por que a proposta foi descartada.", code="intake_reason_required"
            )
        intake.status = IntakeStatus.REJECTED
        intake.detail = reason.strip()[:1000]
        await self.audit.record(
            AuditAction.INTAKE_REJECTED,
            actor=actor,
            actor_ip=context.ip_address,
            resource_type="competition_intake",
            resource_id=intake.public_id,
            meta={"reason": intake.detail},
        )
        await self.session.commit()
        return intake

    # ------------------------------------------------------------------ #
    async def _fail(self, intake: CompetitionIntake, detail: str) -> CompetitionIntake:
        intake.status = IntakeStatus.FAILED
        intake.detail = detail[:1000]
        await self.session.commit()
        logger.warning("intake.failed", intake=intake.public_id, detail=detail[:200])
        return intake


def _document_from(recurso: FetchedResource) -> SourceDocument:
    """O que voltou da rede, no formato que o resto do serviço conhece."""
    return SourceDocument(
        content=recurso.content,
        filename=_filename_from(recurso.final_url),
        declared_mime=recurso.content_type.split(";")[0].strip() or None,
        source_url=recurso.final_url[:500],
        title=_title_from(_filename_from(recurso.final_url)),
    )


def _texto(campo: ProposedField | None) -> str | None:
    """O valor do campo como texto limpo, ou nada."""
    if campo is None or campo.value is None:
        return None
    return str(campo.value).strip() or None


def _targeted(aplicaveis: dict[str, ProposedField], mapa: dict[str, str]) -> dict[str, Any]:
    """Os valores aplicáveis, já na chave da coluna de destino."""
    return {
        destino: aplicaveis[origem].value
        for origem, destino in mapa.items()
        if origem in aplicaveis
    }


def _year_from(aplicaveis: dict[str, ProposedField]) -> int | None:
    """O ano do concurso, derivado da data oficial mais específica que houver."""
    for path in YEAR_SOURCES:
        bruto = _texto(aplicaveis.get(path))
        if not bruto:
            continue
        try:
            return date.fromisoformat(bruto[:10]).year
        except ValueError:
            continue
    return None


def _derived_short_name(name: str) -> str:
    """Sigla do órgão, derivada das iniciais do nome.

    O edital não tem campo de sigla e a coluna exige um valor. Isto é palpite de
    **rótulo** — não de fato do edital —, e vai declarado como lacuna para
    alguém conferir. "Polícia Civil do Distrito Federal" sai "PCDF".
    """
    palavras = [parte for parte in re.split(r"[\s/–-]+", name) if parte]
    # Preposições ("do", "de", "da") não entram na sigla; nomes curtos em
    # maiúscula ("DF") entram.
    iniciais = "".join(parte[0].upper() for parte in palavras if len(parte) > 2 or parte.isupper())
    if 2 <= len(iniciais) <= 40:
        return iniciais
    return name.strip()[:40] or "ORG"


def _coerced_position(target: str, value: Any) -> Any:
    """Converte o que vai para o cargo: tudo que não é nome é número."""
    if target == "education_level":
        return str(value)[:20]
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"O campo '{target}' do cargo precisa ser um número.",
            code="intake_invalid_number",
        ) from exc


def _filename_from(url: str) -> str:
    from urllib.parse import urlparse

    nome = urlparse(url).path.rsplit("/", 1)[-1] or "edital.pdf"
    return nome[:255]


def _title_from(filename: str) -> str:
    """Título do edital a partir do nome do arquivo.

    É só rótulo de tela: o que vale como dado do concurso sai da análise, com
    citação. Por isso tratar "edital-de-abertura-01-2026.pdf" como
    "edital de abertura 01 2026" não afirma nada sobre o documento.
    """
    nome = filename.rsplit("/", 1)[-1].removesuffix(".pdf").replace("-", " ").replace("_", " ")
    return (nome.strip() or "Edital")[:255]


def _coerced(target: str, value: Any) -> Any:
    """Converte o que vem do formulário para o tipo da coluna.

    Data chega como texto ISO; o resto chega como número. Conversão errada aqui
    viraria exceção de banco no meio do cadastro, e a tela não saberia dizer
    qual campo estava torto.
    """
    if target in {"registration_start", "registration_end", "exam_date"}:
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError as exc:
            raise ValidationError(
                f"A data informada em '{target}' não está no formato AAAA-MM-DD.",
                code="intake_invalid_date",
            ) from exc
    if target in {"vacancies_total", "salary_max_cents"}:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"O campo '{target}' precisa ser um número.", code="intake_invalid_number"
            ) from exc
    return value
