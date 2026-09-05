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


class BattlePower(StrEnum):
    """Os três poderes da Fase 2. A lista é curta de propósito.

    Nenhum deles compra conteúdo de estudo nem some com a questão: um bloqueia o
    próximo dano, outro tira uma alternativa errada, o terceiro mostra uma pista
    **que já existe cadastrada**. Poder que revelasse a resposta transformaria a
    batalha num teatro, e o candidato sairia dela achando que sabe.
    """

    SHIELD = "SHIELD"
    ELIMINATE = "ELIMINATE"
    HINT = "HINT"


POWER_LABELS: dict[str, str] = {
    BattlePower.SHIELD: "Escudo",
    BattlePower.ELIMINATE: "Eliminar",
    BattlePower.HINT: "Dica",
}

POWER_DESCRIPTIONS: dict[str, str] = {
    BattlePower.SHIELD: "Impede o dano do próximo erro.",
    BattlePower.ELIMINATE: "Remove uma alternativa incorreta.",
    BattlePower.HINT: "Mostra uma pista tirada da explicação já cadastrada.",
}


@dataclass(frozen=True, slots=True)
class CombatSettings:
    """Réguas do combate — combo, crítico, moedas e preço dos poderes.

    Vivem no banco, ao lado das réguas de layout, pela mesma razão: o ponto em
    que um acerto é "rápido" e o preço de um escudo são decisões de produto que
    mudam com o uso. Nenhuma delas é constante de código.
    """

    #: Acerto abaixo deste tempo é crítico. Vinte segundos é o padrão de fábrica,
    #: não uma verdade: a régua existe justamente para ser calibrada com dados.
    critical_seconds: int = 20
    #: Dano extra do crítico e de cada degrau de combo, em porcento.
    critical_bonus_percent: int = 50
    combo_damage_percent: int = 10
    #: Degraus de combo que ainda contam. Sem teto, uma sequência longa
    #: derrubaria qualquer inimigo com dois acertos.
    max_combo_steps: int = 5
    coins_per_correct: int = 5
    coins_per_combo_step: int = 2
    #: Moedas com que a batalha começa, para o primeiro poder não depender de
    #: já ter acertado alguma coisa.
    starting_coins: int = 30
    shield_cost: int = 25
    eliminate_cost: int = 20
    hint_cost: int = 15
    #: Vida extra de um chefe, sobre a de um inimigo comum de mesmo tamanho.
    boss_hp_percent: int = 60

    def cost_of(self, power: str) -> int:
        if power == BattlePower.SHIELD:
            return self.shield_cost
        if power == BattlePower.ELIMINATE:
            return self.eliminate_cost
        return self.hint_cost


DEFAULT_COMBAT_SETTINGS = CombatSettings()


# --------------------------------------------------------------------------- #
# Fase 3 — classes e equipamentos
# --------------------------------------------------------------------------- #
#
# A linha que separa o RPG do estudo, e que nenhuma peça atravessa:
#
#     classe e equipamento mudam o **combate**, nunca a **medição**.
#
# Eles alteram vida, dano, moedas e o preço dos poderes. Não escolhem questão,
# não mexem na dificuldade, não destravam conteúdo e não entram no XP. O que
# decide "desafio cumprido", o que limpa um estágio de campanha e o que ordena o
# ranking continua sendo a taxa de acerto crua — a mesma com e sem armadura.
# Sem essa linha, um equipamento melhor faria a plataforma dizer que o candidato
# está melhor do que está, que é a única coisa que ela não pode fazer.


@dataclass(frozen=True, slots=True)
class Modifiers:
    """O que uma peça muda no combate, em porcento sobre a base."""

    damage_percent: int = 0
    max_hp_percent: int = 0
    coin_percent: int = 0
    #: Desconto no preço dos poderes.
    power_discount_percent: int = 0

    def __add__(self, other: Modifiers) -> Modifiers:
        return Modifiers(
            damage_percent=self.damage_percent + other.damage_percent,
            max_hp_percent=self.max_hp_percent + other.max_hp_percent,
            coin_percent=self.coin_percent + other.coin_percent,
            power_discount_percent=self.power_discount_percent + other.power_discount_percent,
        )


@dataclass(frozen=True, slots=True)
class ClassSpec:
    slug: str
    name: str
    description: str
    #: A troca declarada por escrito. Toda classe ganha de um lado e perde do
    #: outro: uma classe só melhor que as outras não seria escolha.
    tradeoff: str
    modifiers: Modifiers


#: Quatro classes, livres para qualquer candidato. **Nenhuma é destravada por
#: nível, liga ou pagamento** (itens 3 e 24 da gamificação): elas são estilo de
#: jogo, e estilo de jogo não se conquista, se escolhe.
#:
#: A primeira é neutra de propósito. Quem nunca escolheu classe joga o combate
#: base, e é contra ele que as trocas das outras três são declaradas — um padrão
#: que já desse vantagem esconderia a comparação.
CLASSES: tuple[ClassSpec, ...] = (
    ClassSpec(
        "recruta",
        "Recruta",
        "O combate sem especialização — a régua com que todas as outras se comparam.",
        "Nenhuma vantagem e nenhuma perda.",
        Modifiers(),
    ),
    ClassSpec(
        "guardiao",
        "Guardião",
        "Aguenta mais erros antes de cair.",
        "+30% de vida, −15% de dano.",
        Modifiers(max_hp_percent=30, damage_percent=-15),
    ),
    ClassSpec(
        "duelista",
        "Duelista",
        "Derruba o inimigo mais rápido, e erra com mais custo.",
        "+25% de dano, −20% de vida.",
        Modifiers(damage_percent=25, max_hp_percent=-20),
    ),
    ClassSpec(
        "estrategista",
        "Estrategista",
        "Vive de poderes: mais moedas e preços menores.",
        "+40% de moedas e −25% no preço dos poderes; vida e dano de base.",
        Modifiers(coin_percent=40, power_discount_percent=25),
    ),
)

CLASSES_BY_SLUG: dict[str, ClassSpec] = {item.slug: item for item in CLASSES}
DEFAULT_CLASS = CLASSES[0]


class EquipmentSlot(StrEnum):
    WEAPON = "WEAPON"
    ARMOR = "ARMOR"
    TRINKET = "TRINKET"


@dataclass(frozen=True, slots=True)
class EquipmentSpec:
    slug: str
    name: str
    slot: str
    description: str
    modifiers: Modifiers
    #: Conquista que libera a peça. ``None`` é o equipamento inicial, que todo
    #: mundo já tem — ninguém entra na batalha desarmado.
    requires_achievement: str | None = None


#: Equipamento é **conquistado, nunca sorteado nem comprado**: cada peça pede uma
#: conquista que já existia na plataforma, medida em estudo real. Não há caixa de
#: recompensa, raridade nem loja (item 34 da gamificação).
EQUIPMENT: tuple[EquipmentSpec, ...] = (
    EquipmentSpec(
        "espada-simples",
        "Espada simples",
        EquipmentSlot.WEAPON,
        "A arma com que todo mundo começa.",
        Modifiers(),
    ),
    EquipmentSpec(
        "lamina-do-acerto",
        "Lâmina do Acerto",
        EquipmentSlot.WEAPON,
        "Forjada em mil questões respondidas.",
        Modifiers(damage_percent=10),
        requires_achievement="mil-questoes",
    ),
    EquipmentSpec(
        "gladio-do-atirador",
        "Gládio do Atirador",
        EquipmentSlot.WEAPON,
        "Recompensa de quem acerta com precisão sustentada.",
        Modifiers(damage_percent=15, coin_percent=-10),
        requires_achievement="atirador-de-elite",
    ),
    EquipmentSpec(
        "gibao-de-couro",
        "Gibão de couro",
        EquipmentSlot.ARMOR,
        "A proteção com que todo mundo começa.",
        Modifiers(),
    ),
    EquipmentSpec(
        "cota-de-ferro",
        "Cota de Ferro",
        EquipmentSlot.ARMOR,
        "Sete dias seguidos de estudo útil viram placas.",
        Modifiers(max_hp_percent=15),
        requires_achievement="disciplina-de-ferro",
    ),
    EquipmentSpec(
        "couraca-do-maratonista",
        "Couraça do Maratonista",
        EquipmentSlot.ARMOR,
        "Cem horas de foco acumuladas em aço.",
        Modifiers(max_hp_percent=25, damage_percent=-5),
        requires_achievement="cem-horas",
    ),
    EquipmentSpec(
        "amuleto-de-latao",
        "Amuleto de latão",
        EquipmentSlot.TRINKET,
        "O talismã com que todo mundo começa.",
        Modifiers(),
    ),
    EquipmentSpec(
        "sinete-do-analista",
        "Sinete do Analista",
        EquipmentSlot.TRINKET,
        "De quem volta aos próprios erros em vez de fugir deles.",
        Modifiers(coin_percent=25),
        requires_achievement="analista-de-erros",
    ),
    EquipmentSpec(
        "talisma-da-virada",
        "Talismã da Virada",
        EquipmentSlot.TRINKET,
        "Para quem transformou a pior disciplina na melhor.",
        Modifiers(power_discount_percent=20, max_hp_percent=5),
        requires_achievement="virada-de-jogo",
    ),
)

EQUIPMENT_BY_SLUG: dict[str, EquipmentSpec] = {item.slug: item for item in EQUIPMENT}

#: A peça inicial de cada espaço — a que não pede conquista nenhuma.
DEFAULT_EQUIPMENT: dict[str, EquipmentSpec] = {
    slot: next(item for item in EQUIPMENT if item.slot == slot and not item.requires_achievement)
    for slot in EquipmentSlot
}


@dataclass(frozen=True, slots=True)
class Loadout:
    """A classe e as três peças com que uma batalha foi jogada.

    Fica **congelada na rodada**, como as questões. Trocar de armadura no meio da
    batalha e ter o dano já causado recalculado faria o HP mudar sozinho — e o
    combate deixaria de ser reconstruível a partir das respostas.
    """

    class_slug: str = DEFAULT_CLASS.slug
    weapon_slug: str = "espada-simples"
    armor_slug: str = "gibao-de-couro"
    trinket_slug: str = "amuleto-de-latao"

    @property
    def modifiers(self) -> Modifiers:
        total = CLASSES_BY_SLUG.get(self.class_slug, DEFAULT_CLASS).modifiers
        for slug, slot in (
            (self.weapon_slug, EquipmentSlot.WEAPON),
            (self.armor_slug, EquipmentSlot.ARMOR),
            (self.trinket_slug, EquipmentSlot.TRINKET),
        ):
            piece = EQUIPMENT_BY_SLUG.get(slug)
            # Peça desconhecida vira a inicial: um slug inválido no banco não
            # pode derrubar a batalha de quem está estudando.
            if piece is None or piece.slot != slot:
                piece = DEFAULT_EQUIPMENT[slot]
            total = total + piece.modifiers
        return total


DEFAULT_LOADOUT = Loadout()


def resolve_loadout(
    *,
    class_slug: str | None,
    weapon_slug: str | None,
    armor_slug: str | None,
    trinket_slug: str | None,
    unlocked: set[str],
) -> Loadout:
    """Monta o loadout válido, trocando por inicial o que ainda não foi conquistado."""

    def piece(slug: str | None, slot: str) -> str:
        spec = EQUIPMENT_BY_SLUG.get(slug or "")
        if spec is None or spec.slot != slot:
            return DEFAULT_EQUIPMENT[slot].slug
        if spec.requires_achievement and spec.requires_achievement not in unlocked:
            return DEFAULT_EQUIPMENT[slot].slug
        return spec.slug

    return Loadout(
        class_slug=(class_slug if class_slug in CLASSES_BY_SLUG else DEFAULT_CLASS.slug),
        weapon_slug=piece(weapon_slug, EquipmentSlot.WEAPON),
        armor_slug=piece(armor_slug, EquipmentSlot.ARMOR),
        trinket_slug=piece(trinket_slug, EquipmentSlot.TRINKET),
    )


def _scaled(base: int, percent: int, *, minimum: int = 1) -> int:
    return max(minimum, round(base * (100 + percent) / 100))


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
        # Nunca zero: a régua é editável no banco e vira divisor da estimativa de
        # linhas. Um zero digitado no painel derrubaria a tela de batalha.
        if viewport == Viewport.MOBILE:
            return max(1, self.chars_per_line_mobile)
        if viewport == Viewport.TABLET:
            return max(1, self.chars_per_line_tablet)
        return max(1, self.chars_per_line_desktop)


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


def stable_choice(seed: str, options: list[str]) -> str:
    """Uma escolha estável dentro de uma lista — leitura pública do mesmo hash.

    A mesma questão elimina sempre a mesma alternativa: se a escolha mudasse a
    cada uso, o poder viraria sorteio e a tela mostraria coisas diferentes para
    a mesma jogada.
    """
    return options[_stable_index(seed, len(options))]


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
    #: Tempo real gasto na questão. É o que decide o crítico — e por isso o
    #: crítico não é sorteado: sorteio daria HP diferente a cada leitura da
    #: mesma batalha, e o combate deixaria de ser reconstruível.
    time_seconds: int = 0
    #: Havia escudo ativo nesta questão quando ela foi respondida.
    shielded: bool = False


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    """O que uma resposta produziu no combate, questão a questão."""

    index: int
    is_correct: bool
    damage: int
    #: Quem levou o dano. ``None`` quando o escudo absorveu o golpe.
    damage_target: str | None
    combo: int
    is_critical: bool
    shielded: bool
    coins: int


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
    #: Sequência de acertos em curso e a maior da batalha.
    combo: int = 0
    best_combo: int = 0
    #: Moedas ganhas menos gastas. Também derivadas — não há saldo guardado.
    coins: int = 0
    coins_earned: int = 0
    coins_spent: int = 0
    criticals: int = 0
    outcomes: list[AnswerOutcome] = field(default_factory=list)
    #: O loadout com que a batalha foi jogada, congelado na largada.
    loadout: Loadout = DEFAULT_LOADOUT

    @property
    def last_outcome(self) -> AnswerOutcome | None:
        return self.outcomes[-1] if self.outcomes else None

    @property
    def player_hp_ratio(self) -> float:
        return round(self.player_hp / self.player_max_hp, 4) if self.player_max_hp else 0.0

    @property
    def enemy_hp_ratio(self) -> float:
        return round(self.enemy_hp / self.enemy_max_hp, 4) if self.enemy_max_hp else 0.0


def _combo_steps(streak: int, settings: CombatSettings) -> int:
    """Degraus de combo que ainda contam — a sequência tem teto."""
    return max(0, min(streak - 1, settings.max_combo_steps))


def player_damage(
    *,
    streak: int,
    is_critical: bool,
    settings: CombatSettings = DEFAULT_COMBAT_SETTINGS,
    loadout: Loadout = DEFAULT_LOADOUT,
) -> int:
    """Dano de um acerto: base, mais combo, mais crítico, mais equipamento.

    Tudo aqui é função dos dados da resposta e do loadout congelado na rodada.
    Não há sorteio em lugar nenhum — o mesmo conjunto de respostas produz sempre
    o mesmo dano, que é o que permite reconstruir a batalha em toda leitura em
    vez de guardar HP.
    """
    bonus = _combo_steps(streak, settings) * settings.combo_damage_percent
    if is_critical:
        bonus += settings.critical_bonus_percent
    base = PLAYER_DAMAGE * (100 + bonus) / 100
    return _scaled(round(base), loadout.modifiers.damage_percent)


def player_max_hp(loadout: Loadout = DEFAULT_LOADOUT) -> int:
    """Vida do guerreiro depois da classe e da armadura."""
    return _scaled(PLAYER_MAX_HP, loadout.modifiers.max_hp_percent, minimum=MONSTER_DAMAGE)


def coins_for(
    *,
    streak: int,
    settings: CombatSettings = DEFAULT_COMBAT_SETTINGS,
    loadout: Loadout = DEFAULT_LOADOUT,
) -> int:
    """Moedas de um acerto. Errar não tira moeda: já custou vida."""
    base = (
        settings.coins_per_correct + _combo_steps(streak, settings) * settings.coins_per_combo_step
    )
    return _scaled(base, loadout.modifiers.coin_percent, minimum=0)


def power_cost(power: str, *, settings: CombatSettings, loadout: Loadout) -> int:
    """Preço de um poder já com o desconto da classe e do amuleto."""
    return _scaled(settings.cost_of(power), -loadout.modifiers.power_discount_percent, minimum=0)


def evaluate_battle(
    answers: list[BattleAnswer],
    *,
    questions: int,
    settings: CombatSettings = DEFAULT_COMBAT_SETTINGS,
    coins_spent: int = 0,
    loadout: Loadout = DEFAULT_LOADOUT,
    boss_hp_percent: int = 0,
) -> BattleStatus:
    """Reconstrói o combate a partir das respostas — a única fonte de verdade."""
    max_hp = _scaled(enemy_max_hp(questions), boss_hp_percent)
    enemy_hp = max_hp
    max_player_hp = player_max_hp(loadout)
    player_hp = max_player_hp

    streak = 0
    best_combo = 0
    criticals = 0
    earned = 0
    outcomes: list[AnswerOutcome] = []

    for index, answer in enumerate(answers):
        if answer.is_correct:
            streak += 1
            best_combo = max(best_combo, streak)
            critical = answer.time_seconds > 0 and answer.time_seconds <= settings.critical_seconds
            criticals += 1 if critical else 0
            damage = player_damage(
                streak=streak, is_critical=critical, settings=settings, loadout=loadout
            )
            enemy_hp = max(0, enemy_hp - damage)
            coins = coins_for(streak=streak, settings=settings, loadout=loadout)
            earned += coins
            outcomes.append(
                AnswerOutcome(
                    index=index,
                    is_correct=True,
                    damage=damage,
                    damage_target="enemy",
                    combo=streak,
                    is_critical=critical,
                    shielded=False,
                    coins=coins,
                )
            )
            continue

        streak = 0
        # O escudo absorve o golpe inteiro — é para isso que ele foi comprado.
        damage = 0 if answer.shielded else MONSTER_DAMAGE
        player_hp = max(0, player_hp - damage)
        outcomes.append(
            AnswerOutcome(
                index=index,
                is_correct=False,
                damage=damage,
                damage_target=None if answer.shielded else "player",
                combo=0,
                is_critical=False,
                shielded=answer.shielded,
                coins=0,
            )
        )

    correct = sum(1 for item in answers if item.is_correct)
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
        player_max_hp=max_player_hp,
        enemy_hp=enemy_hp,
        enemy_max_hp=max_hp,
        answered=len(answers),
        correct=correct,
        wrong=len(answers) - correct,
        questions=questions,
        is_over=victory or defeat or exhausted,
        victory=victory,
        defeat=defeat,
        outcome_reason=reason,
        combo=streak,
        best_combo=best_combo,
        coins=settings.starting_coins + earned - coins_spent,
        coins_earned=earned,
        coins_spent=coins_spent,
        criticals=criticals,
        outcomes=outcomes,
        loadout=loadout,
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
