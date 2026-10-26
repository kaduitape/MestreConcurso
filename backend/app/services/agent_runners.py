"""Os agentes que de fato rodam hoje.

O catálogo em ``app.domain.agents`` declara os oito do pedido. Aqui ficam só os
que têm implementação de verdade — e isso é deliberado: registrar um agente que
não faz nada o deixaria **verde** na tela de acompanhamento, que é pior do que
deixá-lo pulado. Pulado traz o motivo escrito; verde mente.

Os oito registrados reutilizam serviços que já estavam em produção:

* **Analista de editais** → o pipeline de análise, com suas sete etapas e a
  conferência de cada citação no PDF.
* **Inteligência estatística** → o cálculo de incidência da banca, que já
  separa frequência observada de estimativa e carrega o tamanho da amostra.
* **Tutor adaptativo** → o Priority Score, que reúne os sinais reais do
  candidato e diz o que faltou quando um sinal não existe.
* **Auditor de qualidade** → o portão de regras determinísticas, que varre o
  conteúdo publicado do concurso e declara o próprio alcance.
* **Professor** → os planos de geração em massa **já confirmados por uma
  pessoa**, nos tipos dele: aula e mapa mental. O agente executa; quem autoriza
  o gasto é gente.
* **Memorização** → os mesmos planos, no tipo baralho de flashcards, montando
  rascunho a partir de aula **publicada**. Sem material conferido ele não gera,
  e diz isso no lugar de gerar do rascunho.
* **Mestre de batalhas** → os mesmos planos, no tipo questão: escreve questões
  inéditas em rascunho, com o gabarito conferido na origem, sem banca e sem ano.

O orquestrador não refaz o trabalho deles. Ele os chama na ordem certa e
registra o que aconteceu.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.agents import AgentKey
from app.models.agent_run import AgentRun
from app.models.catalog import Competition
from app.models.notice import Notice, NoticeKind
from app.models.study import StudyPlan, StudyPlanStatus
from app.models.user import User
from app.services.auth import RequestContext
from app.services.orchestrator import AgentOutcome, registry


async def _competition(session: AsyncSession, run: AgentRun) -> Competition | None:
    if run.competition_id is None:
        return None
    return (
        await session.execute(select(Competition).where(Competition.id == run.competition_id))
    ).scalar_one_or_none()


async def run_notice_analyst(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Roda a análise do edital principal do concurso."""
    from app.services.notice_analysis import NoticeAnalysisService

    notices = (
        (
            await session.execute(
                select(Notice)
                .where(Notice.competition_id == run.competition_id)
                .order_by(Notice.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    principal = next((item for item in notices if item.kind == NoticeKind.MAIN), None)
    if principal is None:
        # Sem edital não há o que analisar, e isso não é falha: é ausência de
        # insumo. O motivo escrito evita que alguém procure um erro que não há.
        return AgentOutcome(
            detail="O concurso ainda não tem edital principal cadastrado.", skipped=True
        )
    if not principal.files:
        return AgentOutcome(
            detail="O edital está cadastrado, mas sem arquivo PDF enviado.", skipped=True
        )

    outcome = await NoticeAnalysisService(session).analyze(
        principal, actor=None, context=RequestContext()
    )
    return AgentOutcome(
        detail=(
            f"Edital analisado: {outcome.positions_created} cargo(s), "
            f"{outcome.subjects_created} disciplinas, "
            f"{outcome.facts_created} dados extraídos e "
            f"{outcome.events_created} datas identificadas."
        ),
        result={
            "notice": outcome.notice_public_id,
            "positions_created": outcome.positions_created,
            "subjects_created": outcome.subjects_created,
            "facts_created": outcome.facts_created,
            "events_created": outcome.events_created,
            "cached": outcome.cached,
        },
    )


async def run_statistics(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Recalcula a incidência da banca do concurso."""
    from app.services.intelligence import IntelligenceService

    competition = await _competition(session, run)
    if competition is None or competition.exam_board is None:
        return AgentOutcome(
            detail="O concurso não tem banca definida, então não há provas para analisar.",
            skipped=True,
        )

    resultado = await IntelligenceService(session).recompute_board(competition.exam_board.slug)

    if resultado.incidence_blocked:
        # O serviço já diz por que não deu — repassar isso é melhor que
        # inventar um sucesso vazio.
        return AgentOutcome(detail=resultado.incidence_blocked, skipped=True)

    return AgentOutcome(
        detail=(
            f"{resultado.incidence_rows} linhas de incidência a partir de "
            f"{resultado.questions_sampled} questões da banca."
        ),
        result={
            "board": resultado.board_slug,
            "questions_sampled": resultado.questions_sampled,
            "incidence_rows": resultado.incidence_rows,
            "profile_metrics": resultado.profile_metrics,
        },
    )


async def run_tutor(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Recalcula a ordem de estudo de quem está estudando para este concurso.

    Nenhuma IA entra aqui: o Priority Score soma sinais reais do candidato
    (desempenho, incidência, progresso) e marca como ausente o sinal que não
    existe. Um número inventado seria pior que nenhum.
    """
    from app.services.priority import PriorityService

    if run.competition_id is None:
        return AgentOutcome(detail="A execução não está ligada a um concurso.", skipped=True)

    candidatos = list(
        (
            await session.execute(
                select(User)
                .join(StudyPlan, StudyPlan.user_id == User.id)
                .where(
                    StudyPlan.competition_id == run.competition_id,
                    StudyPlan.status == StudyPlanStatus.ACTIVE,
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    if not candidatos:
        # Ausência de candidato não é falha: é ausência de insumo. O motivo
        # escrito evita que alguém procure um erro que não há.
        return AgentOutcome(
            detail=(
                "Nenhum candidato tem plano de estudo ativo para este concurso, "
                "então não há prioridade para recalcular."
            ),
            skipped=True,
        )

    service = PriorityService(session)
    linhas = 0
    sem_sinal = 0
    for candidato in candidatos:
        report = await service.compute(candidato)
        linhas += len(report.scores)
        if not report.scores:
            sem_sinal += 1

    detalhe = f"{len(candidatos)} candidatos recalculados e {linhas} linhas de ordem de estudo."
    if sem_sinal:
        detalhe += (
            f" {sem_sinal} ficaram sem nenhuma linha por falta de sinal — "
            "o relatório de cada candidato diz o que faltou."
        )
    return AgentOutcome(
        detail=detalhe,
        result={
            "candidates": len(candidatos),
            "priority_rows": linhas,
            "candidates_without_signal": sem_sinal,
        },
    )


async def run_auditor(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Varre o conteúdo publicado do concurso com as regras do auditor.

    Nenhuma IA: as regras são determinísticas e a conta aparece. Um auditor que
    julga por modelo de linguagem não repete o mesmo veredito sobre a mesma
    questão, e um portão que muda de ideia não é portão.
    """
    from app.services.content_audit import ContentAuditService

    if run.competition_id is None:
        return AgentOutcome(detail="A execução não está ligada a um concurso.", skipped=True)

    resultado = await ContentAuditService(session).sweep_competition(run.competition_id)

    if resultado.audited == 0:
        detalhe = "Não há conteúdo publicado ligado a este concurso para conferir."
        if resultado.notes:
            detalhe = f"{detalhe} {' '.join(resultado.notes)}"
        return AgentOutcome(detail=detalhe, skipped=True)

    detalhe = (
        f"{resultado.audited} conteúdos conferidos: {resultado.blocked} com bloqueio, "
        f"{resultado.warned} com aviso e {resultado.clean} limpos."
    )
    if resultado.not_checked:
        # O que não deu para conferir é parte do resultado, não rodapé.
        detalhe += f" {resultado.not_checked} itens ficaram sem conferência."
    if resultado.notes:
        detalhe += " " + " ".join(resultado.notes)

    return AgentOutcome(
        detail=detalhe,
        result={
            "audited": resultado.audited,
            "blocked": resultado.blocked,
            "warned": resultado.warned,
            "clean": resultado.clean,
            "not_checked": resultado.not_checked,
            "notes": list(resultado.notes),
        },
    )


@dataclass(frozen=True, slots=True)
class PlanPass:
    """O que uma passada sobre os planos confirmados produziu."""

    generated: int = 0
    reused: int = 0
    failed: int = 0
    blocked: int = 0
    remaining: int = 0
    no_source: int = 0
    plans: int = 0


async def _run_confirmed_plans(
    session: AsyncSession, run: AgentRun, *, kinds: tuple[str, ...]
) -> PlanPass:
    """Roda os planos confirmados do concurso, só nos tipos pedidos.

    O filtro por tipo é o que mantém a fronteira entre os agentes honesta: o
    Professor executa aula e mapa mental, a Memorização executa baralho. Sem
    ele, o primeiro a rodar levaria o crédito pelo trabalho do outro na tela de
    acompanhamento.
    """
    from app.domain.generation import PlanStatus
    from app.models.generation import GenerationItem, GenerationPlan
    from app.models.user import User as UserModel
    from app.services.auth import RequestContext
    from app.services.generation import GenerationService

    planos = list(
        (
            await session.execute(
                select(GenerationPlan)
                .where(
                    GenerationPlan.competition_id == run.competition_id,
                    GenerationPlan.status.in_([PlanStatus.CONFIRMED, PlanStatus.RUNNING]),
                    GenerationPlan.id.in_(
                        select(GenerationItem.plan_id).where(GenerationItem.kind.in_(kinds))
                    ),
                )
                .order_by(GenerationPlan.id)
            )
        )
        .scalars()
        .all()
    )

    service = GenerationService(session)
    resultado = PlanPass(plans=len(planos))
    for plano in planos:
        actor = (
            await session.execute(
                select(UserModel).where(UserModel.id == plano.confirmed_by_user_id)
            )
        ).scalar_one_or_none()
        if actor is None:
            continue
        passada = await service.run(plano, actor, RequestContext(), kinds=kinds)
        resultado = PlanPass(
            generated=resultado.generated + passada.generated,
            reused=resultado.reused + passada.reused,
            failed=resultado.failed + passada.failed,
            blocked=resultado.blocked + passada.blocked,
            remaining=resultado.remaining + passada.remaining,
            no_source=resultado.no_source + passada.no_source,
            plans=resultado.plans,
        )
    return resultado


async def run_teacher(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Executa os planos de geração confirmados deste concurso: aulas e mapas.

    O agente **não confirma plano**. Montar o plano mostra a estimativa, e
    disparar centenas de chamadas de IA é decisão de uma pessoa — se o agente
    pudesse confirmar sozinho, a confirmação não valeria nada.
    """
    from app.domain.generation import GenerationKind

    if run.competition_id is None:
        return AgentOutcome(detail="A execução não está ligada a um concurso.", skipped=True)

    tipos = (GenerationKind.TRAINING_LESSON, GenerationKind.MIND_MAP)
    passada = await _run_confirmed_plans(session, run, kinds=tipos)
    if passada.plans == 0:
        return AgentOutcome(
            detail=(
                "Não há plano de geração confirmado com aula ou mapa mental para "
                "este concurso. Monte o plano no painel, confira a estimativa e "
                "confirme — o agente executa, mas não autoriza o gasto."
            ),
            skipped=True,
        )

    detalhe = (
        f"{passada.generated} rascunhos gerados, {passada.reused} tópicos reaproveitados "
        f"e {passada.failed} falhas."
    )
    if passada.blocked:
        detalhe += f" {passada.blocked} itens barrados pelo teto de gasto."
    if passada.remaining:
        detalhe += f" {passada.remaining} itens continuam na fila para a próxima passada."
    detalhe += " Nada foi publicado: rascunho de IA espera conferência humana."

    return AgentOutcome(
        detail=detalhe,
        result={
            "generated": passada.generated,
            "reused": passada.reused,
            "failed": passada.failed,
            "blocked": passada.blocked,
            "remaining": passada.remaining,
        },
    )


async def run_memory(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Monta os baralhos oficiais dos tópicos, em rascunho, a partir de aula publicada.

    Duas regras do desenho aparecem no resultado deste agente, e nenhuma das
    duas é rodapé:

    *Cartão não nasce de rascunho.* O baralho é gerado do texto de uma aula
    **publicada** — material que uma pessoa já conferiu. Tópico cuja aula ainda
    é rascunho fica sem baralho, com o motivo escrito, e não vira falha.

    *Nenhum baralho é publicado aqui.* Ele fica em rascunho, invisível para
    candidato, esperando curadoria. Publicar é ação de pessoa, e passa pelo
    portão da Fase 3.
    """
    from app.domain.generation import GenerationKind

    if run.competition_id is None:
        return AgentOutcome(detail="A execução não está ligada a um concurso.", skipped=True)

    passada = await _run_confirmed_plans(session, run, kinds=(GenerationKind.FLASHCARD_DECK,))
    if passada.plans == 0:
        return AgentOutcome(
            detail=(
                "Não há plano de geração confirmado com baralho de flashcards para "
                "este concurso. Inclua o tipo no plano, confira a estimativa e "
                "confirme — o agente executa, mas não autoriza o gasto."
            ),
            skipped=True,
        )

    detalhe = (
        f"{passada.generated} baralho(s) montado(s) em rascunho, "
        f"{passada.reused} tópico(s) que já tinham baralho e {passada.failed} falha(s)."
    )
    if passada.no_source:
        # Sem aula publicada não há cartão, e isto é resultado, não nota de pé
        # de página: é o que a curadoria precisa resolver para o agente render.
        detalhe += (
            f" {passada.no_source} tópico(s) sem material conferido: o cartão oficial "
            "não nasce de rascunho de aula."
        )
    if passada.blocked:
        detalhe += f" {passada.blocked} itens barrados pelo teto de gasto."
    if passada.remaining:
        detalhe += f" {passada.remaining} itens continuam na fila para a próxima passada."
    detalhe += " Nenhum baralho foi publicado: rascunho espera conferência humana."

    return AgentOutcome(
        detail=detalhe,
        result={
            "generated": passada.generated,
            "reused": passada.reused,
            "failed": passada.failed,
            "blocked": passada.blocked,
            "remaining": passada.remaining,
            "no_source": passada.no_source,
        },
    )


async def run_battle_master(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Escreve questões inéditas dos tópicos, em rascunho, a partir de aula publicada.

    Três coisas aparecem no resultado deste agente, e nenhuma é rodapé:

    *Questão não nasce de rascunho.* A fonte é aula **publicada** — material que
    uma pessoa já conferiu. Tópico sem aula publicada fica sem questão, com o
    motivo escrito, e isso não é falha.

    *O que não passou na conferência é dito.* Rascunho sem gabarito único, com
    citação que não existe no material ou que se apresenta como questão de banca
    é descartado na origem, com o motivo contado por tipo.

    *Nenhuma questão é publicada aqui.* Ela nasce ``DRAFT``, marcada como gerada
    por IA, sem banca e sem ano. Publicar é ação de pessoa, e passa pelo portão
    da Fase 3, que cobra a conferência humana.
    """
    from app.domain.generation import GenerationKind

    if run.competition_id is None:
        return AgentOutcome(detail="A execução não está ligada a um concurso.", skipped=True)

    passada = await _run_confirmed_plans(session, run, kinds=(GenerationKind.QUESTION_SET,))
    if passada.plans == 0:
        return AgentOutcome(
            detail=(
                "Não há plano de geração confirmado com questões para este concurso. "
                "Inclua o tipo no plano, confira a estimativa e confirme — o agente "
                "executa, mas não autoriza o gasto."
            ),
            skipped=True,
        )

    detalhe = (
        f"{passada.generated} tópico(s) com questões geradas em rascunho, "
        f"{passada.reused} tópico(s) que já tinham questão suficiente no banco e "
        f"{passada.failed} falha(s)."
    )
    if passada.no_source:
        detalhe += (
            f" {passada.no_source} tópico(s) sem material conferido ou sem questão "
            "aprovada na conferência de origem."
        )
    if passada.blocked:
        detalhe += f" {passada.blocked} itens barrados pelo teto de gasto."
    if passada.remaining:
        detalhe += f" {passada.remaining} itens continuam na fila para a próxima passada."
    detalhe += (
        " Nada foi publicado: questão gerada espera conferência humana, e nenhuma "
        "delas se apresenta como questão de banca."
    )

    return AgentOutcome(
        detail=detalhe,
        result={
            "generated": passada.generated,
            "reused": passada.reused,
            "failed": passada.failed,
            "blocked": passada.blocked,
            "remaining": passada.remaining,
            "no_source": passada.no_source,
        },
    )


async def run_improvements(session: AsyncSession, run: AgentRun) -> AgentOutcome:
    """Varre os registros da própria plataforma e grava achados para revisão.

    Nenhuma IA, nenhuma escrita fora das duas tabelas de achados e nenhuma ação
    aplicada: o analista propõe, uma pessoa decide. Quando a credencial restrita
    está configurada, a varredura roda nela — e o detalhe do passo diz qual das
    duas garantias está valendo, porque "isolado" e "isolado só no código" não
    são a mesma coisa.
    """
    from app.services.improvements import ImprovementService, IsolationMode

    relatorio = await ImprovementService(session).run()

    sem_amostra = [item for item in relatorio.detectors if item.status == "NOT_ENOUGH_DATA"]
    detalhe = (
        f"{relatorio.opened} achado(s) novo(s), {relatorio.updated} atualizado(s), "
        f"{relatorio.resolved} fechado(s) por terem deixado de aparecer e "
        f"{relatorio.reopened} reaberto(s)."
    )
    if sem_amostra:
        # Detector sem amostra é parte do resultado, não rodapé: ele não fechou
        # nenhum achado antigo, e isso precisa estar dito.
        detalhe += (
            f" {len(sem_amostra)} detector(es) não rodaram por falta de amostra e "
            "não fecharam nada."
        )
    detalhe += (
        " Credencial restrita de banco em uso."
        if relatorio.isolation == IsolationMode.DB_READONLY
        else " Sem credencial restrita de banco: a garantia de leitura é só do código."
    )

    return AgentOutcome(
        detail=detalhe,
        result={
            "isolation": relatorio.isolation,
            "opened": relatorio.opened,
            "updated": relatorio.updated,
            "resolved": relatorio.resolved,
            "reopened": relatorio.reopened,
            "muted": relatorio.muted,
            "detectors": [
                {
                    "key": item.key,
                    "status": item.status,
                    "found": item.found,
                    "detail": item.detail,
                }
                for item in relatorio.detectors
            ],
        },
    )


def register_default_agents() -> None:
    """Liga as chaves do catálogo às implementações reais.

    Os oito do pedido, agora todos com implementação de verdade. O catálogo e o
    registro precisam continuar contando a mesma história: um agente declarado
    como construído sem implementação registrada seria pulado dizendo "ainda não
    foi implementado", contradizendo a própria ficha dele na tela.

    Catálogo e registro precisam contar a mesma história. Um agente declarado
    como construído sem implementação registrada seria pulado dizendo "ainda
    não foi implementado", contradizendo a própria ficha dele na tela.
    """
    registry.register(AgentKey.NOTICE_ANALYST, run_notice_analyst)
    registry.register(AgentKey.STATISTICS, run_statistics)
    registry.register(AgentKey.TUTOR, run_tutor)
    registry.register(AgentKey.AUDITOR, run_auditor)
    registry.register(AgentKey.TEACHER, run_teacher)
    registry.register(AgentKey.MEMORY, run_memory)
    registry.register(AgentKey.BATTLE_MASTER, run_battle_master)
    registry.register(AgentKey.IMPROVEMENTS, run_improvements)


register_default_agents()
