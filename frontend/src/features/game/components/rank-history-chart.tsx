import { cn } from '@/lib/utils'
import type { RankHistory } from '@/lib/api/types'
import { RANK_STYLE, scorePercent } from '../helpers'

/**
 * A evolução do rank — inclusive quando ele cai. Ao lado, o XP no mesmo período:
 * ver os dois juntos é o que deixa claro que acumular não é dominar.
 */
export function RankHistoryChart({ history }: { history: RankHistory }) {
  if (history.points.length < 2) {
    return <p className="text-sm text-muted">{history.empty_reason}</p>
  }

  const width = 100
  const height = 40
  const step = width / (history.points.length - 1)
  const line = history.points
    .map((point, index) => `${index * step},${height - point.rank_score * height}`)
    .join(' ')

  const delta = history.delta ?? 0
  const first = history.points[0]
  const last = history.points[history.points.length - 1]

  return (
    <div className="space-y-3">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-16 w-full"
        role="img"
        aria-label={`Score do rank de ${scorePercent(first.rank_score)} a ${scorePercent(
          last.rank_score,
        )} em ${history.points.length} dias.`}
      >
        <polyline
          points={line}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          className="text-primary"
        />
      </svg>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs">
        <span className="text-subtle">
          {history.points.length} dias · de {RANK_STYLE[first.rank_slug].label} a{' '}
          {RANK_STYLE[last.rank_slug].label}
        </span>
        <span
          className={cn(
            'font-mono tabular-nums',
            delta > 0 && 'text-success',
            delta < 0 && 'text-danger',
            delta === 0 && 'text-subtle',
          )}
        >
          {delta > 0 ? '+' : ''}
          {scorePercent(delta)} no período
        </span>
      </div>

      <p className="text-xs text-subtle">
        XP no mesmo período: {first.xp_total} → {last.xp_total}. O XP mede esforço acumulado; o
        rank mede desempenho. Eles se movem por motivos diferentes.
      </p>
    </div>
  )
}
