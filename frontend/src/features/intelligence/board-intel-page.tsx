import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, Dna, TrendingDown, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { catalogApi } from '@/lib/api/catalog'
import { intelligenceApi } from '@/lib/api/intelligence'
import { queryKeys } from '@/lib/query-client'
import { PriorityPanel } from './priority-panel'
import { percent, trendLabel } from './helpers'

const METRIC_UNITS: Record<string, (value: number) => string> = {
  PERCENT: (value) => percent(value, 0),
  COUNT: (value) => value.toFixed(1),
}

export function BoardIntelPage() {
  const [board, setBoard] = useState('')

  const boards = useQuery({
    queryKey: ['catalog', 'boards', 'all'],
    queryFn: () => catalogApi.boards({ page: 1, page_size: 100 }),
  })

  useEffect(() => {
    if (!board && boards.data?.items.length) setBoard(boards.data.items[0].slug)
  }, [board, boards.data])

  const incidence = useQuery({
    queryKey: queryKeys.incidence(board),
    queryFn: () => intelligenceApi.incidence(board),
    enabled: Boolean(board),
  })
  const dna = useQuery({
    queryKey: queryKeys.boardDna(board),
    queryFn: () => intelligenceApi.boardDna(board),
    enabled: Boolean(board),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Inteligência"
        description="O que a banca cobra, o que o seu histórico mostra e o que isso muda no seu plano."
        actions={
          <Select
            value={board}
            onChange={(event) => setBoard(event.target.value)}
            aria-label="Banca"
            className="w-auto"
          >
            {boards.data?.items.map((item) => (
              <option key={item.public_id} value={item.slug}>
                {item.name}
              </option>
            ))}
          </Select>
        }
      />

      <PriorityPanel />

      {boards.data?.items.length === 0 && (
        <EmptyState
          icon={Dna}
          title="Nenhuma banca cadastrada"
          description="O mapa de incidência e o DNA da banca são calculados sobre as questões cadastradas de cada banca."
        />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="size-5 text-primary" aria-hidden /> Mapa de incidência
            </CardTitle>
            <CardDescription>
              {incidence.data && incidence.data.board_questions_count > 0
                ? `${incidence.data.board_questions_count} questões da banca no banco` +
                  (incidence.data.period_start_year
                    ? `, de ${incidence.data.period_start_year} a ${incidence.data.period_end_year}.`
                    : '.')
                : 'Fatia de cada disciplina nas questões cadastradas da banca.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {incidence.isLoading && <SkeletonList rows={3} />}
            {incidence.isError && (
              <ErrorState error={incidence.error} onRetry={() => incidence.refetch()} />
            )}

            {incidence.data?.empty_reason && (
              <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                {incidence.data.empty_reason}
              </p>
            )}

            {incidence.data?.rows.map((row) => {
              const trend = trendLabel(row.trend)
              return (
                <div
                  key={`${row.subject_name}-${row.topic_name ?? ''}`}
                  className="space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2 text-sm">
                    <span className="font-medium">{row.topic_name ?? row.subject_name}</span>
                    <span className="flex items-center gap-2 text-muted">
                      {row.trend !== null &&
                        (row.trend > 0 ? (
                          <TrendingUp className="size-4 text-success" aria-hidden />
                        ) : (
                          <TrendingDown className="size-4 text-danger" aria-hidden />
                        ))}
                      {percent(row.incidence_pct, 1)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${row.incidence_pct * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-subtle">
                    {row.questions_count} de {row.board_questions_count} questões
                    {trend ? ` · ${trend}` : ' · sem histórico para apontar tendência'}
                  </p>
                </div>
              )
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Dna className="size-5 text-secondary" aria-hidden /> DNA da banca
            </CardTitle>
            <CardDescription>
              Métricas contadas sobre as questões cadastradas — cada uma leva a amostra junto.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {dna.isLoading && <SkeletonList rows={3} />}
            {dna.isError && <ErrorState error={dna.error} onRetry={() => dna.refetch()} />}

            {dna.data?.empty_reason && (
              <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
                {dna.data.empty_reason}
              </p>
            )}

            {dna.data?.metrics.map((metric) => (
              <div key={metric.metric_slug} className="space-y-2">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-sm font-medium">{metric.label}</p>
                  <Badge variant="outline">{metric.sample_questions} questões</Badge>
                </div>
                {Object.keys(metric.detail).length > 0 ? (
                  <ul className="space-y-1">
                    {Object.entries(metric.detail).map(([key, value]) => (
                      <li key={key} className="flex items-center gap-2 text-sm">
                        <span className="w-40 shrink-0 truncate text-muted">{key}</span>
                        <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-muted">
                          <span
                            className="block h-full rounded-full bg-secondary"
                            style={{ width: `${value * 100}%` }}
                          />
                        </span>
                        <span className="w-12 text-right text-xs tabular-nums">
                          {percent(value, 0)}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted">
                    {(METRIC_UNITS[metric.unit] ?? String)(metric.value)}
                  </p>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
