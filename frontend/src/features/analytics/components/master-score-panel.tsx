import { useState } from 'react'
import { ChevronDown, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ConfidenceLevel, MasterScore } from '@/lib/api/types'

const CONFIDENCE_LABEL: Record<ConfidenceLevel, string> = {
  NONE: 'sem amostra',
  LOW: 'amostra pequena',
  MEDIUM: 'amostra razoável',
  HIGH: 'amostra sólida',
}

const SCALE = 1000

/**
 * O Mestre Score com a faixa **desenhada**, não só escrita.
 *
 * A barra mostra o intervalo como região e o valor central como um traço dentro
 * dela. É a diferença entre "seu score é 644" e "seu score está entre 592 e 686,
 * e a melhor estimativa é 644" — só a segunda é verdadeira.
 */
export function MasterScorePanel({ score }: { score: MasterScore }) {
  const [open, setOpen] = useState(false)

  if (score.empty_reason) {
    return (
      <div className="space-y-3">
        <p className="text-4xl font-semibold text-subtle">—</p>
        <p className="text-sm text-muted">{score.empty_reason}</p>
        <ul className="space-y-1">
          {score.components.map((item) => (
            <li key={item.key} className="text-xs text-subtle">
              {item.label}: {item.detail}
            </li>
          ))}
        </ul>
      </div>
    )
  }

  const left = (score.low / SCALE) * 100
  const width = ((score.high - score.low) / SCALE) * 100
  const center = (score.value / SCALE) * 100

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-mono text-4xl font-semibold tabular-nums">{score.value}</span>
        <span className="text-sm text-muted">de {SCALE}</span>
        <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-medium text-primary">
          {score.band}
        </span>
      </div>

      <div
        className="relative h-3 w-full overflow-hidden rounded-full bg-surface-muted"
        role="img"
        aria-label={`Mestre Score ${score.value} de ${SCALE}, faixa de ${score.low} a ${score.high}.`}
      >
        <div
          className="absolute inset-y-0 rounded-full bg-primary/30"
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div className="absolute inset-y-0 w-0.5 bg-primary" style={{ left: `${center}%` }} />
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
        <span className="font-mono tabular-nums text-subtle">
          faixa {score.low}–{score.high}
        </span>
        <span className="text-subtle">{CONFIDENCE_LABEL[score.confidence]}</span>
      </div>

      <p className="text-sm text-muted">{score.band_note}</p>

      {score.available_weight < 1 && (
        <p className="rounded-md bg-warning-soft/40 p-2 text-xs">
          {Math.round(score.available_weight * 100)}% dos sinais têm amostra. O score é
          calculado sobre o que existe — o que falta não conta como zero.
        </p>
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
            As parcelas abaixo somam exatamente {score.value}. XP não entra nesta conta.
          </p>
          <ul className="space-y-2">
            {score.components.map((item) => (
              <li key={item.key} className="space-y-1">
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className={cn(!item.available && 'text-subtle')}>{item.label}</span>
                  <span className="font-mono text-xs tabular-nums">
                    {item.points} / {Math.round(item.weight * SCALE)}
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${(item.points / (item.weight * SCALE)) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-subtle">{item.detail}</p>
              </li>
            ))}
          </ul>
          <p className="flex items-start gap-2 text-xs text-muted">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {score.interval_note}
          </p>
        </div>
      )}
    </div>
  )
}
