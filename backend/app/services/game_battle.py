"""Batalha RPG — a visão de combate de uma rodada de desafio.

Este serviço **não** duplica nada da mecânica de rodadas. Ele lê uma ``GameRun``
do modo ``BATTLE`` — criada, respondida e encerrada pelo mesmo `ChallengeService`
da Fase 3 — e acrescenta a camada que só a batalha precisa: quem é o inimigo,
quanto de vida sobrou dos dois lados e qual layout a questão pede.

O HP não é guardado em lugar nenhum. Ele é derivado das respostas, como todo o
resto do estado de uma rodada: um contador paralelo poderia divergir do que o
candidato de fato respondeu, e aí o combate mentiria sobre o estudo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.game.achievements import ACHIEVEMENTS_BY_SLUG
from app.domain.game.battle import (
    CLASSES,
    CLASSES_BY_SLUG,
    DEFAULT_COMBAT_SETTINGS,
    DEFAULT_LAYOUT_SETTINGS,
    DEFAULT_LOADOUT,
    EQUIPMENT_BY_SLUG,
    POWER_DESCRIPTIONS,
    POWER_LABELS,
    AnswerMonster,
    BattleAnswer,
    BattlePower,
    BattleStatus,
    ClassSpec,
    CombatSettings,
    EquipmentSpec,
    LayoutSettings,
    Loadout,
    MonsterSpecies,
    Viewport,
    evaluate_battle,
    monsters_for,
    power_cost,
    resolve_loadout,
    select_battle_layout,
    species_for,
    stable_choice,
)
from app.domain.game.battle import EQUIPMENT as EQUIPMENT_CATALOGUE
from app.domain.game.battle_campaign import (
    MAX_STAGES,
    BattleRanking,
    Campaign,
    RankingEntry,
    StageInput,
    build_campaign,
    build_ranking,
)
from app.domain.game.challenges import MODES_BY_KEY, ChallengeMode
from app.models.catalog import Subject
from app.models.game import (
    Achievement,
    BattleLoadout,
    BattlePowerUse,
    BattleRunLoadout,
    BattleSetting,
    GameRun,
    GamificationProfile,
    UserAchievement,
)
from app.models.intelligence import UserPriority
from app.models.question import Question, QuestionStatus
from app.models.study import StudyPlan, StudyPlanStatus
from app.models.user import User
from app.repositories.game import (
    BattleLoadoutRepository,
    BattlePowerUseRepository,
    BattleRunLoadoutRepository,
    BattleSettingRepository,
)
from app.services.game_challenges import ChallengeService, RunView
from app.services.game_seasons import SeasonService

logger = get_logger(__name__)

#: Questões de uma batalha de chefe — lido do próprio modo, não redigitado.
BOSS_QUESTIONS = MODES_BY_KEY[ChallengeMode.BATTLE_BOSS].questions

#: Rótulos das chaves de configuração, para o painel administrativo explicar
#: o que cada régua faz em vez de mostrar um número solto.
LAYOUT_LABELS: dict[str, str] = {
    "short_answer_max": "Maior alternativa que ainda cabe na arena (desktop)",
    "short_average_max": "Média de caracteres que ainda cabe na arena (desktop)",
    "tablet_short_answer_max": "Maior alternativa que ainda cabe na arena (tablet)",
    "tablet_short_average_max": "Média de caracteres que ainda cabe na arena (tablet)",
    "mobile_short_answer_max": "Maior alternativa que ainda cabe na arena (celular)",
    "mobile_short_average_max": "Média de caracteres que ainda cabe na arena (celular)",
    "max_options_for_arena": "Máximo de alternativas na arena",
    "chars_per_line_desktop": "Caracteres por linha do card (desktop)",
    "chars_per_line_tablet": "Caracteres por linha do card (tablet)",
    "chars_per_line_mobile": "Caracteres por linha do card (celular)",
    "max_lines_for_arena": "Linhas de texto que ainda cabem embaixo do monstro",
}

#: Réguas do combate (Fase 2). Ficam na mesma tabela pelo mesmo motivo: o preço
#: de um escudo e o tempo que faz um acerto ser "rápido" são decisões de
#: produto, e produto muda sem deploy.
COMBAT_LABELS: dict[str, str] = {
    "critical_seconds": "Tempo máximo de um acerto para valer crítico (segundos)",
    "critical_bonus_percent": "Dano extra do crítico (%)",
    "combo_damage_percent": "Dano extra por degrau de combo (%)",
    "max_combo_steps": "Degraus de combo que ainda contam",
    "coins_per_correct": "Moedas por acerto",
    "coins_per_combo_step": "Moedas extras por degrau de combo",
    "starting_coins": "Moedas com que a batalha começa",
    "shield_cost": "Preço do Escudo",
    "eliminate_cost": "Preço do Eliminar",
    "hint_cost": "Preço da Dica",
    "boss_hp_percent": "Vida extra do chefe (%)",
}

SETTING_LABELS: dict[str, str] = {**LAYOUT_LABELS, **COMBAT_LABELS}


@dataclass(frozen=True, slots=True)
class PowerOffer:
    """Um poder como a tela precisa vê-lo: preço, se cabe no bolso, e o que fez."""

    power: str
    label: str
    description: str
    cost: int
    affordable: bool
    used: bool
    #: O que o poder revelou nesta questão, quando já foi usado.
    removed_letter: str | None = None
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class EquipmentOffer:
    """Uma peça do arsenal, com o motivo de estar travada quando estiver."""

    spec: EquipmentSpec
    is_unlocked: bool
    #: Nome da conquista que libera a peça, para a tela dizer o caminho.
    requirement_label: str | None = None


@dataclass(frozen=True, slots=True)
class ArmoryView:
    loadout: Loadout
    classes: list[ClassSpec] = field(default_factory=list)
    equipment: list[EquipmentOffer] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BattleView:
    """A rodada, vista como combate."""

    run: RunView
    status: BattleStatus
    enemy: MonsterSpecies
    monsters: list[AnswerMonster]
    layout: str
    layout_reason: str
    settings: LayoutSettings
    combat: CombatSettings
    powers: list[PowerOffer] = field(default_factory=list)
    #: Letras escondidas pelo ELIMINAR nesta questão.
    removed_letters: list[str] = field(default_factory=list)
    hint: str | None = None
    loadout: Loadout = DEFAULT_LOADOUT
    #: Verdadeiro quando a rodada é um chefe de campanha.
    is_boss: bool = False


class BattleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.challenges = ChallengeService(session)
        self.settings = BattleSettingRepository(session)
        self.power_uses = BattlePowerUseRepository(session)
        self.loadouts = BattleLoadoutRepository(session)
        self.run_loadouts = BattleRunLoadoutRepository(session)

    # ------------------------------------------------------------------ #
    # Configuração
    # ------------------------------------------------------------------ #
    async def sync_settings(self) -> int:
        """Semeia as réguas de fábrica que ainda não existem no banco."""
        existing = {item.key for item in await self.settings.all_settings()}
        created = 0
        for key, label in SETTING_LABELS.items():
            if key in existing:
                continue
            factory = DEFAULT_LAYOUT_SETTINGS if key in LAYOUT_LABELS else DEFAULT_COMBAT_SETTINGS
            self.session.add(BattleSetting(key=key, value=int(getattr(factory, key)), label=label))
            created += 1
        if created:
            await self.session.commit()
            logger.info("battle.settings_seeded", created=created)
        return created

    async def _stored(self) -> dict[str, int]:
        await self.sync_settings()
        return {item.key: item.value for item in await self.settings.all_settings()}

    async def layout_settings(self) -> LayoutSettings:
        """As réguas de layout vigentes: a tabela vence sobre o padrão de fábrica."""
        stored = await self._stored()
        return LayoutSettings(
            **{
                key: stored.get(key, int(getattr(DEFAULT_LAYOUT_SETTINGS, key)))
                for key in LAYOUT_LABELS
            }
        )

    async def combat_settings(self) -> CombatSettings:
        """As réguas de combate vigentes — combo, crítico, moedas e preços."""
        stored = await self._stored()
        return CombatSettings(
            **{
                key: stored.get(key, int(getattr(DEFAULT_COMBAT_SETTINGS, key)))
                for key in COMBAT_LABELS
            }
        )

    # ------------------------------------------------------------------ #
    # Visão da batalha
    # ------------------------------------------------------------------ #
    async def _status(
        self,
        view: RunView,
        combat: CombatSettings,
        uses: Sequence[BattlePowerUse],
        loadout: Loadout,
    ) -> BattleStatus:
        """Reconstrói o combate a partir das respostas e dos poderes gastos.

        As respostas dizem o dano; os poderes dizem o que foi absorvido e o que
        foi pago. Nada além disso é guardado: HP, combo e saldo saem daqui a
        cada leitura, e por isso não têm como divergir do que aconteceu.
        """
        rows = await self.challenges.answers_of(view.run)
        shielded = {item.question_id for item in uses if item.power == BattlePower.SHIELD}
        question_ids = list(view.run.question_ids or [])

        answers = [
            BattleAnswer(
                is_correct=bool(item.is_correct),
                time_seconds=int(item.time_seconds or 0),
                shielded=(question_ids[index] in shielded if index < len(question_ids) else False),
            )
            for index, item in enumerate(rows)
        ]
        return evaluate_battle(
            answers,
            questions=view.spec.questions,
            settings=combat,
            coins_spent=sum(item.cost for item in uses),
            loadout=loadout,
            boss_hp_percent=(
                combat.boss_hp_percent if view.run.mode == ChallengeMode.BATTLE_BOSS else 0
            ),
        )

    def _offers(
        self,
        *,
        combat: CombatSettings,
        coins: int,
        question: Question | None,
        uses: Sequence[BattlePowerUse],
        loadout: Loadout,
    ) -> tuple[list[PowerOffer], list[str], str | None]:
        """Os três poderes na questão corrente, com preço e o que já revelaram."""
        current = (
            {item.power: item for item in uses if item.question_id == question.id}
            if question
            else {}
        )
        offers: list[PowerOffer] = []
        for power in (BattlePower.SHIELD, BattlePower.ELIMINATE, BattlePower.HINT):
            used = current.get(power)
            cost = power_cost(power, settings=combat, loadout=loadout)
            offers.append(
                PowerOffer(
                    power=power,
                    label=POWER_LABELS[power],
                    description=POWER_DESCRIPTIONS[power],
                    cost=cost,
                    affordable=coins >= cost,
                    used=used is not None,
                    removed_letter=used.removed_letter if used else None,
                    hint=used.hint if used else None,
                )
            )

        removed = [
            item.removed_letter
            for item in current.values()
            if item.power == BattlePower.ELIMINATE and item.removed_letter
        ]
        hint_row = current.get(BattlePower.HINT)
        return offers, removed, (hint_row.hint if hint_row else None)

    def _build(
        self,
        view: RunView,
        status: BattleStatus,
        settings: LayoutSettings,
        combat: CombatSettings,
        uses: Sequence[BattlePowerUse],
        loadout: Loadout,
        *,
        viewport: str,
        question: Question | None,
    ) -> BattleView:
        # A espécie sai do identificador da rodada: o mesmo inimigo do começo ao
        # fim, sem precisar guardar nada.
        enemy = species_for(view.run.public_id)

        offers, removed, hint = self._offers(
            combat=combat, coins=status.coins, question=question, uses=uses, loadout=loadout
        )

        # A alternativa eliminada sai da conta do layout também: decidir a arena
        # por um texto que não vai aparecer daria a resposta errada.
        visible = (
            [item for item in question.alternatives if item.letter not in removed]
            if question
            else []
        )
        letters = [item.letter for item in visible]
        decision = select_battle_layout(
            [item.content for item in visible], viewport=viewport, settings=settings
        )
        monsters = monsters_for(question.public_id, letters, enemy=enemy) if question else []

        return BattleView(
            run=view,
            status=status,
            enemy=enemy,
            monsters=monsters,
            layout=decision.layout,
            layout_reason=decision.reason,
            settings=settings,
            combat=combat,
            powers=offers,
            removed_letters=removed,
            hint=hint,
            loadout=loadout,
            is_boss=view.run.mode == ChallengeMode.BATTLE_BOSS,
        )

    async def _assemble(
        self, run_view: RunView, *, viewport: str, question: Question | None
    ) -> BattleView:
        settings = await self.layout_settings()
        combat = await self.combat_settings()
        uses = await self.power_uses.for_run(run_view.run.id)
        loadout = await self.run_loadout(run_view.run.id)
        status = await self._status(run_view, combat, uses, loadout)
        return self._build(
            run_view,
            status,
            settings,
            combat,
            uses,
            loadout,
            viewport=viewport,
            question=question,
        )

    async def run_loadout(self, run_id: int) -> Loadout:
        """O loadout congelado da rodada. Rodadas antigas usam o de base."""
        frozen = await self.run_loadouts.for_run(run_id)
        if frozen is None:
            return DEFAULT_LOADOUT
        return Loadout(
            class_slug=frozen.class_slug,
            weapon_slug=frozen.weapon_slug,
            armor_slug=frozen.armor_slug,
            trinket_slug=frozen.trinket_slug,
        )

    async def view(
        self, user: User, public_id: str, *, viewport: str = Viewport.DESKTOP
    ) -> BattleView:
        """Estado atual da batalha, já com o layout decidido para a questão."""
        run_view = await self.challenges.view(user, public_id)
        return await self._assemble(run_view, viewport=viewport, question=run_view.question)

    async def start(
        self,
        user: User,
        *,
        viewport: str = Viewport.DESKTOP,
        boss: bool = False,
        subject_public_id: str | None = None,
    ) -> BattleView:
        """Abre a batalha reaproveitando a largada das rodadas de desafio."""
        subject_id: int | None = None
        if subject_public_id:
            subject = (
                await self.session.execute(
                    select(Subject).where(Subject.public_id == subject_public_id)
                )
            ).scalar_one_or_none()
            if subject is None:
                raise NotFoundError("Disciplina não encontrada.")
            subject_id = subject.id
            boss = True

        mode = ChallengeMode.BATTLE_BOSS if boss else ChallengeMode.BATTLE
        run_view = await self.challenges.start(user, mode, subject_id=subject_id)

        # O loadout é congelado aqui, como as questões: trocar de armadura no
        # meio da batalha não pode recalcular o dano que já foi causado.
        chosen = await self.loadout_of(user)
        self.session.add(
            BattleRunLoadout(
                game_run_id=run_view.run.id,
                class_slug=chosen.class_slug,
                weapon_slug=chosen.weapon_slug,
                armor_slug=chosen.armor_slug,
                trinket_slug=chosen.trinket_slug,
            )
        )
        await self.session.commit()

        logger.info("battle.started", user=user.public_id, run=run_view.run.public_id, mode=mode)
        return await self._assemble(run_view, viewport=viewport, question=run_view.question)

    async def current(self, user: User, *, viewport: str = Viewport.DESKTOP) -> BattleView | None:
        run = await self.challenges.runs.running_for(user.id)
        if run is None or run.mode not in (ChallengeMode.BATTLE, ChallengeMode.BATTLE_BOSS):
            return None
        return await self.view(user, run.public_id, viewport=viewport)

    # ------------------------------------------------------------------ #
    # Poderes
    # ------------------------------------------------------------------ #
    @staticmethod
    def _first_sentence(text: str, *, limit: int = 180) -> str:
        """Uma pista, não a explicação inteira — e sempre texto já cadastrado."""
        clean = " ".join(text.split())
        cut = clean.find(". ")
        if 0 < cut + 1 <= limit:
            return clean[: cut + 1]
        return clean if len(clean) <= limit else clean[: limit - 1].rstrip() + "…"

    def _hint_from(self, question: Question) -> str | None:
        """A dica sai do que já existe cadastrado. Sem conteúdo, não há dica.

        Gerar um texto aqui para o poder "funcionar" seria inventar conteúdo de
        estudo — exatamente o que a plataforma não faz.
        """
        correct = next((item for item in question.alternatives if item.is_correct), None)
        for source in (question.explanation, correct.feedback if correct else None):
            if source and source.strip():
                return self._first_sentence(source)
        return None

    async def use_power(
        self, user: User, public_id: str, power: str, *, viewport: str = Viewport.DESKTOP
    ) -> BattleView:
        """Gasta moedas num poder da questão corrente."""
        if power not in set(BattlePower):
            raise NotFoundError("Poder desconhecido.")

        run_view = await self.challenges.view(user, public_id)
        if run_view.run.status != "RUNNING" or run_view.question is None:
            raise ConflictError("Esta batalha já terminou.", code="battle_over")

        question = run_view.question
        combat = await self.combat_settings()
        uses = await self.power_uses.for_run(run_view.run.id)
        loadout = await self.run_loadout(run_view.run.id)
        status = await self._status(run_view, combat, uses, loadout)

        if any(item.question_id == question.id and item.power == power for item in uses):
            raise ConflictError("Este poder já foi usado nesta questão.", code="power_used")

        cost = power_cost(power, settings=combat, loadout=loadout)
        if status.coins < cost:
            raise ConflictError(
                f"Faltam {cost - status.coins} moeda(s) para este poder.",
                code="not_enough_coins",
            )

        removed_letter: str | None = None
        hint: str | None = None

        if power == BattlePower.ELIMINATE:
            already = {
                item.removed_letter
                for item in uses
                if item.question_id == question.id and item.removed_letter
            }
            wrong = sorted(
                item.letter
                for item in question.alternatives
                if not item.is_correct and item.letter not in already
            )
            if not wrong:
                raise ConflictError(
                    "Não há alternativa incorreta para eliminar nesta questão.",
                    code="nothing_to_eliminate",
                )
            # Escolha estável: a mesma questão elimina sempre a mesma letra.
            removed_letter = stable_choice(f"{question.public_id}:eliminate", wrong)

        elif power == BattlePower.HINT:
            hint = self._hint_from(question)
            if hint is None:
                # Sem conteúdo cadastrado não há cobrança: o candidato não paga
                # por um poder que não tem o que entregar.
                raise ConflictError(
                    "Esta questão não tem explicação cadastrada, então não há dica a mostrar.",
                    code="no_hint_available",
                )

        self.session.add(
            BattlePowerUse(
                game_run_id=run_view.run.id,
                question_id=question.id,
                power=power,
                cost=cost,
                removed_letter=removed_letter,
                hint=hint,
            )
        )
        await self.session.commit()
        logger.info(
            "battle.power_used",
            user=user.public_id,
            run=run_view.run.public_id,
            power=power,
            cost=cost,
        )
        return await self.view(user, public_id, viewport=viewport)

    # ------------------------------------------------------------------ #
    # Classe e equipamento
    # ------------------------------------------------------------------ #
    async def _unlocked(self, user: User) -> set[str]:
        """As conquistas que o candidato já tem — a única chave dos equipamentos."""
        rows = (
            await self.session.execute(
                select(Achievement.slug)
                .join(UserAchievement, UserAchievement.achievement_id == Achievement.id)
                .where(UserAchievement.user_id == user.id)
            )
        ).scalars()
        return set(rows)

    async def loadout_of(self, user: User) -> Loadout:
        """A escolha do candidato, já filtrada pelo que ele de fato conquistou.

        Peça ainda não conquistada volta a ser a inicial em vez de virar erro: o
        equipamento é enfeite de combate, e enfeite não pode impedir alguém de
        estudar.
        """
        stored = await self.loadouts.for_user(user.id)
        if stored is None:
            return DEFAULT_LOADOUT
        return resolve_loadout(
            class_slug=stored.class_slug,
            weapon_slug=stored.weapon_slug,
            armor_slug=stored.armor_slug,
            trinket_slug=stored.trinket_slug,
            unlocked=await self._unlocked(user),
        )

    async def armory(self, user: User) -> ArmoryView:
        """O arsenal: classes, peças, o que está travado e por qual conquista."""
        unlocked = await self._unlocked(user)
        current = await self.loadout_of(user)
        return ArmoryView(
            loadout=current,
            classes=list(CLASSES),
            equipment=[
                EquipmentOffer(
                    spec=item,
                    is_unlocked=item.requires_achievement is None
                    or item.requires_achievement in unlocked,
                    requirement_label=(
                        ACHIEVEMENTS_BY_SLUG[item.requires_achievement].name
                        if item.requires_achievement in ACHIEVEMENTS_BY_SLUG
                        else None
                    ),
                )
                for item in EQUIPMENT_CATALOGUE
            ],
        )

    async def set_loadout(
        self,
        user: User,
        *,
        class_slug: str | None,
        weapon_slug: str | None,
        armor_slug: str | None,
        trinket_slug: str | None,
    ) -> ArmoryView:
        """Grava a escolha. Peça não conquistada é recusada, dizendo o motivo."""
        unlocked = await self._unlocked(user)
        for slug in (weapon_slug, armor_slug, trinket_slug):
            spec = EQUIPMENT_BY_SLUG.get(slug or "")
            if spec is None:
                raise NotFoundError("Equipamento desconhecido.")
            if spec.requires_achievement and spec.requires_achievement not in unlocked:
                required = ACHIEVEMENTS_BY_SLUG.get(spec.requires_achievement)
                raise ConflictError(
                    (
                        f"{spec.name} é liberado pela conquista "
                        f"“{required.name if required else spec.requires_achievement}”, "
                        "que você ainda não tem."
                    ),
                    code="equipment_locked",
                )
        if class_slug not in CLASSES_BY_SLUG:
            raise NotFoundError("Classe desconhecida.")

        stored = await self.loadouts.for_user(user.id)
        if stored is None:
            stored = BattleLoadout(user_id=user.id)
            self.session.add(stored)
        stored.class_slug = class_slug
        stored.weapon_slug = weapon_slug or DEFAULT_LOADOUT.weapon_slug
        stored.armor_slug = armor_slug or DEFAULT_LOADOUT.armor_slug
        stored.trinket_slug = trinket_slug or DEFAULT_LOADOUT.trinket_slug
        await self.session.commit()
        logger.info("battle.loadout_saved", user=user.public_id, klass=stored.class_slug)
        return await self.armory(user)

    # ------------------------------------------------------------------ #
    # Campanha
    # ------------------------------------------------------------------ #
    async def campaign(self, user: User) -> Campaign:
        """O mapa da campanha, derivado do Priority Score e das rodadas reais.

        Nada aqui é conteúdo novo: os estágios são as disciplinas fracas que a
        Inteligência já calculou, e um estágio é vencido quando existe uma
        batalha de chefe encerrada nela com acerto suficiente. **Nenhum estágio
        tranca outro** — quem quiser começar pelo terceiro pode.
        """
        priorities = list(
            (
                await self.session.execute(
                    select(UserPriority)
                    .where(UserPriority.user_id == user.id, UserPriority.subject_id.is_not(None))
                    .order_by(UserPriority.score.desc(), UserPriority.label)
                    .limit(MAX_STAGES)
                )
            )
            .scalars()
            .all()
        )
        if not priorities:
            return build_campaign([], required_questions=BOSS_QUESTIONS)

        subject_ids = [item.subject_id for item in priorities]
        subjects = {
            item.id: item
            for item in (
                await self.session.execute(select(Subject).where(Subject.id.in_(subject_ids)))
            )
            .scalars()
            .all()
        }

        runs = (
            await self.session.execute(
                select(
                    GameRun.subject_id,
                    func.count(GameRun.id),
                    func.coalesce(func.sum(case((GameRun.achieved.is_(True), 1), else_=0)), 0),
                )
                .where(
                    GameRun.user_id == user.id,
                    GameRun.mode == ChallengeMode.BATTLE_BOSS,
                    GameRun.status == "FINISHED",
                    GameRun.subject_id.in_(subject_ids),
                )
                .group_by(GameRun.subject_id)
            )
        ).all()
        played = {row[0]: (int(row[1]), int(row[2] or 0)) for row in runs}

        available = {
            row[0]: int(row[1])
            for row in (
                await self.session.execute(
                    select(Question.subject_id, func.count(Question.id))
                    .where(
                        Question.subject_id.in_(subject_ids),
                        Question.status == QuestionStatus.PUBLISHED,
                    )
                    .group_by(Question.subject_id)
                )
            ).all()
        }

        stages: list[StageInput] = []
        for item in priorities:
            subject = subjects.get(item.subject_id or 0)
            if subject is None:
                continue
            battles, cleared = played.get(item.subject_id, (0, 0))
            stages.append(
                StageInput(
                    subject_id=subject.id,
                    subject_public_id=subject.public_id,
                    label=item.label or subject.name,
                    priority_score=float(item.score),
                    battles=battles,
                    cleared_battles=cleared,
                    questions_available=available.get(subject.id, 0),
                )
            )
        return build_campaign(stages, required_questions=BOSS_QUESTIONS)

    # ------------------------------------------------------------------ #
    # Ranking
    # ------------------------------------------------------------------ #
    async def ranking(self, user: User) -> BattleRanking:
        """A tabela do contexto do candidato, ordenada por acerto — não por dano."""
        profile = await self.challenges.engine.profile_for(user)
        if profile.league_opt_out:
            return BattleRanking(
                context_label="",
                participants=0,
                empty_reason=(
                    "Você desligou a comparação com outros candidatos. Nada da sua batalha "
                    "depende dela — ligue quando quiser."
                ),
            )

        position_id, context_label = await SeasonService(self.session).context_of(user)
        if position_id is None:
            return BattleRanking(
                context_label="",
                participants=0,
                empty_reason=(
                    "O ranking compara candidatos ao mesmo cargo. Vincule seu plano a um "
                    "cargo para saber com quem você está disputando."
                ),
            )

        rows = (
            await self.session.execute(
                select(
                    User.public_id,
                    func.count(GameRun.id),
                    # "Vitória" no ranking é `achieved`: a taxa de acerto crua da
                    # rodada, a mesma que dá XP. Dano e equipamento não entram.
                    func.coalesce(func.sum(case((GameRun.achieved.is_(True), 1), else_=0)), 0),
                    func.coalesce(func.sum(GameRun.score), 0),
                    GamificationProfile.league_display_name,
                )
                .join(StudyPlan, StudyPlan.user_id == User.id)
                .join(
                    GameRun,
                    (GameRun.user_id == User.id)
                    & GameRun.mode.in_([ChallengeMode.BATTLE, ChallengeMode.BATTLE_BOSS])
                    & (GameRun.status == "FINISHED"),
                )
                .outerjoin(GamificationProfile, GamificationProfile.user_id == User.id)
                .where(
                    StudyPlan.position_id == position_id,
                    StudyPlan.status == StudyPlanStatus.ACTIVE,
                    or_(
                        GamificationProfile.id.is_(None),
                        GamificationProfile.league_opt_out.is_(False),
                    ),
                )
                .group_by(User.public_id, GamificationProfile.league_display_name)
            )
        ).all()

        entries = [
            RankingEntry(
                user_key=str(row[0]),
                battles=int(row[1]),
                wins=int(row[2] or 0),
                correct=int(row[3]),
                display_name=row[4],
            )
            for row in rows
        ]
        return build_ranking(entries, you_key=user.public_id, context_label=context_label)
