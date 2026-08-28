import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { analyticsApi } from '@/lib/api/analytics'
import { queryKeys } from '@/lib/query-client'
import { CategoryBars, IntervalChart } from './components/interval-chart'
import { MasterScorePanel } from './components/master-score-panel'
import { PathList, ProjectionPanel } from './components/projection-panel'

export function AnalyticsPage() {
  const overview = useQuery({
    queryKey: queryKeys.analyticsOverview,
    queryFn: () => analyticsApi.overview(),
  })
  const history = useQuery({
    queryKey: queryKeys.analyticsScoreHistory(90),
    queryFn: () => analyticsApi.masterScoreHistory(90),
  })

  if (overview.isLoading) return <SkeletonList rows={4} />
  if (overview.isError)
    return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />

  const data = overview.data!

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analytics"
        description="Competência medida, com a incerteza à vista. Cada gráfico serve uma decisão."
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Mestre Score</CardTitle>
            <CardDescription>
              Competência real, de 0 a 1000. XP não entra nesta conta.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <MasterScorePanel score={data.master_score} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Se a prova fosse hoje</CardTitle>
            <CardDescription>
              Estimativa de acerto sobre o seu histórico — não previsão de resultado.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ProjectionPanel projection={data.projection} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Caminho da aprovação</CardTitle>
          <CardDescription>
            Ações ordenadas por quantas questões da prova elas colocam em jogo.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PathList path={data.path} />
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {data.charts.map((chart) => (
          <Card key={chart.key}>
            <CardHeader>
              <CardTitle className="text-base">{chart.title}</CardTitle>
              <CardDescription>{chart.decision}</CardDescription>
            </CardHeader>
            <CardContent>
              {chart.key === 'cobertura' ? (
                <CategoryBars chart={chart} />
              ) : (
                <IntervalChart chart={chart} />
              )}
            </CardContent>
          </Card>
        ))}

        {history.data && history.data.points.length > 1 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Evolução do Mestre Score</CardTitle>
              <CardDescription>
                Mostra se a competência medida está subindo. O score pode cair — e a queda
                aparece.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <IntervalChart
                chart={{
                  key: 'mestre-score',
                  title: 'Evolução do Mestre Score',
                  decision: 'Mostra se a competência medida está subindo.',
                  unit: 'pts',
                  points: history.data.points.map((point) => ({
                    label: new Date(point.day).toLocaleDateString('pt-BR', {
                      day: '2-digit',
                      month: '2-digit',
                    }),
                    value: point.value,
                    low: point.low,
                    high: point.high,
                    sample: 1,
                    day: point.day,
                  })),
                  empty_reason: null,
                  note: 'A faixa de cada dia acompanha o ponto: a linha sozinha esconderia a incerteza.',
                }}
              />
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
