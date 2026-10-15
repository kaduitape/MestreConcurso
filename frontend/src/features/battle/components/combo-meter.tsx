import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Flame, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * O contador de sequência.
 *
 * Só aparece a partir do segundo acerto seguido: "COMBO x1" não é sequência
 * nenhuma, e um selo permanente na tela vira ruído em volta do enunciado.
 */
export function ComboMeter({ combo, className }: { combo: number; className?: string }) {
  const reduce = useReducedMotion()
  return (
    <AnimatePresence>
      {combo >= 2 && (
        <motion.span
          className={cn(
            'inline-flex items-center gap-1 rounded-full bg-game-orange/15 px-2.5 py-1',
            'text-xs font-black tracking-wide text-game-orange uppercase',
            className,
          )}
          initial={reduce ? false : { opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.22 }}
          aria-label={`Sequência de ${combo} acertos`}
        >
          <Flame className="size-3.5" aria-hidden />
          Combo ×{combo}
        </motion.span>
      )}
    </AnimatePresence>
  )
}

/** O selo de crítico, que dura o tempo do golpe. */
export function CriticalBadge({
  visible,
  className,
}: {
  visible: boolean
  className?: string
}) {
  const reduce = useReducedMotion()
  return (
    <AnimatePresence>
      {visible && (
        <motion.span
          className={cn(
            'pointer-events-none absolute inline-flex items-center gap-1 rounded-full',
            'bg-game-gold px-2 py-0.5 text-[11px] font-black tracking-wide text-game-bg uppercase',
            className,
          )}
          initial={reduce ? { opacity: 1 } : { opacity: 0, scale: 0.6, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0 : 0.25 }}
        >
          <Zap className="size-3" aria-hidden />
          Crítico
        </motion.span>
      )}
    </AnimatePresence>
  )
}
