import { Flame, Shield } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { StreakInfo } from '@/lib/api/types'

export function StreakCounter({
  streak,
  compact = false,
}: {
  streak: StreakInfo
  compact?: boolean
}) {
  if (compact) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm font-medium">
        <Flame
          className={cn('size-4', streak.current > 0 ? 'text-warning' : 'text-subtle')}
          aria-hidden
        />
        {streak.current} {streak.current === 1 ? 'dia' : 'dias'}
      </span>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Flame
          className={cn('size-6', streak.current > 0 ? 'text-warning' : 'text-subtle')}
          aria-hidden
        />
        <span className="text-2xl font-semibold">
          {streak.current} {streak.current === 1 ? 'dia' : 'dias'}
        </span>
      </div>

      <p className="text-sm text-muted">{streak.message}</p>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-subtle">
        <span>recorde {streak.longest}</span>
        <span>média {streak.average.toString().replace('.', ',')} dias/semana</span>
        <span className="inline-flex items-center gap-1">
          <Shield className="size-3" aria-hidden />
          {streak.shields_left} proteção(ões)
        </span>
      </div>

      <div className="flex gap-1" aria-label="Últimos 14 dias">
        {streak.history.map((day) => (
          <span
            key={day.day}
            title={`${new Date(`${day.day}T00:00:00`).toLocaleDateString('pt-BR')}: ${
              day.qualified ? 'estudou' : day.shielded ? 'protegido' : 'sem estudo'
            }`}
            className={cn(
              'h-6 flex-1 rounded-sm',
              day.qualified ? 'bg-warning' : day.shielded ? 'bg-info/50' : 'bg-surface-muted',
            )}
          />
        ))}
      </div>
    </div>
  )
}
