import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { RankInfo } from '@/lib/api/types'
import { RANK_STYLE, scorePercent } from '../helpers'

export function RankBadge({ rank, size = 'md' }: { rank: RankInfo; size?: 'sm' | 'md' }) {
  const style = RANK_STYLE[rank.slug]
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-semibold text-white',
        size === 'sm' ? 'px-2.5 py-0.5 text-[11px]' : 'px-3 py-1 text-sm',
      )}
      style={{ backgroundImage: `linear-gradient(135deg, ${style.from}, ${style.to})` }}
    >
      {style.label}
    </span>
  )
}

/** O rank aberto: as parcelas somam exatamente o score exibido. */
export function RankPanel({ rank }: { rank: RankInfo }) {
  const [open, setOpen] = useState(false)
  const sum = rank.components.reduce((total, item) => total + item.points, 0)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <RankBadge rank={rank} />
        <span className="text-sm text-muted">score {scorePercent(rank.score)}</span>
      </div>

      {rank.next_tier_name && (
        <div className="space-y-1">
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round(rank.progress_to_next * 100)}%` }}
            />
          </div>
          <p className="text-xs text-subtle">
            {scorePercent(rank.progress_to_next, 0)} do caminho para {rank.next_tier_name}.
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex items-center gap-1 text-xs font-medium text-primary"
      >
        por quê?
        <ChevronDown className={cn('size-3 transition', open && 'rotate-180')} aria-hidden />
      </button>

      {open && (
        <div className="space-y-3 rounded-md border border-border p-3">
          <p className="text-xs text-muted">
            As parcelas abaixo somam exatamente {scorePercent(sum)}. XP não entra nesta conta —
            o rank mede desempenho, não acúmulo.
          </p>
          <ul className="space-y-2">
            {rank.components.map((item) => (
              <li key={item.key} className="space-y-1">
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className={cn(!item.available && 'text-subtle')}>{item.label}</span>
                  <span className="font-mono text-xs tabular-nums">
                    {item.points.toFixed(3)} / {item.weight.toFixed(2)}
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${(item.points / item.weight) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-subtle">{item.detail}</p>
              </li>
            ))}
          </ul>
          {rank.missing_signals.length > 0 && (
            <p className="rounded-md bg-warning-soft/40 p-2 text-xs">
              {rank.missing_signals.length} sinal(is) ainda sem amostra. Eles valem zero até
              existirem dados — o rank cresce conforme você gera histórico.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export function LevelBadge({ level }: { level: number }) {
  return <Badge variant="primary">LVL {level}</Badge>
}
