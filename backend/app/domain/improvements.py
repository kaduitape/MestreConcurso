"""Analista de melhorias — os detectores, e o que cada um pode afirmar.

Desenho aprovado em [docs/36-agente-8-desenho.md]: analista **somente-leitura**,
detectores determinísticos, achado com evidência para uma pessoa decidir. A IA
não participa deste módulo — não participa de nenhum, nesta primeira parte.

Quatro regras governam o que está aqui, e todas as quatro são sobre o que um
analista **não** pode dizer:

*Sem amostra, sem achado.* Cada detector declara janela e amostra mínima. Abaixo
disso ele devolve ``NOT_ENOUGH_DATA`` com o que falta, e o painel mostra isso —
é o mesmo critério do ``NOT_CHECKED`` do auditor e do ``NOT_EVALUATED`` do
roteador. Um analista que opina sobre três chamadas de IA é pior que um analista
calado.

*Economia só com número medido.* Nenhum achado afirma economia que não tenha
saído de ``ai_usage``. Quando não há custo medido, o campo fica vazio e o texto
diz que não dá para estimar.

*Nada aqui aplica nada.* O módulo é puro: devolve achados. Quem grava é o
serviço, e o que ele grava é proposta — nunca ação.

*O achado aponta o destino.* Problema que tem tela para resolver vai para o
administrador; problema que precisa de código vai para desenvolvimento, descrito
em texto. Nenhum achado propõe patch: o desenho aprovado é a opção A, sem
acesso ao repositório.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

#: Dias que um achado recusado passa sem voltar pela mesma impressão digital.
#: Recusar e ser ignorado faria o administrador parar de recusar. Fica nos
#: limiares de cada detector, editável no banco como os outros.
DEFAULT_MUTE_DAYS = 90


class DetectorKey(StrEnum):
    """Os quatro detectores do primeiro corte."""

    SUSPECT_ANSWER_KEY = "SUSPECT_ANSWER_KEY"
    TOPIC_WITHOUT_MATERIAL = "TOPIC_WITHOUT_MATERIAL"
    MODEL_ERROR_RATE = "MODEL_ERROR_RATE"
    ROUTE_INERT = "ROUTE_INERT"


class Severity(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Destination(StrEnum):
    #: Existe tela na plataforma para resolver.
    ADMIN = "ADMIN"
    #: Precisa de código. O achado descreve a mudança; não produz patch.
    DEVELOPMENT = "DEVELOPMENT"


class DetectorStatus(StrEnum):
    FOUND = "FOUND"
    #: Rodou, tinha amostra e não achou nada.
    CLEAN = "CLEAN"
    #: Não rodou por falta de amostra — e diz o que falta.
    NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"
    DISABLED = "DISABLED"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    #: Fechado porque o detector **deixou de achar**, não porque alguém disse.
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class DetectorSpec:
    key: str
    label: str
    description: str
    destination: str
    #: O que o detector pode afirmar, escrito para aparecer no painel.
    scope: str
    #: Limiares padrão. Os vigentes moram no banco: mudar um é ``UPDATE``.
    defaults: dict[str, int] = field(default_factory=dict)


DETECTORS: tuple[DetectorSpec, ...] = (
    DetectorSpec(
        key=DetectorKey.SUSPECT_ANSWER_KEY,
        label="Gabarito suspeito",
        description=(
            "Questão com amostra suficiente e acerto muito abaixo do acaso. Uma questão "
            "de quatro alternativas que quase ninguém acerta não é difícil: o gabarito "
            "provavelmente está trocado."
        ),
        destination=Destination.ADMIN,
        scope=(
            "Compara o acerto real com o acerto por acaso (1 ÷ número de alternativas). "
            "Não lê o enunciado nem julga o mérito da questão."
        ),
        defaults={"min_attempts": 30, "chance_divisor": 2, "mute_days": DEFAULT_MUTE_DAYS},
    ),
    DetectorSpec(
        key=DetectorKey.TOPIC_WITHOUT_MATERIAL,
        label="Tópico do edital sem material",
        description=(
            "Tópico cobrado no edital, já vinculado ao catálogo, sem nenhuma questão, "
            "aula ou mapa mental cadastrados. Ordenado pelo peso na prova."
        ),
        destination=Destination.ADMIN,
        scope=(
            "Só conta tópico com vínculo. Tópico do edital sem vínculo é outra lacuna, "
            "e aparece na árvore do edital como NOT_LINKED."
        ),
        defaults={"min_topics": 1, "top_topics": 10, "mute_days": DEFAULT_MUTE_DAYS},
    ),
    DetectorSpec(
        key=DetectorKey.MODEL_ERROR_RATE,
        label="Modelo errando acima do limiar",
        description=(
            "Funcionalidade cujo modelo falha acima do limiar na janela, com o custo "
            "medido das chamadas que falharam."
        ),
        destination=Destination.ADMIN,
        scope=(
            "Conta o que ficou registrado em ai_usage. Chamada que nunca chegou ao "
            "provedor não aparece ali e não entra na conta."
        ),
        defaults={
            "window_days": 7,
            "min_calls": 20,
            "error_rate_percent": 10,
            "mute_days": DEFAULT_MUTE_DAYS,
        },
    ),
    DetectorSpec(
        key=DetectorKey.ROUTE_INERT,
        label="Regra de roteamento inerte",
        description=(
            "Regra de roteamento ligada que nunca se aplicou na janela — ou porque a "
            "condição nunca valeu, ou porque a funcionalidade não informa o sinal de "
            "que ela depende."
        ),
        destination=Destination.ADMIN,
        scope=(
            "Olha as decisões de roteamento mais recentes, até o teto de leitura "
            "declarado no achado. Regra criada depois delas não é avaliada."
        ),
        defaults={
            "window_days": 30,
            "min_decisions": 50,
            "max_rows": 2000,
            "mute_days": DEFAULT_MUTE_DAYS,
        },
    ),
)

DETECTOR_BY_KEY: dict[str, DetectorSpec] = {item.key: item for item in DETECTORS}


# --------------------------------------------------------------------------- #
# Achado
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Finding:
    """Um achado pronto para ser gravado.

    ``evidence`` carrega os números que o produziram, e é o que a tela mostra
    junto do texto. Achado sem evidência não existe neste módulo.
    """

    detector: str
    severity: str
    destination: str
    #: Identifica o achado ao longo do tempo: a segunda passada atualiza, não
    #: duplica. Alvo + detector, nada de data nem de texto.
    fingerprint: str
    title: str
    detail: str
    #: A mudança proposta, em texto. Nunca um patch — decisão D1, opção A.
    proposal: str
    evidence: dict[str, object] = field(default_factory=dict)
    target_kind: str | None = None
    target_public_id: str | None = None
    #: Gasto medido que o problema consumiu, em centavos. ``None`` quando não
    #: há custo medido — e aí o texto não estima nada.
    measured_waste_cents: Decimal | None = None


@dataclass(frozen=True, slots=True)
class DetectorOutcome:
    """O que uma passada do detector produziu, incluindo o que ela não pôde ver."""

    detector: str
    status: str
    detail: str
    findings: tuple[Finding, ...] = ()


def fingerprint(detector: str, target: str) -> str:
    return f"{detector}:{target}"


def _pct(valor: float) -> str:
    return f"{round(valor * 100)}%"


def _reais(centavos: Decimal) -> str:
    return f"R$ {(centavos / 100).quantize(Decimal('0.01'))}".replace(".", ",")


# --------------------------------------------------------------------------- #
# 1. Gabarito suspeito
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class QuestionStats:
    public_id: str
    statement: str
    attempts: int
    correct: int
    alternatives: int
    answer_letter: str | None = None
    #: Letra que a maioria escolheu, e quantos a escolheram. É a evidência mais
    #: forte do detector: se 70% marcaram B e o gabarito diz A, o problema não
    #: é dificuldade.
    most_chosen_letter: str | None = None
    most_chosen_count: int = 0
    subject_name: str | None = None


def suspect_answer_keys(
    rows: list[QuestionStats] | tuple[QuestionStats, ...],
    *,
    min_attempts: int,
    chance_divisor: int,
    considered: int,
) -> DetectorOutcome:
    """Questões cujo acerto está muito abaixo do acaso.

    O limiar é relativo ao acaso, não absoluto: 20% de acerto é desastre numa
    questão de 4 alternativas e esperado numa de 5 com gabarito difícil. O
    divisor padrão é 2 — metade do acaso.
    """
    elegiveis = [item for item in rows if item.attempts >= min_attempts]
    if not elegiveis:
        return DetectorOutcome(
            DetectorKey.SUSPECT_ANSWER_KEY,
            DetectorStatus.NOT_ENOUGH_DATA,
            f"nenhuma questão alcançou {min_attempts} respostas; "
            f"{considered} questão(ões) com resposta foram olhadas",
        )

    achados: list[Finding] = []
    for item in elegiveis:
        if item.alternatives < 2:
            # Questão sem alternativas cadastradas não tem acaso definido.
            continue
        acaso = 1 / item.alternatives
        limite = acaso / max(1, chance_divisor)
        acerto = item.correct / item.attempts
        if acerto > limite:
            continue

        maioria = ""
        if item.most_chosen_letter and item.most_chosen_count:
            fatia = item.most_chosen_count / item.attempts
            maioria = (
                f" A alternativa mais marcada foi a {item.most_chosen_letter} "
                f"({_pct(fatia)} das respostas)"
            )
            if item.answer_letter and item.most_chosen_letter != item.answer_letter:
                maioria += f", e o gabarito aponta a {item.answer_letter}"
            maioria += "."

        achados.append(
            Finding(
                detector=DetectorKey.SUSPECT_ANSWER_KEY,
                severity=Severity.HIGH,
                destination=Destination.ADMIN,
                fingerprint=fingerprint(DetectorKey.SUSPECT_ANSWER_KEY, item.public_id),
                title=f"Gabarito suspeito: {item.statement[:80]}",
                detail=(
                    f"{_pct(acerto)} de acerto em {item.attempts} respostas, contra "
                    f"{_pct(acaso)} esperados por acaso em {item.alternatives} "
                    f"alternativas.{maioria}"
                ),
                proposal=(
                    "Conferir o gabarito desta questão na tela de questões. Enquanto "
                    "ela estiver publicada com gabarito errado, cada resposta ensina o "
                    "contrário do certo e contamina a estatística do tópico."
                ),
                evidence={
                    "attempts": item.attempts,
                    "correct": item.correct,
                    "accuracy": round(acerto, 4),
                    "chance": round(acaso, 4),
                    "threshold": round(limite, 4),
                    "answer_letter": item.answer_letter,
                    "most_chosen_letter": item.most_chosen_letter,
                    "most_chosen_count": item.most_chosen_count,
                    "subject": item.subject_name,
                },
                target_kind="QUESTION",
                target_public_id=item.public_id,
            )
        )

    if not achados:
        return DetectorOutcome(
            DetectorKey.SUSPECT_ANSWER_KEY,
            DetectorStatus.CLEAN,
            f"{len(elegiveis)} questão(ões) com {min_attempts}+ respostas conferidas; "
            "nenhuma abaixo da metade do acaso",
        )
    return DetectorOutcome(
        DetectorKey.SUSPECT_ANSWER_KEY,
        DetectorStatus.FOUND,
        f"{len(achados)} de {len(elegiveis)} questão(ões) com amostra suficiente",
        tuple(achados),
    )


# --------------------------------------------------------------------------- #
# 2. Tópico do edital sem material
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class TopicGap:
    label: str
    subject_label: str
    #: Peso declarado no edital. ``None`` quando o edital não trouxe peso.
    weight: Decimal | None = None
    #: Questões que a disciplina tem na prova, como o edital declarou.
    questions_count: int | None = None

    @property
    def cost_of_absence(self) -> Decimal:
        """Quanto a ausência custa, pelo que o edital declarou.

        Sem peso nem número de questões, o custo é zero **para ordenar** — não
        porque a lacuna não importe, mas porque não há com o que compará-la. O
        achado diz isso em texto.
        """
        peso = self.weight if self.weight is not None else Decimal("0")
        questoes = Decimal(self.questions_count or 0)
        return peso * questoes


@dataclass(frozen=True, slots=True)
class CompetitionGaps:
    competition_public_id: str
    competition_name: str
    notice_title: str
    #: Tópicos vinculados e sem material nenhum.
    gaps: tuple[TopicGap, ...]
    #: Tópicos vinculados do edital — o denominador da lacuna.
    linked_topics: int


def topics_without_material(
    competitions: list[CompetitionGaps] | tuple[CompetitionGaps, ...],
    *,
    min_topics: int,
    top_topics: int,
) -> DetectorOutcome:
    """Um achado por concurso, com os tópicos mais caros primeiro."""
    if not competitions:
        return DetectorOutcome(
            DetectorKey.TOPIC_WITHOUT_MATERIAL,
            DetectorStatus.NOT_ENOUGH_DATA,
            "nenhum concurso publicado com edital analisado e tópicos vinculados",
        )

    achados: list[Finding] = []
    for item in competitions:
        if len(item.gaps) < max(1, min_topics):
            continue
        ordenados = sorted(
            item.gaps,
            key=lambda gap: (-gap.cost_of_absence, gap.subject_label, gap.label),
        )[:top_topics]
        sem_peso = [gap for gap in ordenados if gap.weight is None]
        lista = "; ".join(
            f"{gap.subject_label} › {gap.label}"
            + (f" (peso {gap.weight})" if gap.weight is not None else " (sem peso no edital)")
            for gap in ordenados
        )
        achados.append(
            Finding(
                detector=DetectorKey.TOPIC_WITHOUT_MATERIAL,
                severity=(
                    Severity.HIGH if len(item.gaps) * 2 >= item.linked_topics else Severity.MEDIUM
                ),
                destination=Destination.ADMIN,
                fingerprint=fingerprint(
                    DetectorKey.TOPIC_WITHOUT_MATERIAL, item.competition_public_id
                ),
                title=f"{len(item.gaps)} tópico(s) sem material em {item.competition_name}",
                detail=(
                    f"De {item.linked_topics} tópico(s) vinculados de {item.notice_title}, "
                    f"{len(item.gaps)} não têm questão, aula nem mapa mental. "
                    f"Por ordem de peso na prova: {lista}."
                    + (
                        f" {len(sem_peso)} deles não têm peso declarado no edital e "
                        "ficaram no fim da ordem por falta de comparação, não por "
                        "serem menos importantes."
                        if sem_peso
                        else ""
                    )
                ),
                proposal=(
                    "Montar um plano de geração por tópico para estes assuntos, na tela "
                    "de geração em massa. O plano já pula o que existe e mostra a "
                    "estimativa de custo antes de disparar."
                ),
                evidence={
                    "linked_topics": item.linked_topics,
                    "topics_without_material": len(item.gaps),
                    "notice": item.notice_title,
                    "top": [
                        {
                            "subject": gap.subject_label,
                            "topic": gap.label,
                            "weight": str(gap.weight) if gap.weight is not None else None,
                            "questions_count": gap.questions_count,
                        }
                        for gap in ordenados
                    ],
                },
                target_kind="COMPETITION",
                target_public_id=item.competition_public_id,
            )
        )

    if not achados:
        return DetectorOutcome(
            DetectorKey.TOPIC_WITHOUT_MATERIAL,
            DetectorStatus.CLEAN,
            f"{len(competitions)} concurso(s) conferidos; todos os tópicos vinculados "
            "têm algum material",
        )
    return DetectorOutcome(
        DetectorKey.TOPIC_WITHOUT_MATERIAL,
        DetectorStatus.FOUND,
        f"{len(achados)} de {len(competitions)} concurso(s) com lacuna",
        tuple(achados),
    )


# --------------------------------------------------------------------------- #
# 3. Modelo errando acima do limiar
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class FeatureErrors:
    feature: str
    feature_label: str
    model_slug: str
    provider_slug: str
    calls: int
    errors: int
    #: Custo medido das chamadas que falharam. Zero quando o modelo não tem
    #: preço cadastrado — e aí o achado não afirma desperdício.
    error_cost_cents: Decimal = Decimal("0")
    top_error_code: str | None = None


def model_error_rates(
    rows: list[FeatureErrors] | tuple[FeatureErrors, ...],
    *,
    window_days: int,
    min_calls: int,
    error_rate_percent: int,
) -> DetectorOutcome:
    elegiveis = [item for item in rows if item.calls >= min_calls]
    if not elegiveis:
        total = sum(item.calls for item in rows)
        return DetectorOutcome(
            DetectorKey.MODEL_ERROR_RATE,
            DetectorStatus.NOT_ENOUGH_DATA,
            f"nenhuma funcionalidade alcançou {min_calls} chamadas em {window_days} "
            f"dia(s); {total} chamada(s) registradas no período",
        )

    limite = error_rate_percent / 100
    achados: list[Finding] = []
    for item in elegiveis:
        taxa = item.errors / item.calls
        if taxa < limite:
            continue
        desperdicio = item.error_cost_cents if item.error_cost_cents > 0 else None
        custo = (
            f" As chamadas que falharam custaram {_reais(item.error_cost_cents)}."
            if desperdicio is not None
            else " O modelo não tem preço cadastrado, então o desperdício não pode ser "
            "estimado em dinheiro."
        )
        achados.append(
            Finding(
                detector=DetectorKey.MODEL_ERROR_RATE,
                severity=Severity.HIGH if taxa >= 0.25 else Severity.MEDIUM,
                destination=Destination.ADMIN,
                fingerprint=fingerprint(
                    DetectorKey.MODEL_ERROR_RATE, f"{item.feature}:{item.model_slug}"
                ),
                title=f"{item.feature_label}: {_pct(taxa)} de erro no modelo {item.model_slug}",
                detail=(
                    f"{item.errors} de {item.calls} chamadas falharam em {window_days} "
                    f"dia(s), no provedor {item.provider_slug}."
                    + (
                        f" Erro mais frequente: {item.top_error_code}."
                        if item.top_error_code
                        else ""
                    )
                    + custo
                ),
                proposal=(
                    "Testar a conexão do provedor no painel de IA e, se o erro "
                    "persistir, trocar o modelo desta funcionalidade ou cadastrar um "
                    "modelo de reserva para ela — a reserva atende justamente quando o "
                    "principal responde limite de requisições ou indisponibilidade."
                ),
                evidence={
                    "window_days": window_days,
                    "calls": item.calls,
                    "errors": item.errors,
                    "error_rate": round(taxa, 4),
                    "provider": item.provider_slug,
                    "model": item.model_slug,
                    "top_error_code": item.top_error_code,
                    "error_cost_cents": str(item.error_cost_cents),
                },
                target_kind="AI_FEATURE",
                target_public_id=item.feature,
                measured_waste_cents=desperdicio,
            )
        )

    if not achados:
        return DetectorOutcome(
            DetectorKey.MODEL_ERROR_RATE,
            DetectorStatus.CLEAN,
            f"{len(elegiveis)} funcionalidade(s) com {min_calls}+ chamadas; nenhuma "
            f"acima de {error_rate_percent}% de erro",
        )
    return DetectorOutcome(
        DetectorKey.MODEL_ERROR_RATE,
        DetectorStatus.FOUND,
        f"{len(achados)} de {len(elegiveis)} funcionalidade(s) com amostra suficiente",
        tuple(achados),
    )


# --------------------------------------------------------------------------- #
# 4. Regra de roteamento inerte
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RouteActivity:
    route_id: int
    label: str
    feature: str
    feature_label: str
    model_slug: str | None
    #: Quantas decisões avaliaram esta regra.
    evaluated: int
    matched: int
    not_evaluated: int
    #: Sinais que faltaram, quando a regra ficou sem avaliação.
    missing_signals: tuple[str, ...] = ()


def inert_routes(
    rows: list[RouteActivity] | tuple[RouteActivity, ...],
    *,
    window_days: int,
    min_decisions: int,
    rows_read: int,
    max_rows: int,
) -> DetectorOutcome:
    """Regras ligadas que não decidiram nada.

    Separa os dois motivos, porque a providência é diferente: condição que
    nunca valeu é limiar errado; sinal ausente é regra que depende de algo que
    a funcionalidade não informa — e essa nunca vai valer, não importa o
    limiar.
    """
    elegiveis = [item for item in rows if item.evaluated >= min_decisions]
    if not elegiveis:
        return DetectorOutcome(
            DetectorKey.ROUTE_INERT,
            DetectorStatus.NOT_ENOUGH_DATA,
            f"nenhuma regra foi avaliada em {min_decisions} decisões dentro de "
            f"{window_days} dia(s); {rows_read} decisão(ões) lidas (teto de {max_rows})",
        )

    achados: list[Finding] = []
    for item in elegiveis:
        if item.matched:
            continue
        por_sinal = item.not_evaluated >= item.evaluated
        if por_sinal:
            sinais = ", ".join(item.missing_signals) or "um sinal que a chamada não informa"
            detalhe = (
                f"A regra foi avaliada {item.evaluated} vez(es) e ficou sem avaliação em "
                f"todas: {item.feature_label} não informa {sinais}. Nenhum ajuste de "
                "limiar muda isso."
            )
            proposta = (
                "Trocar a condição por um sinal que esta funcionalidade informa, ou "
                "remover a regra. Enquanto ela estiver ligada, o painel mostra uma "
                "configuração que não decide nada."
            )
        else:
            detalhe = (
                f"A regra foi avaliada {item.evaluated} vez(es) e a condição nunca "
                "valeu. O limiar pode estar fora da faixa que as chamadas reais têm."
            )
            proposta = (
                "Conferir o limiar contra os sinais que o histórico de decisões mostra, "
                "ajustar ou remover a regra."
            )

        achados.append(
            Finding(
                detector=DetectorKey.ROUTE_INERT,
                severity=Severity.LOW,
                destination=Destination.ADMIN,
                fingerprint=fingerprint(DetectorKey.ROUTE_INERT, str(item.route_id)),
                title=f'Regra "{item.label}" nunca se aplicou',
                detail=detalhe,
                proposal=proposta,
                evidence={
                    "window_days": window_days,
                    "rows_read": rows_read,
                    "max_rows": max_rows,
                    "evaluated": item.evaluated,
                    "matched": item.matched,
                    "not_evaluated": item.not_evaluated,
                    "missing_signals": list(item.missing_signals),
                    "feature": item.feature,
                    "model": item.model_slug,
                },
                target_kind="AI_ROUTE",
                target_public_id=str(item.route_id),
            )
        )

    if not achados:
        return DetectorOutcome(
            DetectorKey.ROUTE_INERT,
            DetectorStatus.CLEAN,
            f"{len(elegiveis)} regra(s) com {min_decisions}+ avaliações; todas se "
            "aplicaram ao menos uma vez",
        )
    return DetectorOutcome(
        DetectorKey.ROUTE_INERT,
        DetectorStatus.FOUND,
        f"{len(achados)} de {len(elegiveis)} regra(s) com avaliações suficientes",
        tuple(achados),
    )
