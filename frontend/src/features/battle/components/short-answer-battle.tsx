import { cn } from '@/lib/utils'
import type { Alternative, BattleMonster } from '@/lib/api/types'
import type { BattleMachineState } from '../machine'
import { canSelect, letterTone } from '../machine'
import { Monster, type MonsterMood } from './monster'

const TONE_RING: Record<string, string> = {
  idle: 'border-white/10 hover:border-game-purple/50',
  selected: 'border-game-purple',
  correct: 'border-success bg-success-soft/10',
  wrong: 'border-danger bg-danger-soft/10',
}

/**
 * Modelo 1 — arena. Alternativas curtas: um monstro grande por alternativa.
 *
 * A região inteira é o botão: monstro, letra e texto. Alvo grande importa mais
 * no celular do que qualquer efeito — errar o toque numa batalha custa uma
 * questão.
 */
export function ShortAnswerBattle({
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
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {alternatives.map((alternative) => {
        const tone = letterTone(state, alternative.letter)
        const monster = monsterOf(alternative.letter)

        // O monstro que apanha é o da alternativa correta quando o candidato
        // acerta; quando erra, é ele quem ataca.
        const mood: MonsterMood =
          state.correctLetter === alternative.letter
            ? state.isCorrect === true
              ? state.phase === 'DAMAGE' || state.phase === 'RESULT'
                ? 'hurt'
                : 'idle'
              : state.phase === 'ENEMY_ATTACK'
                ? 'attack'
                : 'idle'
            : 'idle'

        return (
          <button
            key={alternative.public_id}
            type="button"
            disabled={!canSelect(state)}
            onClick={() => onSelect(alternative.letter)}
            aria-pressed={state.selectedLetter === alternative.letter}
            className={cn(
              'flex min-h-[9.5rem] flex-col items-center justify-end gap-2 rounded-2xl border',
              'bg-white/[0.03] p-3 text-center transition-colors',
              'disabled:cursor-default focus-visible:outline-2 focus-visible:outline-offset-2',
              'focus-visible:outline-game-purple-light',
              TONE_RING[tone],
            )}
          >
            {monster && <Monster monster={monster} mood={mood} />}
            <span
              className={cn(
                'flex size-6 items-center justify-center rounded-full text-xs font-black',
                tone === 'correct'
                  ? 'bg-success text-white'
                  : tone === 'wrong'
                    ? 'bg-danger text-white'
                    : 'bg-white/10 text-slate-200',
              )}
            >
              {alternative.letter}
            </span>
            <span className="text-sm leading-snug font-medium text-balance">
              {alternative.content}
            </span>
          </button>
        )
      })}
    </div>
  )
}
