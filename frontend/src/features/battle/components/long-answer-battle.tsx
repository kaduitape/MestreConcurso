import { cn } from '@/lib/utils'
import type { Alternative, BattleMonster } from '@/lib/api/types'
import type { BattleMachineState } from '../machine'
import { canSelect, letterTone } from '../machine'
import { SlashEffect } from './battle-hud'
import { MonsterAvatar, type MonsterMood } from './monster'
import { LetterPlate, MonsterHealth } from './monster-hp'

const TONE_RING: Record<string, string> = {
  idle: 'border-game-gold/25 hover:border-game-gold/60',
  selected: 'border-game-purple',
  correct: 'border-success bg-success-soft/10',
  wrong: 'border-danger bg-danger-soft/10',
}

/**
 * Modelo 2 — compacto. Alternativas longas: avatar pequeno, texto inteiro.
 *
 * A regra que manda aqui é o texto. O card cresce na vertical quando precisa, a
 * fonte não encolhe para caber, e **nada que se move carrega texto junto**: na
 * hora do golpe apenas o avatar, a borda e o efeito se mexem. Mover o card
 * inteiro tiraria a linha que a pessoa está lendo de debaixo dos olhos dela.
 */
export function LongAnswerBattle({
  alternatives,
  monsters,
  state,
  monsterHp,
  onSelect,
}: {
  alternatives: Alternative[]
  monsters: BattleMonster[]
  state: BattleMachineState
  monsterHp: number
  onSelect: (letter: string) => void
}) {
  const monsterOf = (letter: string) => monsters.find((item) => item.letter === letter)

  return (
    <ul className="space-y-2.5">
      {alternatives.map((alternative) => {
        const tone = letterTone(state, alternative.letter)
        const monster = monsterOf(alternative.letter)
        const isTarget = state.correctLetter === alternative.letter

        const mood: MonsterMood = !isTarget
          ? 'idle'
          : state.isCorrect === true
            ? state.phase === 'DAMAGE' || state.phase === 'RESULT'
              ? 'hurt'
              : 'idle'
            : state.phase === 'ENEMY_ATTACK'
              ? 'attack'
              : 'idle'

        return (
          <li key={alternative.public_id}>
            <button
              type="button"
              disabled={!canSelect(state)}
              onClick={() => onSelect(alternative.letter)}
              aria-pressed={state.selectedLetter === alternative.letter}
              className={cn(
                'battle-frame relative flex w-full items-start gap-3 p-3',
                'text-left transition-colors disabled:cursor-default',
                'focus-visible:outline-2 focus-visible:outline-offset-2',
                'focus-visible:outline-game-purple-light',
                TONE_RING[tone],
              )}
            >
              {/* Avatar e vida em coluna: no modo compacto a barra é pequena,
                  porque quem manda aqui é o texto. */}
              <span className="flex shrink-0 flex-col items-center gap-1">
                {monster && <MonsterAvatar monster={monster} mood={mood} />}
                <MonsterHealth
                  letter={alternative.letter}
                  state={state}
                  monsterHp={monsterHp}
                  compact
                  className="max-w-11"
                />
              </span>

              <LetterPlate letter={alternative.letter} tone={tone} className="mt-1 shrink-0" />

              {/* O texto tem prioridade absoluta: não encolhe, não corta. */}
              <span className="min-w-0 flex-1 text-sm leading-relaxed">
                {alternative.content}
              </span>

              <SlashEffect
                visible={isTarget && state.phase === 'PLAYER_ATTACK'}
                className="left-2 -translate-y-2"
              />
            </button>
          </li>
        )
      })}
    </ul>
  )
}
