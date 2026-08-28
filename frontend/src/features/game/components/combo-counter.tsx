import { motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { RunState } from '@/lib/api/types'

/** O combo atual. Sem efeito exagerado: o número já é o recado. */
export function ComboCounter({ state }: { state: RunState }) {
  const reduce = useReducedMotion()
  const active = state.combo > 1

  return (
    <div className="flex items-baseline gap-2">
      <motion.span
        key={state.combo}
        initial={reduce || !active ? false : { scale: 1.12 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.18 }}
        className={cn(
          'font-mono text-2xl font-semibold tabular-nums',
          active ? 'text-primary' : 'text-subtle',
        )}
      >
        {state.combo}
      </motion.span>
      <span className="text-xs text-muted">
        {active ? `sequência · ${state.multiplier.toFixed(1)}×` : 'sem sequência'}
      </span>
    </div>
  )
}

/** Vidas restantes na Sobrevivência. */
export function LivesCounter({ left, total }: { left: number; total: number }) {
  return (
    <div
      className="flex items-center gap-1.5"
      role="img"
      aria-label={`${left} de ${total} vidas`}
    >
      {Array.from({ length: total }, (_, index) => (
        <span
          key={index}
          className={cn(
            'size-2.5 rounded-full',
            index < left ? 'bg-danger' : 'bg-surface-muted',
          )}
        />
      ))}
    </div>
  )
}

/** Tempo restante no Contra o Relógio. */
export function RunClock({ seconds }: { seconds: number }) {
  const minutes = Math.floor(seconds / 60)
  const rest = seconds % 60
  return (
    <span
      className={cn(
        'font-mono text-lg tabular-nums',
        seconds <= 60 ? 'text-danger' : 'text-foreground',
      )}
    >
      {minutes}:{String(rest).padStart(2, '0')}
    </span>
  )
}
