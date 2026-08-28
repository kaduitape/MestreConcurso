import { AlertTriangle, Info } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ExamProjection, StudyPath } from '@/lib/api/types'

/**
 * "Se a prova fosse hoje" — a tela mais perigosa do produto.
 *
 * Ela mostra nota estimada, nunca chance de aprovação; sempre com faixa; e
 * sempre declarando **qual fatia da prova** a estimativa cobre. Cobertura baixa
 * não vira um número menor: vira ausência de número, com o motivo.
 */
export function ProjectionPanel({ projection }: { projection: ExamProjection }) {
  const percent = Math.round(projection.coverage * 100)

  return (
    <div className="space-y-5">
      {projection.is_reliable ? (
        <div className="space-y-1">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-mono text-4xl font-semibold tabular-nums">
              {projection.expected?.toFixed(0)}
            </span>
            <span className="text-sm text-muted">
              de {projection.covered_questions} questões estimadas
            </span>
          </div>
          <p className="font-mono text-xs tabular-nums text-subtle">
            faixa {projection.expected_low?.toFixed(1)}–{projection.expected_high?.toFixed(1)}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted">{projection.empty_reason}</p>
      )}

      <div className="space-y-1">
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
          <div
            className={cn(
              'h-full rounded-full',
              projection.is_reliable ? 'bg-primary' : 'bg-warning',
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="text-xs text-subtle">
          A estimativa cobre {percent}% das questões da prova ({projection.covered_questions} de{' '}
          {projection.total_questions}).
        </p>
      </div>

      <ul className="space-y-3">
        {projection.subjects.map((subject) => (
          <li
            key={`${subject.subject_id ?? subject.name}`}
            className="space-y-1 border-t border-border pt-3 first:border-t-0 first:pt-0"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className={cn('text-sm font-medium', !subject.included && 'text-subtle')}>
                {subject.name}
                {subject.is_eliminatory && (
                  <Badge variant="warning" className="ml-2">
                    eliminatória
                  </Badge>
                )}
              </span>
              <span className="font-mono text-xs tabular-nums text-muted">
                {subject.questions} questões
              </span>
            </div>
            <p className="text-xs text-muted">{subject.detail}</p>
            {subject.risk_note && (
              <p className="flex items-start gap-1.5 rounded-md bg-warning-soft/40 p-2 text-xs">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
                {subject.risk_note}
              </p>
            )}
          </li>
        ))}
      </ul>

      <p className="flex items-start gap-2 rounded-md bg-surface-muted p-3 text-xs text-muted">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        {projection.disclaimer}
      </p>
    </div>
  )
}

const KIND_TONE = {
  IMPROVE: 'primary',
  MEASURE: 'info',
  MAINTAIN: 'neutral',
} as const

/** O caminho: ações ordenadas, cada uma com o número que a gerou. */
export function PathList({ path }: { path: StudyPath }) {
  if (path.steps.length === 0) {
    return <p className="text-sm text-muted">{path.empty_reason}</p>
  }

  return (
    <div className="space-y-4">
      <ol className="space-y-3">
        {path.steps.map((step, index) => (
          <li
            key={`${step.subject_name}-${step.kind}`}
            className="flex gap-3 border-t border-border pt-3 first:border-t-0 first:pt-0"
          >
            <span className="mt-0.5 font-mono text-sm tabular-nums text-subtle">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={KIND_TONE[step.kind]}>{step.label}</Badge>
                <span className="text-sm font-medium">{step.subject_name}</span>
                {step.questions_at_stake > 0 && (
                  <span className="font-mono text-xs tabular-nums text-subtle">
                    {step.questions_at_stake.toFixed(1)} questões em jogo
                  </span>
                )}
              </div>
              <p className="text-sm">{step.action}</p>
              <p className="text-xs text-subtle">{step.evidence}</p>
              {step.risk_note && <p className="text-xs text-warning">{step.risk_note}</p>}
            </div>
          </li>
        ))}
      </ol>

      <p className="text-xs text-muted">{path.disclaimer}</p>
    </div>
  )
}
