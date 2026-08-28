import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Territory, TerritoryState } from '@/lib/api/types'

const STATE_LABEL: Record<TerritoryState, string> = {
  LOCKED: 'Não iniciada',
  STARTED: 'Começou',
  STUDYING: 'Em andamento',
  MASTERED: 'Domínio consolidado',
  NEEDS_REVIEW: 'Pede revisão',
}

const STATE_TONE: Record<TerritoryState, 'neutral' | 'info' | 'success' | 'warning'> = {
  LOCKED: 'neutral',
  STARTED: 'neutral',
  STUDYING: 'info',
  MASTERED: 'success',
  NEEDS_REVIEW: 'warning',
}

const STATE_FILL: Record<TerritoryState, string> = {
  LOCKED: 'bg-border',
  STARTED: 'bg-info/50',
  STUDYING: 'bg-info',
  MASTERED: 'bg-success',
  NEEDS_REVIEW: 'bg-warning',
}

function minutes(value: number): string {
  if (value < 60) return `${value} min`
  return `${Math.floor(value / 60)}h${String(value % 60).padStart(2, '0')}`
}

/**
 * Um território do mapa do edital. O domínio abre em parcelas, como o rank:
 * sinal sem amostra aparece declarado, e não é contado como zero de desempenho.
 */
export function StudyTerritory({ territory }: { territory: Territory }) {
  const [open, setOpen] = useState(false)
  const available = territory.parts.filter((part) => part.available)

  return (
    <div className="space-y-2 rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{territory.subject_name}</span>
        <Badge variant={STATE_TONE[territory.state]}>{STATE_LABEL[territory.state]}</Badge>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
        <div
          className={cn('h-full rounded-full transition-[width]', STATE_FILL[territory.state])}
          style={{ width: `${Math.round(territory.mastery * 100)}%` }}
        />
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 text-xs text-subtle">
        <span className="font-mono tabular-nums">
          domínio {Math.round(territory.mastery * 100)}%
        </span>
        <span>
          {minutes(territory.studied_minutes)} de {minutes(territory.planned_minutes)}{' '}
          planejados
        </span>
      </div>

      <p className="text-xs text-muted">{territory.note}</p>

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
        <div className="space-y-2 rounded-md border border-border p-3">
          <p className="text-xs text-muted">
            {available.length === territory.parts.length
              ? 'Cobertura, desempenho e retenção — as três parcelas com amostra.'
              : `Apenas ${available.length} de ${territory.parts.length} sinais têm amostra. O domínio é calculado sobre o peso disponível, para que um sinal ausente não vire nota baixa.`}
          </p>
          <ul className="space-y-1.5">
            {territory.parts.map((part) => (
              <li key={part.key} className="flex items-baseline justify-between gap-3 text-xs">
                <span className={cn(!part.available && 'text-subtle')}>{part.label}</span>
                <span className="text-right text-subtle">{part.detail}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
