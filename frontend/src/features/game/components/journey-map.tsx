import { Check, Info } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Journey, Milestone } from '@/lib/api/types'

function Dot({ state }: { state: Milestone['state'] }) {
  if (state === 'DONE') {
    return (
      <span className="flex size-7 items-center justify-center rounded-full bg-primary text-white">
        <Check className="size-4" aria-hidden />
      </span>
    )
  }
  if (state === 'CURRENT') {
    return (
      <span className="flex size-7 items-center justify-center rounded-full border-2 border-primary bg-surface">
        <span className="size-2.5 rounded-full bg-primary" />
      </span>
    )
  }
  return <span className="size-7 rounded-full border-2 border-border bg-surface" />
}

/**
 * A trilha da jornada. Cada marco tem critério verificável e o número que o
 * cumpre — o aviso do rodapé é obrigatório, não decorativo.
 */
export function JourneyMap({ journey }: { journey: Journey }) {
  const current = journey.milestones.find((item) => item.key === journey.current_key)

  return (
    <div className="space-y-6">
      <ol className="space-y-0">
        {journey.milestones.map((milestone, index) => (
          <li key={milestone.key} className="flex gap-4">
            <div className="flex flex-col items-center">
              <Dot state={milestone.state} />
              {index < journey.milestones.length - 1 && (
                <span
                  className={cn(
                    'w-0.5 flex-1',
                    milestone.state === 'DONE' ? 'bg-primary' : 'bg-border',
                  )}
                />
              )}
            </div>
            <div className={cn('pb-6', index === journey.milestones.length - 1 && 'pb-0')}>
              <p
                className={cn(
                  'text-sm font-medium',
                  milestone.state === 'PENDING' && 'text-subtle',
                )}
              >
                {milestone.label}
              </p>
              <p className="text-xs text-muted">{milestone.description}</p>
              <p className="mt-1 font-mono text-[11px] tabular-nums text-subtle">
                {milestone.detail}
              </p>
            </div>
          </li>
        ))}
      </ol>

      {current && (
        <div className="space-y-2 rounded-lg border border-border p-4">
          <p className="text-sm font-medium">Etapa atual — {current.label}</p>
          <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round(current.ratio * 100)}%` }}
            />
          </div>
          <p className="text-xs text-muted">
            {Math.round(current.ratio * 100)}% · {current.detail}
          </p>
        </div>
      )}

      <p className="flex items-start gap-2 rounded-md bg-surface-muted p-3 text-xs text-muted">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>{journey.disclaimer}</span>
      </p>
    </div>
  )
}
