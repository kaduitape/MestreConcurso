import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Check, Circle, Loader2, MinusCircle } from 'lucide-react'
import { Alert } from '@/components/ui/alert'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { noticeAnalysisApi } from '@/lib/api/notice-analysis'
import type { AnalysisState, StepStatus } from '@/lib/api/types'
import { cn } from '@/lib/utils'

const ICONS: Record<StepStatus, typeof Check> = {
  PENDING: Circle,
  RUNNING: Loader2,
  DONE: Check,
  SKIPPED: MinusCircle,
  FAILED: AlertTriangle,
}

const TONES: Record<StepStatus, string> = {
  PENDING: 'text-subtle',
  RUNNING: 'text-primary',
  DONE: 'text-success',
  SKIPPED: 'text-muted',
  FAILED: 'text-danger',
}

const ACTIVE_STATUSES = new Set(['QUEUED', 'PROCESSING'])

/**
 * Checklist do processamento, não um spinner: cada etapa mostra o que foi feito
 * e com que resultado. Enquanto o worker trabalha, o estado chega por SSE.
 */
export function AnalysisProgressPanel({
  publicId,
  onFinished,
}: {
  publicId: string
  onFinished?: () => void
}) {
  const initial = useQuery({
    queryKey: ['admin', 'notices', publicId, 'analysis'],
    queryFn: () => noticeAnalysisApi.state(publicId),
  })
  const [live, setLive] = useState<AnalysisState | null>(null)
  const state = live ?? initial.data ?? null
  const isRunning = state ? ACTIVE_STATUSES.has(state.status) : false

  useEffect(() => {
    if (!isRunning) return
    const stop = noticeAnalysisApi.stream(publicId, {
      onProgress: setLive,
      onDone: () => onFinished?.(),
    })
    return stop
  }, [publicId, isRunning, onFinished])

  if (!state) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>Processamento do edital</CardTitle>
        <CardDescription>
          Extração, estruturação e conferência de cada citação contra o PDF.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {state.error && (
          <Alert tone="danger" title="A análise não foi concluída">
            {state.error}
          </Alert>
        )}

        <ol className="space-y-2">
          {state.steps.map((step) => {
            const Icon = ICONS[step.status]
            return (
              <li key={step.key} className="flex items-start gap-3 text-sm">
                <Icon
                  className={cn(
                    'mt-0.5 size-4 shrink-0',
                    TONES[step.status],
                    step.status === 'RUNNING' && 'animate-spin',
                  )}
                  aria-hidden
                />
                <div className="min-w-0">
                  <p
                    className={cn(
                      'font-medium',
                      step.status === 'PENDING' && 'text-subtle',
                      step.status === 'FAILED' && 'text-danger',
                    )}
                  >
                    {step.label}
                  </p>
                  {step.detail && <p className="text-xs text-muted">{step.detail}</p>}
                </div>
              </li>
            )
          })}
        </ol>

        {Object.keys(state.coverage).length > 0 && (
          <p className="rounded-md bg-surface-muted p-3 text-xs text-muted">
            Cobertura da extração: <strong>{state.coverage.official ?? 0}</strong> campo(s) com
            citação conferida, <strong>{state.coverage.inferred ?? 0}</strong> inferido(s) e{' '}
            <strong>{state.coverage.not_found ?? 0}</strong> não localizado(s) — de{' '}
            {state.coverage.total ?? 0} no total.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
