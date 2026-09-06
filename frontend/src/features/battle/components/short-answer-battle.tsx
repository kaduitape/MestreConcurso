import { cn } from '@/lib/utils'
import type { Alternative, BattleMonster } from '@/lib/api/types'
import type { BattleMachineState } from '../machine'
import { canSelect, letterTone } from '../machine'
import { Monster, type MonsterMood } from './monster'
import { LetterPlate, MonsterHealth } from './monster-hp'

const TONE_RING: Record<string, string> = {
  idle: 'border-game-gold/25 hover:border-game-gold/60',
  selected: 'border-game-purple',
  correct: 'border-success bg-success-soft/10',
  wrong: 'border-danger bg-danger-soft/10',
}

/**
 * Modelo 1 — arena. Alternativas curtas: um monstro grande por alternativa.
 *
 * A região inteira é o botão: barra de vida, monstro, letra e texto. Alvo grande
 * importa mais no celular do que qualquer efeito — errar o toque numa batalha
 * custa uma questão.
 */
export function ShortAnswerBattle({
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
              'battle-frame flex min-h-[11rem] flex-col items-center justify-end gap-1.5 p-3',
              'text-center transition-colors',
              'disabled:cursor-default focus-visible:outline-2 focus-visible:outline-offset-2',
              'focus-visible:outline-game-purple-light',
              TONE_RING[tone],
            )}
          >
            {/* A vida fica logo acima do monstro, colada nele: uma barra solta
                no topo do card pareceria pertencer à alternativa inteira, e ela
                é do monstro. */}
            <MonsterHealth letter={alternative.letter} state={state} monsterHp={monsterHp} />
            {monster && <Monster monster={monster} mood={mood} />}
            <LetterPlate letter={alternative.letter} tone={tone} />
            <span className="text-sm leading-snug font-medium text-balance">
              {alternative.content}
            </span>
          </button>
        )
      })}
    </div>
  )
}
