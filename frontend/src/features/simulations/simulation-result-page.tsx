import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Lightbulb, TrendingDown, TrendingUp } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { simulationsApi } from '@/lib/api/questions'
import { queryKeys } from '@/lib/query-client'
import { formatSeconds } from '@/features/study/helpers'
import { DIFFICULTY_LABEL, formatDelta, formatPercent } from '@/features/questions/helpers'

function Bar({ value, tone }: { value: number; tone: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
      <div
        className={`h-full rounded-full ${tone}`}
        style={{ width: `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%` }}
      />
    </div>
  )
}

export function SimulationResultPage() {
  const { attemptId = '' } = useParams()
  const run = useQuery({
    queryKey: queryKeys.simulationAttempt(attemptId),
    queryFn: () => simulationsApi.attempt(attemptId),
    enabled: Boolean(attemptId),
  })

  if (run.isLoading) return <SkeletonList rows={5} />
  if (run.isError) return <ErrorState error={run.error} onRetry={() => run.refetch()} />

  const attempt = run.data!.attempt
  const analysis = attempt.analysis

  if (attempt.status !== 'FINISHED') {
    return (
      <div className="space-y-4">
        <PageHeader title="Simulado em andamento" />
        <p className="text-sm text-muted">
          Este simulado ainda não foi encerrado, então não há correção para mostrar.
        </p>
        <Button asChild>
          <Link to={`/simulados/${attemptId}`}>Voltar para a execução</Link>
        </Button>
      </div>
    )
  }

  const delta = formatDelta(analysis.accuracy_delta)

  return (
    <div className="space-y-6">
      <PageHeader
        title={attempt.simulation?.name ?? 'Resultado do simulado'}
        description={`Encerrado em ${new Date(attempt.finished_at ?? attempt.started_at).toLocaleString('pt-BR')}`}
        actions={
          <Button variant="outline" asChild>
            <Link to="/simulados">
              <ArrowLeft /> Simulados
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted">Acerto</p>
            <p className="text-3xl font-semibold">{formatPercent(analysis.accuracy, 0)}</p>
            <p className="mt-1 text-xs text-subtle">
              {attempt.correct_count} de {analysis.total ?? 0} questões
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted">Placar</p>
            <p className="text-3xl font-semibold">{attempt.score ?? 0}</p>
            <p className="mt-1 text-xs text-subtle">
              {attempt.wrong_count} erradas · {attempt.blank_count} em branco
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted">Tempo total</p>
            <p className="text-3xl font-semibold">{formatSeconds(attempt.elapsed_seconds)}</p>
            <p className="mt-1 text-xs text-subtle">
              {analysis.average_time_seconds ?? 0}s por questão respondida
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted">Comparação</p>
            {analysis.previous_accuracy === null || analysis.previous_accuracy === undefined ? (
              <>
                <p className="text-lg font-medium">Primeiro simulado</p>
                <p className="mt-1 text-xs text-subtle">
                  Ainda não há execução anterior para comparar.
                </p>
              </>
            ) : (
              <>
                <p className="flex items-center gap-2 text-3xl font-semibold">
                  {(analysis.accuracy_delta ?? 0) >= 0 ? (
                    <TrendingUp className="size-6 text-success" />
                  ) : (
                    <TrendingDown className="size-6 text-danger" />
                  )}
                  {delta}
                </p>
                <p className="mt-1 text-xs text-subtle">
                  Média anterior: {formatPercent(analysis.previous_accuracy, 0)}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Por disciplina</CardTitle>
            <CardDescription>
              Números vindos das suas respostas nesta execução, sem estimativa.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(analysis.by_subject ?? []).map((item) => (
              <div key={item.subject_name} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{item.subject_name}</span>
                  <span className="text-muted">
                    {item.correct}/{item.total} · {formatPercent(item.accuracy, 0)}
                  </span>
                </div>
                <Bar
                  value={item.accuracy}
                  tone={
                    item.accuracy >= 0.7
                      ? 'bg-success'
                      : item.accuracy >= 0.5
                        ? 'bg-warning'
                        : 'bg-danger'
                  }
                />
                <p className="text-xs text-subtle">
                  {item.wrong} erradas · {item.blank} em branco · {item.average_time_seconds}s
                  por questão
                </p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Por dificuldade</CardTitle>
            <CardDescription>
              A dificuldade é a classificação registrada na questão.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {(analysis.by_difficulty ?? []).map((item) => (
              <div key={item.difficulty} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">{DIFFICULTY_LABEL[item.difficulty]}</span>
                  <span className="text-muted">
                    {item.correct}/{item.total} · {formatPercent(item.accuracy, 0)}
                  </span>
                </div>
                <Bar value={item.accuracy} tone="bg-primary" />
              </div>
            ))}

            {(analysis.weakest_subjects?.length ?? 0) > 0 && (
              <div className="pt-2">
                <p className="text-sm font-medium">Pontos fracos nesta execução</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {analysis.weakest_subjects?.map((name) => (
                    <Badge key={name} variant="danger">
                      {name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {(analysis.strongest_subjects?.length ?? 0) > 0 && (
              <div>
                <p className="text-sm font-medium">Onde você foi bem</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {analysis.strongest_subjects?.map((name) => (
                    <Badge key={name} variant="success">
                      {name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {(analysis.recommendations?.length ?? 0) > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lightbulb className="size-5 text-primary" aria-hidden /> O que fazer agora
            </CardTitle>
            <CardDescription>
              Cada recomendação cita os números que a justificam — nada aqui é palpite.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {analysis.recommendations?.map((item) => (
                <li key={item} className="flex gap-2">
                  <span className="text-primary">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
