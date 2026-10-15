import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { BattleMachineState } from '../machine'

/**
 * Cores da letra, como as placas de um tabuleiro medieval.
 *
 * A cor é só identidade — ela **não** diz se a alternativa está certa. O acerto
 * e o erro continuam saindo do verde e do vermelho depois da resposta, que é
 * onde a informação de verdade aparece.
 */
const LETTER_PLATE: Record<string, string> = {
  A: 'from-danger/80 to-danger/40 border-danger/50',
  B: 'from-game-blue/80 to-game-blue/40 border-game-blue/50',
  C: 'from-game-purple/80 to-game-purple/40 border-game-purple/50',
  D: 'from-game-gold/80 to-game-gold/40 border-game-gold/50',
  E: 'from-success/80 to-success/40 border-success/50',
}

export function LetterPlate({
  letter,
  tone,
  className,
}: {
  letter: string
  tone: 'idle' | 'selected' | 'correct' | 'wrong'
  className?: string
}) {
  return (
    <span
      className={cn(
        'flex size-7 items-center justify-center rounded-md border bg-gradient-to-b',
        'text-sm font-black text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.2)]',
        tone === 'correct'
          ? 'border-success bg-success from-success to-success'
          : tone === 'wrong'
            ? 'border-danger bg-danger from-danger to-danger'
            : (LETTER_PLATE[letter] ?? 'border-white/20 from-white/20 to-white/5'),
        className,
      )}
    >
      {letter}
    </span>
  )
}

/**
 * A vida do monstro de uma alternativa.
 *
 * Ela vale **dentro desta questão**, e mostra uma coisa só: quanto o seu golpe
 * tirou daquele monstro. A barra do topo é outra — essa atravessa a batalha
 * inteira. Dois números reais, com escopos diferentes, ditos com esse nome.
 *
 * O mesmo dano alimenta as duas: não há segunda fonte de verdade em lugar
 * nenhum.
 */
export function MonsterHealth({
  letter,
  state,
  monsterHp,
  compact,
  className,
}: {
  letter: string
  state: BattleMachineState
  monsterHp: number
  /** No modelo compacto o número sai: ali quem manda é o texto da alternativa. */
  compact?: boolean
  className?: string
}) {
  const reduce = useReducedMotion()

  // Só o monstro da alternativa correta apanha, e só quando o candidato acerta.
  const struck = state.isCorrect === true && state.correctLetter === letter
  const landed =
    struck &&
    (state.phase === 'DAMAGE' || state.phase === 'RESULT' || state.phase === 'EXPLANATION')

  const left = landed ? Math.max(0, monsterHp - state.damage) : monsterHp
  const percent = monsterHp > 0 ? Math.round((left / monsterHp) * 100) : 0

  return (
    <div className={cn('w-full max-w-28 space-y-0.5', className)}>
      <div
        className="h-1.5 w-full overflow-hidden rounded-full bg-black/50 ring-1 ring-white/10"
        role="progressbar"
        aria-label={`Vida do monstro da alternativa ${letter} nesta questão`}
        aria-valuenow={left}
        aria-valuemin={0}
        aria-valuemax={monsterHp}
      >
        <motion.div
          className={cn(
            'h-full rounded-full',
            percent === 0
              ? 'bg-slate-600'
              : percent <= 40
                ? 'bg-gradient-to-r from-danger to-game-orange'
                : 'bg-gradient-to-r from-danger to-red-400',
          )}
          animate={{ width: `${percent}%` }}
          transition={{ duration: reduce ? 0 : 0.4, ease: 'easeOut' }}
        />
      </div>
      {!compact && (
        <p className="text-center font-mono text-[0.68rem] tabular-nums text-subtle">
          {left === 0 ? 'caído' : `HP ${left}`}
        </p>
      )}
    </div>
  )
}
