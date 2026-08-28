import { useEffect, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import type { LevelInfo } from '@/lib/api/types'

/** Conta de zero até o valor final. Respeita `prefers-reduced-motion`. */
export function CountUp({ value, duration = 700 }: { value: number; duration?: number }) {
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(reduce ? value : 0)

  useEffect(() => {
    if (reduce) {
      setShown(value)
      return
    }
    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const ratio = Math.min(1, (now - start) / duration)
      setShown(Math.round(value * (1 - (1 - ratio) ** 3)))
      if (ratio < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [value, duration, reduce])

  return <>{shown.toLocaleString('pt-BR')}</>
}

export function XPBar({ level, compact = false }: { level: LevelInfo; compact?: boolean }) {
  const reduce = useReducedMotion()

  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">
          Nível {level.level}
          {!compact && (
            <span className="ml-2 text-xs text-muted">
              <CountUp value={level.xp_total} /> XP acumulado
            </span>
          )}
        </span>
        <span className="text-xs text-muted tabular-nums">
          {level.is_max
            ? 'nível máximo'
            : `${level.xp_into_level.toLocaleString('pt-BR')} / ${level.xp_for_next?.toLocaleString('pt-BR')}`}
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={reduce ? false : { width: 0 }}
          animate={{ width: `${Math.round(level.ratio * 100)}%` }}
          transition={{ duration: reduce ? 0 : 0.7, ease: 'easeOut' }}
        />
      </div>
      {!compact && !level.is_max && (
        <p className="text-xs text-subtle">
          Faltam {((level.xp_for_next ?? 0) - level.xp_into_level).toLocaleString('pt-BR')} XP
          para o nível {level.level + 1}.
        </p>
      )}
    </div>
  )
}
