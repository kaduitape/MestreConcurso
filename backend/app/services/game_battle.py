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

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.game.battle import (
    DEFAULT_LAYOUT_SETTINGS,
    AnswerMonster,
    BattleAnswer,
    BattleStatus,
    LayoutSettings,
    MonsterSpecies,
    Viewport,
    evaluate_battle,
    monsters_for,
    select_battle_layout,
    species_for,
)
from app.domain.game.challenges import ChallengeMode
from app.models.game import BattleSetting
from app.models.question import Question
from app.models.user import User
from app.repositories.game import BattleSettingRepository
from app.services.game_challenges import ChallengeService, RunView

logger = get_logger(__name__)

#: Rótulos das chaves de configuração, para o painel administrativo explicar
#: o que cada régua faz em vez de mostrar um número solto.
SETTING_LABELS: dict[str, str] = {
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


class BattleService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.challenges = ChallengeService(session)
        self.settings = BattleSettingRepository(session)

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
            self.session.add(
                BattleSetting(
                    key=key,
                    value=int(getattr(DEFAULT_LAYOUT_SETTINGS, key)),
                    label=label,
                )
            )
            created += 1
        if created:
            await self.session.commit()
            logger.info("battle.settings_seeded", created=created)
        return created

    async def layout_settings(self) -> LayoutSettings:
        """As réguas vigentes: a tabela vence sobre o padrão de fábrica."""
        await self.sync_settings()
        stored = {item.key: item.value for item in await self.settings.all_settings()}
        return LayoutSettings(
            **{
                key: stored.get(key, int(getattr(DEFAULT_LAYOUT_SETTINGS, key)))
                for key in SETTING_LABELS
            }
        )

    # ------------------------------------------------------------------ #
    # Visão da batalha
    # ------------------------------------------------------------------ #
    async def _status(self, view: RunView) -> BattleStatus:
        rows = await self.challenges.answers_of(view.run)
        return evaluate_battle(
            [BattleAnswer(is_correct=bool(item.is_correct)) for item in rows],
            questions=view.spec.questions,
        )

    def _build(
        self,
        view: RunView,
        status: BattleStatus,
        settings: LayoutSettings,
        *,
        viewport: str,
        question: Question | None,
    ) -> BattleView:
        # A espécie sai do identificador da rodada: o mesmo inimigo do começo ao
        # fim, sem precisar guardar nada.
        enemy = species_for(view.run.public_id)

        letters = [item.letter for item in question.alternatives] if question else []
        decision = select_battle_layout(
            [item.content for item in question.alternatives] if question else [],
            viewport=viewport,
            settings=settings,
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
        )

    async def view(
        self, user: User, public_id: str, *, viewport: str = Viewport.DESKTOP
    ) -> BattleView:
        """Estado atual da batalha, já com o layout decidido para a questão."""
        run_view = await self.challenges.view(user, public_id)
        settings = await self.layout_settings()
        status = await self._status(run_view)
        return self._build(
            run_view, status, settings, viewport=viewport, question=run_view.question
        )

    async def start(self, user: User, *, viewport: str = Viewport.DESKTOP) -> BattleView:
        """Abre a batalha reaproveitando a largada das rodadas de desafio."""
        run_view = await self.challenges.start(user, ChallengeMode.BATTLE)
        settings = await self.layout_settings()
        status = await self._status(run_view)
        logger.info("battle.started", user=user.public_id, run=run_view.run.public_id)
        return self._build(
            run_view, status, settings, viewport=viewport, question=run_view.question
        )

    async def current(self, user: User, *, viewport: str = Viewport.DESKTOP) -> BattleView | None:
        run = await self.challenges.runs.running_for(user.id)
        if run is None or run.mode != "BATTLE":
            return None
        return await self.view(user, run.public_id, viewport=viewport)
