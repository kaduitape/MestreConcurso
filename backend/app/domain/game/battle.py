"""Batalha RPG — a questão vira um combate, sem deixar de ser uma questão.

A decisão que sustenta o módulo inteiro: **o estado da batalha é derivado das
respostas**, nunca acumulado. HP do guerreiro, HP do inimigo, quem está vivo —
tudo sai da lista de respostas já dadas, exatamente como o estado das rodadas de
desafio da Fase 3. Um contador de HP guardado à parte poderia divergir do que o
candidato de fato respondeu, e aí o combate mentiria sobre o estudo.

A segunda decisão é sobre leitura. Um RPG que esconde o enunciado atrás de efeito
falhou como plataforma de estudo, por mais bonito que esteja: por isso a escolha
de layout olha **as alternativas**, o texto tem prioridade sobre o monstro, e no
modelo compacto nada que se move carrega texto junto.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum

# --------------------------------------------------------------------------- #
# Combate
# --------------------------------------------------------------------------- #
PLAYER_MAX_HP = 100

#: Dano de um acerto e de um erro. O erro custa menos que o acerto rende: a
#: batalha é uma consequência do estudo, não uma punição por errar.
PLAYER_DAMAGE = 34
MONSTER_DAMAGE = 20

#: Fração de acertos que derruba o inimigo. Com 0,75, acertar três de cada
#: quatro questões vence a batalha — o HP acompanha o tamanho da rodada em vez
#: de ser um número solto.
ENEMY_HP_ACCURACY_TARGET = 0.75


class BattleLayout(StrEnum):
    #: Alternativas curtas: monstros grandes na arena, um por alternativa.
    MONSTER_ARENA = "monster-arena"
    #: Alternativas longas: avatar pequeno ao lado do texto completo.
    COMPACT_ANSWER = "compact-answer"


class Viewport(StrEnum):
    DESKTOP = "desktop"
    TABLET = "tablet"
    MOBILE = "mobile"


class BattleState(StrEnum):
    """Os estados que a tela atravessa. Um só, em vez de booleanos espalhados."""

    QUESTION = "QUESTION"
    ANSWER_SELECTED = "ANSWER_SELECTED"
    PLAYER_ATTACK = "PLAYER_ATTACK"
    ENEMY_ATTACK = "ENEMY_ATTACK"
    DAMAGE = "DAMAGE"
    RESULT = "RESULT"
    EXPLANATION = "EXPLANATION"
    NEXT_QUESTION = "NEXT_QUESTION"
    VICTORY = "VICTORY"
    DEFEAT = "DEFEAT"


# --------------------------------------------------------------------------- #
# Escolha de layout
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class LayoutSettings:
    """Limiares da escolha de layout.

    Vivem no banco (``battle_settings``) e são semeados a partir daqui. O pedido
    é explícito: dá para calibrar a régua sem tocar em código, porque o ponto em
    que uma alternativa "fica longa" depende da fonte, do idioma e do aparelho —
    coisas que mudam sem aviso.
    """

    short_answer_max: int = 45
    short_average_max: int = 30
    tablet_short_answer_max: int = 38
    tablet_short_average_max: int = 26
    mobile_short_answer_max: int = 30
    mobile_short_average_max: int = 20
    #: Acima disto a arena não cabe sem espremer os monstros.
    max_options_for_arena: int = 5
    #: Caracteres que cabem numa linha do card, por viewport. É o que permite
    #: estimar quantas linhas o texto ocuparia antes de renderizar.
    chars_per_line_desktop: int = 34
    chars_per_line_tablet: int = 28
    chars_per_line_mobile: int = 22
    #: Mais linhas que isto embaixo de um monstro empurra o enunciado da tela.
    max_lines_for_arena: int = 2

    def answer_max_for(self, viewport: str) -> int:
        if viewport == Viewport.MOBILE:
            return self.mobile_short_answer_max
        if viewport == Viewport.TABLET:
            return self.tablet_short_answer_max
        return self.short_answer_max

    def average_max_for(self, viewport: str) -> int:
        if viewport == Viewport.MOBILE:
            return self.mobile_short_average_max
        if viewport == Viewport.TABLET:
            return self.tablet_short_average_max
        return self.short_average_max

    def chars_per_line_for(self, viewport: str) -> int:
        if viewport == Viewport.MOBILE:
            return self.chars_per_line_mobile
        if viewport == Viewport.TABLET:
            return self.chars_per_line_tablet
        return self.chars_per_line_desktop


DEFAULT_LAYOUT_SETTINGS = LayoutSettings()


@dataclass(frozen=True, slots=True)
class LayoutDecision:
    layout: str
    #: Por que este layout. A tela pode não mostrar, mas a decisão não é opaca.
    reason: str
    max_length: int
    average_length: float
    estimated_lines: int
    options: int
    viewport: str

    @property
    def is_arena(self) -> bool:
        return self.layout == BattleLayout.MONSTER_ARENA


def select_battle_layout(
    option_texts: list[str],
    *,
    viewport: str = Viewport.DESKTOP,
    settings: LayoutSettings | None = None,
) -> LayoutDecision:
    """Escolhe o layout olhando **as alternativas**, não a pergunta.

    A pergunta ocupa um painel próprio, que rola quando precisa. Quem decide se
    a arena cabe é o texto que vai embaixo de cada monstro — e é por isso que a
    conta principal é sobre as alternativas.
    """
    config = settings or DEFAULT_LAYOUT_SETTINGS
    texts = [item.strip() for item in option_texts]
    lengths = [len(item) for item in texts] or [0]

    max_length = max(lengths)
    average_length = round(sum(lengths) / len(lengths), 2)
    per_line = config.chars_per_line_for(viewport)
    estimated_lines = max(1, -(-max_length // per_line))  # divisão para cima

    base = LayoutDecision(
        layout=BattleLayout.COMPACT_ANSWER,
        reason="",
        max_length=max_length,
        average_length=average_length,
        estimated_lines=estimated_lines,
        options=len(texts),
        viewport=viewport,
    )

    def compact(reason: str) -> LayoutDecision:
        return LayoutDecision(
            layout=BattleLayout.COMPACT_ANSWER,
            reason=reason,
            max_length=base.max_length,
            average_length=base.average_length,
            estimated_lines=base.estimated_lines,
            options=base.options,
            viewport=viewport,
        )

    if len(texts) > config.max_options_for_arena:
        return compact(f"{len(texts)} alternativas não cabem na arena sem espremer os monstros.")
    if max_length > config.answer_max_for(viewport):
        return compact(
            f"A maior alternativa tem {max_length} caracteres, acima de "
            f"{config.answer_max_for(viewport)} para {viewport}."
        )
    if average_length > config.average_max_for(viewport):
        return compact(
            f"A média de {average_length:.0f} caracteres passa de "
            f"{config.average_max_for(viewport)} para {viewport}."
        )
    if estimated_lines > config.max_lines_for_arena:
        return compact(
            f"O texto ocuparia {estimated_lines} linhas embaixo do monstro, acima de "
            f"{config.max_lines_for_arena}."
        )

    return LayoutDecision(
        layout=BattleLayout.MONSTER_ARENA,
        reason=(
            f"Alternativas curtas (maior com {max_length} caracteres, média "
            f"{average_length:.0f}): cabem embaixo dos monstros."
        ),
        max_length=base.max_length,
        average_length=base.average_length,
        estimated_lines=base.estimated_lines,
        options=base.options,
        viewport=viewport,
    )


# --------------------------------------------------------------------------- #
# Bestiário
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class MonsterSpecies:
    slug: str
    name: str
    #: Forma da silhueta desenhada no cliente. Arte em WebP pode substituí-la
    #: depois sem mexer aqui: o cliente só precisa do slug.
    shape: str
    color_token: str
    accent_token: str


#: Silhuetas SVG desenhadas no cliente — leves, escaláveis e sem download. A
#: lista é curta de propósito: fantasia medieval sóbria, sem mascote fofo.
BESTIARY: tuple[MonsterSpecies, ...] = (
    MonsterSpecies("orc", "Orc", "brute", "game-purple", "game-purple-light"),
    MonsterSpecies("wraith", "Espectro", "wisp", "game-blue", "game-cyan"),
    MonsterSpecies("golem", "Golem", "hulk", "game-gold", "game-orange"),
    MonsterSpecies("serpent", "Serpente", "coil", "success", "game-cyan"),
    MonsterSpecies("gargoyle", "Gárgula", "winged", "danger", "game-orange"),
)

BESTIARY_BY_SLUG: dict[str, MonsterSpecies] = {item.slug: item for item in BESTIARY}


def _stable_index(seed: str, size: int) -> int:
    """Índice estável a partir de um texto — o mesmo monstro em toda leitura.

    Sorteio a cada render faria o inimigo trocar de cara no meio da batalha.
    """
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return digest[0] % size if size else 0


def species_for(seed: str) -> MonsterSpecies:
    return BESTIARY[_stable_index(seed, len(BESTIARY))]


def enemy_max_hp(questions: int) -> int:
    """HP do inimigo proporcional ao tamanho da rodada.

    Assim o combate termina junto com as questões, em vez de exigir uma conta de
    cabeça do candidato para saber se ainda dá para vencer.
    """
    needed = max(1, round(questions * ENEMY_HP_ACCURACY_TARGET))
    return needed * PLAYER_DAMAGE


# --------------------------------------------------------------------------- #
# Estado derivado
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class BattleAnswer:
    """Uma resposta já corrigida, reduzida ao que o combate precisa."""

    is_correct: bool


@dataclass(frozen=True, slots=True)
class BattleStatus:
    player_hp: int
    player_max_hp: int
    enemy_hp: int
    enemy_max_hp: int
    answered: int
    correct: int
    wrong: int
    questions: int
    is_over: bool
    #: Verdadeiro só quando o inimigo caiu. Acabar as questões com ele vivo não
    #: é vitória — é a batalha terminando sem desfecho.
    victory: bool
    defeat: bool
    outcome_reason: str | None = None

    @property
    def player_hp_ratio(self) -> float:
        return round(self.player_hp / self.player_max_hp, 4) if self.player_max_hp else 0.0

    @property
    def enemy_hp_ratio(self) -> float:
        return round(self.enemy_hp / self.enemy_max_hp, 4) if self.enemy_max_hp else 0.0


def evaluate_battle(answers: list[BattleAnswer], *, questions: int) -> BattleStatus:
    """Reconstrói o combate a partir das respostas — a única fonte de verdade."""
    correct = sum(1 for item in answers if item.is_correct)
    wrong = len(answers) - correct

    max_hp = enemy_max_hp(questions)
    enemy_hp = max(0, max_hp - correct * PLAYER_DAMAGE)
    player_hp = max(0, PLAYER_MAX_HP - wrong * MONSTER_DAMAGE)

    victory = enemy_hp == 0
    defeat = player_hp == 0 and not victory
    exhausted = len(answers) >= questions

    reason: str | None = None
    if victory:
        reason = "O inimigo caiu."
    elif defeat:
        reason = "Seu guerreiro não aguentou os erros desta rodada."
    elif exhausted:
        reason = "As questões acabaram e o inimigo continua de pé."

    return BattleStatus(
        player_hp=player_hp,
        player_max_hp=PLAYER_MAX_HP,
        enemy_hp=enemy_hp,
        enemy_max_hp=max_hp,
        answered=len(answers),
        correct=correct,
        wrong=wrong,
        questions=questions,
        is_over=victory or defeat or exhausted,
        victory=victory,
        defeat=defeat,
        outcome_reason=reason,
    )


# --------------------------------------------------------------------------- #
# Monstros de uma questão
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class AnswerMonster:
    """O monstro que representa uma alternativa na tela."""

    letter: str
    species: str
    name: str
    shape: str
    color_token: str
    accent_token: str
    #: Variação da silhueta, para quatro monstros da mesma espécie não ficarem
    #: idênticos lado a lado.
    variant: int


@dataclass(frozen=True, slots=True)
class QuestionBattle:
    question_public_id: str
    monsters: list[AnswerMonster] = field(default_factory=list)
    layout: LayoutDecision | None = None


def monsters_for(
    question_public_id: str, letters: list[str], *, enemy: MonsterSpecies
) -> list[AnswerMonster]:
    """Um monstro por alternativa, estável e derivado da questão.

    Todos da espécie do inimigo da batalha: é ele que está sendo enfrentado, e
    quatro espécies diferentes por questão fariam o combate perder o fio.
    """
    return [
        AnswerMonster(
            letter=letter,
            species=enemy.slug,
            name=enemy.name,
            shape=enemy.shape,
            color_token=enemy.color_token,
            accent_token=enemy.accent_token,
            variant=_stable_index(f"{question_public_id}:{letter}", 4),
        )
        for letter in letters
    ]
