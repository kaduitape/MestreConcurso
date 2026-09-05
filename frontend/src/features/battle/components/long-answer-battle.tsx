import { cn } from '@/lib/utils'
import type { Alternative, BattleMonster } from '@/lib/api/types'
import type { BattleMachineState } from '../machine'
import { canSelect, letterTone } from '../machine'
import { SlashEffect } from './battle-hud'
import { MonsterAvatar, type MonsterMood } from './monster'

const TONE_RING: Record<string, string> = {
  idle: 'border-white/10 hover:border-game-purple/50',
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
  onSelect,
}: {
  alternatives: Alternative[]
  monsters: BattleMonster[]
  state: BattleMachineState
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
                'relative flex w-full items-start gap-3 rounded-xl border bg-white/[0.03] p-3',
                'text-left transition-colors disabled:cursor-default',
                'focus-visible:outline-2 focus-visible:outline-offset-2',
                'focus-visible:outline-game-purple-light',
                TONE_RING[tone],
              )}
            >
              {monster && <MonsterAvatar monster={monster} mood={mood} />}

              <span
                className={cn(
                  'mt-1.5 flex size-6 shrink-0 items-center justify-center rounded-full',
                  'text-xs font-black',
                  tone === 'correct'
                    ? 'bg-success text-white'
                    : tone === 'wrong'
                      ? 'bg-danger text-white'
                      : 'bg-white/10 text-slate-200',
                )}
              >
                {alternative.letter}
              </span>

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
