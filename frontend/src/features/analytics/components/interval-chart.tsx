import type { AnalyticsChart } from '@/lib/api/types'

const HEIGHT = 60

/**
 * Um gráfico com a **faixa desenhada**: a região sombreada é o intervalo de cada
 * ponto, e a linha é o valor central. Duas semanas com o mesmo acerto e amostras
 * diferentes ficam visivelmente diferentes — que é exatamente o ponto.
 */
export function IntervalChart({ chart }: { chart: AnalyticsChart }) {
  const isPercent = chart.unit === '%'
  const format = (value: number) =>
    isPercent ? `${Math.round(value * 100)}%` : `${Math.round(value)}`

  if (chart.points.length === 0) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted">{chart.empty_reason}</p>
        <p className="text-xs text-subtle">{chart.decision}</p>
      </div>
    )
  }

  const values = chart.points.map((point) => point.high ?? point.value)
  const max = isPercent ? 1 : Math.max(...values, 1)
  const step = chart.points.length > 1 ? 100 / (chart.points.length - 1) : 0
  const y = (value: number) => HEIGHT - (value / max) * HEIGHT

  const line = chart.points.map((point, index) => `${index * step},${y(point.value)}`).join(' ')

  const hasBand = chart.points.every((point) => point.low !== null && point.high !== null)
  const band = hasBand
    ? [
        ...chart.points.map((point, index) => `${index * step},${y(point.high!)}`),
        ...[...chart.points]
          .reverse()
          .map(
            (point, index) => `${(chart.points.length - 1 - index) * step},${y(point.low!)}`,
          ),
      ].join(' ')
    : null

  const last = chart.points[chart.points.length - 1]

  return (
    <div className="space-y-3">
      <svg
        viewBox={`0 0 100 ${HEIGHT}`}
        preserveAspectRatio="none"
        className="h-24 w-full"
        role="img"
        aria-label={chart.points
          .map((point) => `${point.label}: ${format(point.value)} em ${point.sample}`)
          .join('; ')}
      >
        {band && <polygon points={band} className="fill-primary/15" />}
        <polyline
          points={line}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          className="text-primary"
        />
      </svg>

      <div className="flex justify-between text-[11px] text-subtle">
        <span>{chart.points[0].label}</span>
        <span className="font-mono tabular-nums">
          {format(last.value)}
          {hasBand && (
            <span className="ml-1">
              ({format(last.low!)}–{format(last.high!)})
            </span>
          )}
        </span>
        <span>{last.label}</span>
      </div>

      {chart.note && <p className="text-xs text-subtle">{chart.note}</p>}
    </div>
  )
}

/** Barras horizontais para séries categóricas (cobertura por disciplina). */
export function CategoryBars({ chart }: { chart: AnalyticsChart }) {
  if (chart.points.length === 0) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted">{chart.empty_reason}</p>
        <p className="text-xs text-subtle">{chart.decision}</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <ul className="space-y-2">
        {chart.points.map((point) => (
          <li key={point.label} className="space-y-1">
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span>{point.label}</span>
              <span className="font-mono text-xs tabular-nums text-muted">
                {Math.round(point.value * 100)}%
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round(point.value * 100)}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      {chart.note && <p className="text-xs text-subtle">{chart.note}</p>}
    </div>
  )
}
