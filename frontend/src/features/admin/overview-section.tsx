import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { adminApi } from '@/lib/api/admin'
import { queryKeys } from '@/lib/query-client'

const metrics = [
  { key: 'users_total', label: 'Usuários' },
  { key: 'users_active', label: 'Ativos' },
  { key: 'users_pending', label: 'Aguardando confirmação' },
  { key: 'users_suspended', label: 'Suspensos' },
  { key: 'users_created_last_7_days', label: 'Novos em 7 dias' },
  { key: 'sessions_active', label: 'Sessões ativas' },
  { key: 'logins_last_24h', label: 'Logins em 24h' },
] as const

export function OverviewSection() {
  const overview = useQuery({ queryKey: queryKeys.adminOverview, queryFn: adminApi.overview })

  if (overview.isError) {
    return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <Card key={metric.key}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted">{metric.label}</CardTitle>
            </CardHeader>
            <CardContent>
              {overview.isLoading ? (
                <Skeleton className="h-8 w-16" />
              ) : (
                <p className="text-3xl font-semibold tracking-tight tabular-nums">
                  {overview.data?.[metric.key] ?? 0}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-xs text-subtle">
        Todos os números vêm de contagens diretas no banco, calculadas no servidor. Indicadores
        comerciais (MRR, churn, ARPU) entram na Fase 10, junto com assinaturas e pagamentos.
      </p>
    </div>
  )
}
