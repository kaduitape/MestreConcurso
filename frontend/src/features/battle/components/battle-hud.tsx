import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { cn } from '@/lib/utils'
import type { BattleStatus } from '@/lib/api/types'

/** Barra de vida. Só `transform`/`width` numa faixa curta — nada de layout. */
export function HealthBar({
  label,
  current,
  max,
  ratio,
  tone,
  className,
}: {
  label: string
  current: number
  max: number
  ratio: number
  tone: 'player' | 'enemy'
  className?: string
}) {
  const percent = Math.round(ratio * 100)
  return (
    <div className={cn('space-y-1', className)}>
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="font-semibold tracking-wide uppercase">{label}</span>
        <span className="font-mono tabular-nums text-muted">
          {current}/{max}
        </span>
      </div>
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-white/10"
        role="progressbar"
        aria-label={`Vida de ${label}`}
        aria-valuenow={current}
        aria-valuemin={0}
        aria-valuemax={max}
      >
        <motion.div
          className={cn(
            'h-full rounded-full',
            tone === 'player'
              ? 'bg-gradient-to-r from-success to-emerald-400'
              : 'bg-gradient-to-r from-danger to-game-orange',
            percent <= 25 && 'animate-pulse',
          )}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.45, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}

/** O número de dano que sobe e some. */
export function DamageEffect({
  amount,
  visible,
  className,
}: {
  amount: number
  visible: boolean
  className?: string
}) {
  const reduce = useReducedMotion()
  return (
    <AnimatePresence>
      {visible && amount > 0 && (
        <motion.span
          className={cn(
            'pointer-events-none absolute font-mono text-2xl font-black text-danger',
            'drop-shadow-[0_2px_8px_rgb(0_0_0/0.6)]',
            className,
          )}
          initial={{ opacity: 0, y: 0, scale: 0.8 }}
          animate={{ opacity: 1, y: reduce ? 0 : -26, scale: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduce ? 0.15 : 0.6 }}
          aria-live="polite"
        >
          −{amount}
        </motion.span>
      )}
    </AnimatePresence>
  )
}

/** O arco de espada: um traço luminoso curto, sem partículas pesadas. */
export function SlashEffect({ visible, className }: { visible: boolean; className?: string }) {
  const reduce = useReducedMotion()
  if (reduce) return null
  return (
    <AnimatePresence>
      {visible && (
        <motion.svg
          viewBox="0 0 100 100"
          className={cn('pointer-events-none absolute size-24', className)}
          initial={{ opacity: 0, rotate: -35, scale: 0.7 }}
          animate={{ opacity: [0, 1, 0], rotate: 20, scale: 1.1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
          aria-hidden
        >
          <path
            d="M12 78 Q40 20 88 14"
            fill="none"
            stroke="var(--color-game-cyan)"
            strokeWidth={7}
            strokeLinecap="round"
          />
        </motion.svg>
      )}
    </AnimatePresence>
  )
}

/** O placar da batalha: as duas vidas e o andamento das questões. */
export function BattleHUD({
  status,
  enemyName,
  className,
}: {
  status: BattleStatus
  enemyName: string
  className?: string
}) {
  return (
    <div className={cn('grid gap-3 sm:grid-cols-2', className)}>
      <HealthBar
        label="Guerreiro"
        current={status.player_hp}
        max={status.player_max_hp}
        ratio={status.player_hp_ratio}
        tone="player"
      />
      <HealthBar
        label={enemyName}
        current={status.enemy_hp}
        max={status.enemy_max_hp}
        ratio={status.enemy_hp_ratio}
        tone="enemy"
      />
      <p className="text-xs text-subtle sm:col-span-2">
        Questão {Math.min(status.answered + 1, status.questions)} de {status.questions} ·{' '}
        {status.correct} acerto(s)
      </p>
    </div>
  )
}
