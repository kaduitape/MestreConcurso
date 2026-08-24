"""Priority Score: o que estudar primeiro, e por quê.

A regra que sustenta esta fase: **as parcelas exibidas somam exatamente o número
exibido**. O arredondamento usa o método do maior resto, então a soma fecha em
inteiros — não há "≈" na interface.

Cada sinal que falta é declarado em ``missing_signals`` e vale zero. A plataforma
prefere um score menor e honesto a um score inflado por suposição.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAX_SCORE = 100

# Teto de cada sinal. A soma dos tetos é o score máximo.
WEIGHT_INCIDENCE = 30
WEIGHT_NOTICE = 25
WEIGHT_PERFORMANCE = 25
WEIGHT_STALENESS = 12
WEIGHT_COVERAGE = 8

# Amostras mínimas por sinal.
MIN_ATTEMPTS = 5
# A partir daqui, "faz tempo que não estuda" já vale o teto do sinal.
STALENESS_SATURATION_DAYS = 21

LABELS: dict[str, str] = {
    "incidencia_na_banca": "Incidência na banca",
    "peso_no_edital": "Peso no edital",
    "seu_desempenho": "Seu desempenho",
    "tempo_sem_estudar": "Tempo sem estudar",
    "conteudo_pendente": "Conteúdo ainda não coberto",
}


@dataclass(frozen=True, slots=True)
class PriorityInput:
    """Tudo o que se sabe sobre uma disciplina/assunto de um candidato.

    Campos ``None`` significam **sinal ausente**, não zero: a diferença aparece
    no resultado.
    """

    scope_key: str
    label: str
    color_token: str = "subject-especifica"
    subject_id: int | None = None
    topic_id: int | None = None
    # 0..1 — fatia das questões da banca (mapa de incidência).
    incidence_pct: float | None = None
    # 0..1 — participação da disciplina no edital do cargo.
    notice_share: float | None = None
    # 0..1 — taxa de acerto do candidato.
    accuracy: float | None = None
    attempts: int = 0
    days_since_studied: int | None = None
    # 0..1 — quanto do tempo planejado já foi cumprido.
    completion: float | None = None


@dataclass(frozen=True, slots=True)
class Contribution:
    key: str
    label: str
    points: int
    max_points: int
    # Como o ponto saiu do dado bruto — o texto que a interface mostra.
    detail: str


@dataclass(frozen=True, slots=True)
class PriorityScore:
    scope_key: str
    label: str
    color_token: str
    subject_id: int | None
    topic_id: int | None
    score: int
    contributions: list[Contribution] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    # Fração dos sinais disponíveis (0..1): a confiança do próprio score.
    coverage: float = 0.0

    @property
    def contributions_sum(self) -> int:
        return sum(item.points for item in self.contributions)


def _largest_remainder(raw: list[float]) -> list[int]:
    """Arredonda mantendo a soma igual ao inteiro da soma original."""
    floors = [int(value) for value in raw]
    remainder = round(sum(raw)) - sum(floors)
    if remainder <= 0:
        return floors
    order = sorted(range(len(raw)), key=lambda index: raw[index] - floors[index], reverse=True)
    for index in order[:remainder]:
        floors[index] += 1
    return floors


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%".replace(".", ",")


def compute_priority(item: PriorityInput) -> PriorityScore:
    """Calcula o score de um recorte, com a origem de cada ponto."""
    raw: list[float] = []
    meta: list[tuple[str, int, str]] = []
    missing: list[str] = []

    # 1. Incidência na banca — o que mais cai vale mais.
    if item.incidence_pct is None:
        missing.append("incidencia_na_banca")
        raw.append(0.0)
        meta.append(("incidencia_na_banca", WEIGHT_INCIDENCE, "sem amostra de questões da banca"))
    else:
        share = min(1.0, item.incidence_pct / 0.25)  # 25% da prova satura o sinal
        raw.append(share * WEIGHT_INCIDENCE)
        meta.append(
            (
                "incidencia_na_banca",
                WEIGHT_INCIDENCE,
                f"{_percent(item.incidence_pct)} das questões da banca",
            )
        )

    # 2. Peso no edital — o que o edital cobra mais.
    if item.notice_share is None:
        missing.append("peso_no_edital")
        raw.append(0.0)
        meta.append(("peso_no_edital", WEIGHT_NOTICE, "disciplina fora do edital do cargo"))
    else:
        share = min(1.0, item.notice_share / 0.25)
        raw.append(share * WEIGHT_NOTICE)
        meta.append(
            ("peso_no_edital", WEIGHT_NOTICE, f"{_percent(item.notice_share)} do plano de estudo")
        )

    # 3. Desempenho — errar muito sobe a prioridade; acertar muito derruba.
    if item.accuracy is None or item.attempts < MIN_ATTEMPTS:
        missing.append("seu_desempenho")
        raw.append(0.0)
        meta.append(
            (
                "seu_desempenho",
                WEIGHT_PERFORMANCE,
                (
                    f"{item.attempts} resposta(s) registrada(s); "
                    f"mínimo de {MIN_ATTEMPTS} para entrar na conta"
                ),
            )
        )
    else:
        raw.append((1 - item.accuracy) * WEIGHT_PERFORMANCE)
        meta.append(
            (
                "seu_desempenho",
                WEIGHT_PERFORMANCE,
                f"{_percent(item.accuracy)} de acerto em {item.attempts} respostas",
            )
        )

    # 4. Tempo sem estudar — o esquecimento é previsível, então é contabilizado.
    if item.days_since_studied is None:
        missing.append("tempo_sem_estudar")
        raw.append(0.0)
        meta.append(("tempo_sem_estudar", WEIGHT_STALENESS, "ainda não estudada neste plano"))
    else:
        ratio = min(1.0, item.days_since_studied / STALENESS_SATURATION_DAYS)
        raw.append(ratio * WEIGHT_STALENESS)
        meta.append(
            (
                "tempo_sem_estudar",
                WEIGHT_STALENESS,
                f"{item.days_since_studied} dia(s) desde o último estudo",
            )
        )

    # 5. Conteúdo pendente — o que ainda não foi coberto pesa mais.
    if item.completion is None:
        missing.append("conteudo_pendente")
        raw.append(0.0)
        meta.append(("conteudo_pendente", WEIGHT_COVERAGE, "sem plano ativo para comparar"))
    else:
        pending = max(0.0, 1 - min(1.0, item.completion))
        raw.append(pending * WEIGHT_COVERAGE)
        meta.append(
            (
                "conteudo_pendente",
                WEIGHT_COVERAGE,
                f"{_percent(1 - pending)} do tempo planejado já cumprido",
            )
        )

    points = _largest_remainder(raw)
    contributions = [
        Contribution(
            key=key,
            label=LABELS[key],
            points=points[index],
            max_points=ceiling,
            detail=detail,
        )
        for index, (key, ceiling, detail) in enumerate(meta)
    ]
    return PriorityScore(
        scope_key=item.scope_key,
        label=item.label,
        color_token=item.color_token,
        subject_id=item.subject_id,
        topic_id=item.topic_id,
        score=sum(points),
        contributions=contributions,
        missing_signals=missing,
        coverage=round((len(meta) - len(missing)) / len(meta), 3),
    )


def rank_priorities(items: list[PriorityInput]) -> list[PriorityScore]:
    """Calcula e ordena — maior score primeiro, desempate pelo nome."""
    scores = [compute_priority(item) for item in items]
    scores.sort(key=lambda score: (-score.score, score.label))
    return scores


def adjust_shares_by_priority(
    shares: dict[str, float], scores: dict[str, int], *, max_shift: float = 0.20
) -> dict[str, float]:
    """Inclina a divisão do plano na direção do Priority Score, sem virar a mesa.

    A fatia de cada disciplina se move no máximo ``max_shift`` (20%) em relação à
    linha de base do edital: o desempenho ajusta o plano, não o substitui.
    Disciplinas sem score ficam exatamente onde estavam.
    """
    if not shares or not scores:
        return dict(shares)

    ranked = [scores[key] for key in shares if key in scores]
    if not ranked:
        return dict(shares)
    average = sum(ranked) / len(ranked)
    if average <= 0:
        return dict(shares)

    adjusted: dict[str, float] = {}
    for key, share in shares.items():
        score = scores.get(key)
        if score is None:
            adjusted[key] = share
            continue
        deviation = (score - average) / average
        factor = 1 + max(-max_shift, min(max_shift, deviation * max_shift))
        adjusted[key] = share * factor

    total = sum(adjusted.values())
    if total <= 0:
        return dict(shares)
    return {key: value / total for key, value in adjusted.items()}
