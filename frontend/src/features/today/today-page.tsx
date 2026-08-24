import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  CalendarClock,
  CalendarRange,
  CheckCircle2,
  Circle,
  Clock,
  Lock,
  RefreshCw,
  Target,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton, SkeletonList } from '@/components/ui/skeleton'
import { ApiError } from '@/lib/api/client'
import { studyApi } from '@/lib/api/study'
import { queryKeys } from '@/lib/query-client'
import { useAuth } from '@/providers/auth-provider'
import { firstName, greeting } from '@/lib/utils'
import { MissionPanel } from '@/features/study/mission'
import { SprintDialog } from '@/features/study/sprint-dialog'
import { formatMinutes } from '@/features/study/helpers'

function SetupStep({
  done,
  locked,
  title,
  description,
  phase,
  action,
}: {
  done?: boolean
  locked?: boolean
  title: string
  description: string
  phase?: string
  action?: ReactNode
}) {
  return (
    <li className="flex items-start gap-3 border-b border-border/60 py-3 last:border-0">
      {done ? (
        <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
      ) : locked ? (
        <Lock className="mt-0.5 size-5 shrink-0 text-subtle" aria-hidden />
      ) : (
        <Circle className="mt-0.5 size-5 shrink-0 text-muted" aria-hidden />
      )}
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm font-medium">
          {title}
          {phase && <Badge variant="outline">{phase}</Badge>}
        </p>
        <p className="text-sm text-muted">{description}</p>
      </div>
      {action}
    </li>
  )
}

export function TodayPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()

  const mission = useQuery({
    queryKey: queryKeys.studyToday(),
    queryFn: () => studyApi.today(),
    retry: false,
  })

  const weekMinutes = useQuery({
    queryKey: queryKeys.studyWeekMinutes,
    queryFn: studyApi.weekMinutes,
    enabled: mission.isSuccess,
  })

  const rebalance = useMutation({
    mutationFn: studyApi.rebalance,
    onSuccess: (result) => {
      toast.success(result.summary)
      queryClient.invalidateQueries({ queryKey: ['study'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível replanejar.'),
  })

  if (!user) return null

  const hasNoPlan =
    mission.isError && mission.error instanceof ApiError && mission.error.code === 'no_active_plan'

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm text-muted">{greeting()},</p>
          <h1 className="text-3xl font-semibold tracking-tight">
            {firstName(user.full_name)}.
          </h1>
        </div>
        {mission.isSuccess && <SprintDialog />}
      </header>

      {mission.isLoading && <SkeletonList rows={3} />}

      {hasNoPlan && (
        <Card>
          <CardHeader>
            <CardTitle>Comece pelo seu plano</CardTitle>
            <CardDescription>
              A missão diária aparece assim que existir um plano — e o plano sai de dados
              reais, não de suposição.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul>
              <SetupStep
                done
                title="Conta criada"
                description={`Membro desde ${new Date(user.created_at).toLocaleDateString('pt-BR')}.`}
              />
              <SetupStep
                done={Boolean(user.email_verified_at)}
                title="E-mail confirmado"
                description={
                  user.email_verified_at
                    ? 'Confirmado.'
                    : 'Confirme seu e-mail para liberar todos os recursos.'
                }
              />
              <SetupStep
                title="Montar plano de estudo"
                description="Escolha o cargo e informe sua disponibilidade real por dia da semana."
                action={
                  <Button asChild size="sm">
                    <Link to="/plano/novo">Montar plano</Link>
                  </Button>
                }
              />
              <SetupStep
                locked
                phase="Fase 5"
                title="Resolver questões da banca"
                description="Banco de provas e simulados com correção detalhada."
              />
            </ul>
          </CardContent>
        </Card>
      )}

      {mission.isError && !hasNoPlan && (
        <Alert tone="danger" title="Não foi possível carregar sua missão">
          Tente recarregar a página em instantes.
        </Alert>
      )}

      {mission.data && (
        <>
          {mission.data.overdue_count > 0 && (
            <Alert tone="warning" title={`${mission.data.overdue_count} tarefa(s) atrasada(s)`}>
              <p>
                O plano não acumula dívida: o replanejamento redistribui o que couber e
                declara o que ficou de fora.
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                loading={rebalance.isPending}
                onClick={() => rebalance.mutate()}
              >
                <RefreshCw /> Replanejar agora
              </Button>
            </Alert>
          )}

          <MissionPanel mission={mission.data} />

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
                  <CalendarClock className="size-4" aria-hidden /> Dias até a prova
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold tabular-nums">
                  {mission.data.days_until_exam ?? '—'}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
                  <Clock className="size-4" aria-hidden /> Estudado em 7 dias
                </CardTitle>
              </CardHeader>
              <CardContent>
                {weekMinutes.isLoading ? (
                  <Skeleton className="h-8 w-16" />
                ) : (
                  <p className="text-2xl font-semibold">
                    {formatMinutes(weekMinutes.data?.minutes ?? 0)}
                  </p>
                )}
                <p className="text-xs text-subtle">tempo real de foco, sem pausas</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
                  <Target className="size-4" aria-hidden /> Concluído hoje
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold">
                  {formatMinutes(mission.data.done_minutes)}
                </p>
                <p className="text-xs text-subtle">
                  de {formatMinutes(mission.data.planned_minutes)} planejados
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted">
                  <AlertTriangle className="size-4" aria-hidden /> Atrasos
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-semibold tabular-nums">
                  {mission.data.overdue_count}
                </p>
                <p className="text-xs text-subtle">tarefas de dias anteriores</p>
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/plano">
                <Target /> Ver meu plano
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/calendario">
                <CalendarRange /> Calendário
              </Link>
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
