import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CalendarRange, RefreshCw, Target } from 'lucide-react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { studyApi } from '@/lib/api/study'
import { queryKeys } from '@/lib/query-client'
import { WEEKDAYS, explainTask, formatMinutes } from './helpers'

export function PlanPage() {
  const queryClient = useQueryClient()

  const plan = useQuery({
    queryKey: queryKeys.studyPlan,
    queryFn: studyApi.plan,
    retry: false,
  })

  const progress = useQuery({
    queryKey: queryKeys.studyProgress,
    queryFn: studyApi.progress,
    enabled: plan.isSuccess,
  })

  const rebalance = useMutation({
    mutationFn: studyApi.rebalance,
    onSuccess: (result) => {
      toast.success(result.summary || 'Nada a replanejar.')
      queryClient.invalidateQueries({ queryKey: ['study'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível replanejar.'),
  })

  if (plan.isLoading) return <SkeletonList rows={4} />

  if (plan.isError) {
    const notFound = plan.error instanceof ApiError && plan.error.code === 'no_active_plan'
    if (!notFound) return <ErrorState error={plan.error} onRetry={() => plan.refetch()} />
    return (
      <EmptyState
        icon={Target}
        title="Você ainda não tem um plano"
        description="Escolha o cargo que vai prestar e informe sua disponibilidade — o plano é montado na hora."
        action={
          <Button asChild>
            <Link to="/plano/novo">Montar meu plano</Link>
          </Button>
        }
      />
    )
  }

  const data = plan.data!
  const progressByKey = new Map(
    (progress.data ?? []).map((item) => [item.subject_key, item]),
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={data.name}
        description={`${formatMinutes(data.weekly_minutes_target)} por semana · ${formatMinutes(data.total_planned_minutes)} planejados até a prova`}
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/calendario">
                <CalendarRange /> Calendário
              </Link>
            </Button>
            <Button
              variant="outline"
              loading={rebalance.isPending}
              onClick={() => rebalance.mutate()}
            >
              <RefreshCw /> Replanejar atrasos
            </Button>
            <Button asChild>
              <Link to="/plano/novo">Refazer plano</Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <p className="text-xs tracking-wide text-subtle uppercase">Dias até a prova</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {data.days_until_exam ?? '—'}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs tracking-wide text-subtle uppercase">Meta semanal</p>
            <p className="mt-1 text-2xl font-semibold">
              {formatMinutes(data.weekly_minutes_target)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-xs tracking-wide text-subtle uppercase">Disciplinas</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{data.shares.length}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Como o tempo foi dividido</CardTitle>
          <CardDescription>
            A fatia de cada disciplina sai de três números do edital — nenhuma delas foi
            estimada por IA.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-4">
            {data.shares.map((share) => {
              const studied = progressByKey.get(share.key)
              const completion = studied ? Math.round(studied.completion * 100) : 0
              return (
                <li key={share.key} className="space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">{share.name}</p>
                    <p className="text-sm text-muted">
                      {formatMinutes(share.minutes)} ·{' '}
                      {(share.share * 100).toFixed(1)}% do plano
                      {studied && ` · ${completion}% cumprido`}
                    </p>
                  </div>
                  <div
                    className="h-2 overflow-hidden rounded-full bg-surface-muted"
                    role="img"
                    aria-label={`${share.name}: ${completion}% cumprido`}
                  >
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{ width: `${Math.max(2, completion)}%` }}
                    />
                  </div>
                  <p className="text-xs text-subtle">
                    {explainTask(share.breakdown).join(' · ')}
                  </p>
                </li>
              )
            })}
          </ul>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sua disponibilidade</CardTitle>
            <CardDescription>Base de todo o cálculo da agenda.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {WEEKDAYS.map((weekday) => {
                const item = data.availability.find((row) => row.weekday === weekday.value)
                return (
                  <li
                    key={weekday.value}
                    className="flex items-center justify-between rounded-md bg-surface-muted px-3 py-2 text-sm"
                  >
                    <span>{weekday.label}</span>
                    <span className={item ? 'font-medium' : 'text-subtle'}>
                      {item ? formatMinutes(item.minutes) : 'folga'}
                    </span>
                  </li>
                )
              })}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Composição por tipo de atividade</CardTitle>
            <CardDescription>
              Perto da prova, teoria cede lugar a questões e revisão.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(data.minutes_by_kind).map(([kind, minutes]) => (
              <div key={kind} className="flex items-center justify-between text-sm">
                <span>{kind}</span>
                <Badge variant="outline">{formatMinutes(minutes)}</Badge>
              </div>
            ))}
            {Object.keys(data.minutes_by_kind).length === 0 && (
              <p className="text-sm text-muted">Sem tarefas geradas ainda.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Alert tone="info">
        A priorização por desempenho, erros e retenção (Mestre Priority Score) chega na Fase 6.
        Hoje o plano usa edital, extensão do conteúdo e tempo disponível — e mostra sempre de
        onde veio cada número.
      </Alert>
    </div>
  )
}
