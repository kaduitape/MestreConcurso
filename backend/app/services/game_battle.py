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

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.domain.game.battle import (
    DEFAULT_COMBAT_SETTINGS,
    DEFAULT_LAYOUT_SETTINGS,
    POWER_DESCRIPTIONS,
    POWER_LABELS,
    AnswerMonster,
    BattleAnswer,
    BattlePower,
    BattleStatus,
    CombatSettings,
    LayoutSettings,
    MonsterSpecies,
    Viewport,
    evaluate_battle,
    monsters_for,
    select_battle_layout,
    species_for,
    stable_choice,
)
from app.domain.game.challenges import ChallengeMode
from app.models.game import BattlePowerUse, BattleSetting
from app.models.question import Question
from app.models.user import User
from app.repositories.game import BattlePowerUseRepository, BattleSettingRepository
from app.services.game_challenges import ChallengeService, RunView

logger = get_logger(__name__)

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


class BattleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.challenges = ChallengeService(session)
        self.settings = BattleSettingRepository(session)
        self.power_uses = BattlePowerUseRepository(session)

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
        self, view: RunView, combat: CombatSettings, uses: Sequence[BattlePowerUse]
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
        )

    def _offers(
        self,
        *,
        combat: CombatSettings,
        coins: int,
        question: Question | None,
        uses: Sequence[BattlePowerUse],
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
            cost = combat.cost_of(power)
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
        *,
        viewport: str,
        question: Question | None,
    ) -> BattleView:
        # A espécie sai do identificador da rodada: o mesmo inimigo do começo ao
        # fim, sem precisar guardar nada.
        enemy = species_for(view.run.public_id)

        offers, removed, hint = self._offers(
            combat=combat, coins=status.coins, question=question, uses=uses
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
        )

    async def _assemble(
        self, run_view: RunView, *, viewport: str, question: Question | None
    ) -> BattleView:
        settings = await self.layout_settings()
        combat = await self.combat_settings()
        uses = await self.power_uses.for_run(run_view.run.id)
        status = await self._status(run_view, combat, uses)
        return self._build(
            run_view, status, settings, combat, uses, viewport=viewport, question=question
        )

    async def view(
        self, user: User, public_id: str, *, viewport: str = Viewport.DESKTOP
    ) -> BattleView:
        """Estado atual da batalha, já com o layout decidido para a questão."""
        run_view = await self.challenges.view(user, public_id)
        return await self._assemble(run_view, viewport=viewport, question=run_view.question)

    async def start(self, user: User, *, viewport: str = Viewport.DESKTOP) -> BattleView:
        """Abre a batalha reaproveitando a largada das rodadas de desafio."""
        run_view = await self.challenges.start(user, ChallengeMode.BATTLE)
        logger.info("battle.started", user=user.public_id, run=run_view.run.public_id)
        return await self._assemble(run_view, viewport=viewport, question=run_view.question)

    async def current(self, user: User, *, viewport: str = Viewport.DESKTOP) -> BattleView | None:
        run = await self.challenges.runs.running_for(user.id)
        if run is None or run.mode != "BATTLE":
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
        status = await self._status(run_view, combat, uses)

        if any(item.question_id == question.id and item.power == power for item in uses):
            raise ConflictError("Este poder já foi usado nesta questão.", code="power_used")

        cost = combat.cost_of(power)
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
