"""Campanha e ranking da Batalha RPG — os dois lados da Fase 3 que medem gente.

A campanha **não inventa conteúdo**. Ela é a lista de disciplinas fracas do
candidato, que já sai do Priority Score, apresentada como uma sequência de
chefes. Sem Priority Score não há campanha — e a tela diz isso em vez de exibir
um mapa de fantasia.

O ranking herda as duas proteções que a liga já trazia (item 21 do pedido):
compara **dentro do mesmo contexto**, e some inteiro para quem desligou a
comparação. E acrescenta a regra que a Fase 3 exigiu: a ordem é a **taxa de
acerto crua**, nunca o dano. Equipamento e classe mudam o combate; se mudassem
também a posição na tabela, a plataforma estaria dizendo que quem tem armadura
melhor estuda melhor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.game.leagues import MIN_LEAGUE_SIZE

#: Estágios que a campanha mostra. Mais que isso vira lista de tarefas, não mapa.
MAX_STAGES = 6

#: Abaixo disto ninguém entra na tabela: duas batalhas não dizem quem vai melhor.
MIN_RANKED_BATTLES = 3


# --------------------------------------------------------------------------- #
# Campanha
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class StageInput:
    """Uma disciplina do Priority Score, com o que já foi feito nela."""

    subject_id: int
    subject_public_id: str
    label: str
    #: O Priority Score real. É ele que ordena a campanha.
    priority_score: float
    #: Batalhas de chefe já encerradas nesta disciplina, e quantas foram vencidas
    #: pelo critério de acerto.
    battles: int = 0
    cleared_battles: int = 0
    questions_available: int = 0


@dataclass(frozen=True, slots=True)
class CampaignStage:
    order: int
    subject_public_id: str
    label: str
    priority_score: float
    battles: int
    cleared: bool
    is_locked: bool
    #: Por que este estágio ainda não pode ser jogado, quando for o caso.
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class Campaign:
    stages: list[CampaignStage] = field(default_factory=list)
    cleared: int = 0
    total: int = 0
    empty_reason: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.total > 0 and self.cleared == self.total


def build_campaign(items: list[StageInput], *, required_questions: int) -> Campaign:
    """Monta a campanha a partir das disciplinas fracas reais do candidato.

    A ordem é a do Priority Score: a campanha começa onde o candidato está pior,
    que é a única ordem que ajuda alguém a passar. Nenhum estágio é trancado por
    outro — **conteúdo de estudo não fica atrás de progresso de jogo** (itens 3 e
    24 da gamificação). O que pode faltar é questão no banco, e isso é dito.
    """
    if not items:
        return Campaign(
            empty_reason=(
                "A campanha enfrenta as suas disciplinas mais frágeis, e elas saem do "
                "Priority Score. Calcule a prioridade em Inteligência para abrir o mapa."
            )
        )

    ordered = sorted(items, key=lambda item: (-item.priority_score, item.label))[:MAX_STAGES]
    stages: list[CampaignStage] = []
    for index, item in enumerate(ordered, start=1):
        short = item.questions_available < required_questions
        stages.append(
            CampaignStage(
                order=index,
                subject_public_id=item.subject_public_id,
                label=item.label,
                priority_score=item.priority_score,
                battles=item.battles,
                cleared=item.cleared_battles > 0,
                is_locked=short,
                blocked_reason=(
                    (
                        f"O banco tem {item.questions_available} de "
                        f"{required_questions} questões publicadas nesta disciplina."
                    )
                    if short
                    else None
                ),
            )
        )

    return Campaign(
        stages=stages,
        cleared=sum(1 for item in stages if item.cleared),
        total=len(stages),
    )


# --------------------------------------------------------------------------- #
# Ranking
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RankingEntry:
    user_key: str
    battles: int
    #: Batalhas em que a taxa de acerto bateu o alvo — o mesmo critério que
    #: decide "desafio cumprido". Dano e equipamento não entram aqui.
    wins: int
    #: Acertos somados nas batalhas encerradas. Serve de desempate.
    correct: int
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class RankingMember:
    position: int
    label: str
    battles: int
    wins: int
    correct: int
    is_you: bool
    is_named: bool


@dataclass(frozen=True, slots=True)
class BattleRanking:
    context_label: str
    participants: int
    members: list[RankingMember] = field(default_factory=list)
    your_position: int | None = None
    empty_reason: str | None = None
    note: str = (
        "A ordem é quantas batalhas você venceu pelo acerto — o mesmo critério que dá XP. "
        "Equipamento e classe mudam o combate, não a posição, e nada aqui diz coisa "
        "alguma sobre aprovação."
    )


def build_ranking(
    entries: list[RankingEntry], *, you_key: str, context_label: str
) -> BattleRanking:
    """Ordena por vitórias reais, com anonimato de fábrica e amostra mínima."""
    ranked = [item for item in entries if item.battles >= MIN_RANKED_BATTLES]

    if len(ranked) < MIN_LEAGUE_SIZE:
        return BattleRanking(
            context_label=context_label,
            participants=len(ranked),
            empty_reason=(
                f"{len(ranked)} candidato(s) do seu contexto têm ao menos "
                f"{MIN_RANKED_BATTLES} batalhas. A partir de {MIN_LEAGUE_SIZE} a tabela "
                "passa a significar alguma coisa."
            ),
        )

    # Ordena por vitórias e desempata por acertos somados. **Não há percentual
    # aqui**: uma batalha pode terminar antes das questões acabarem, e dividir
    # por um denominador incerto seria fabricar estatística.
    ordered = sorted(ranked, key=lambda item: (-item.wins, -item.correct, item.user_key))

    members: list[RankingMember] = []
    your_position: int | None = None
    for position, item in enumerate(ordered, start=1):
        is_you = item.user_key == you_key
        if is_you:
            your_position = position
        # Anonimato por padrão: só aparece com nome quem escolheu aparecer.
        named = bool(item.display_name)
        members.append(
            RankingMember(
                position=position,
                label=item.display_name or ("Você" if is_you else f"Candidato #{position}"),
                battles=item.battles,
                wins=item.wins,
                correct=item.correct,
                is_you=is_you,
                is_named=named,
            )
        )

    return BattleRanking(
        context_label=context_label,
        participants=len(ordered),
        members=members,
        your_position=your_position,
    )
