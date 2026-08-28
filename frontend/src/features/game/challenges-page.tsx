import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Flame, Swords, Timer, Zap } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import type { ChallengeModeKey, GameRun } from '@/lib/api/types'
import { ComboCounter, LivesCounter, RunClock } from './components/combo-counter'

const MODE_ICON: Record<ChallengeModeKey, LucideIcon> = {
  BOSS: Swords,
  SURVIVAL: Flame,
  COMBO: Zap,
  TIME_ATTACK: Timer,
}

function RunHeader({ run }: { run: GameRun }) {
  const state = run.state
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <p className="text-sm text-muted">{run.mode_name}</p>
        {run.subject_label && <p className="text-lg font-semibold">{run.subject_label}</p>}
      </div>
      <div className="flex items-center gap-6">
        {state.lives_left !== null && (
          <LivesCounter left={state.lives_left} total={state.lives_left + state.wrong} />
        )}
        {state.seconds_left !== null && <RunClock seconds={state.seconds_left} />}
        {run.mode === 'COMBO' && <ComboCounter state={state} />}
        <span className="font-mono text-sm tabular-nums text-subtle">
          {state.answered} / {state.answered + state.questions_left}
        </span>
      </div>
    </div>
  )
}

function RunBoard({
  run,
  onAnswer,
  onFinish,
  pending,
}: {
  run: GameRun
  onAnswer: (letter: string, seconds: number) => void
  onFinish: (abandon: boolean) => void
  pending: boolean
}) {
  const startedAt = useRef(Date.now())
  const question = run.question

  useEffect(() => {
    startedAt.current = Date.now()
  }, [question?.public_id])

  if (run.status !== 'RUNNING' || !question) {
    const score = run.score
    return (
      <div className="space-y-4">
        <RunHeader run={run} />
        <div className="space-y-2 rounded-lg border border-border p-4">
          <p className="text-lg font-semibold">{score?.headline}</p>
          {run.state.over_reason && (
            <p className="text-sm text-muted">{run.state.over_reason}</p>
          )}
          <Badge variant={score?.achieved ? 'success' : 'neutral'}>
            {score?.achieved ? 'Desafio cumprido' : 'Desafio não cumprido'}
          </Badge>
        </div>

        {score && (
          <div className="rounded-lg border border-border p-4">
            <p className="mb-2 text-sm font-medium">De onde veio o XP</p>
            <ul className="space-y-1">
              {score.breakdown.map((line) => (
                <li key={line.label} className="flex justify-between gap-4 text-sm">
                  <span className="text-muted">{line.label}</span>
                  <span className="tabular-nums">{line.value}</span>
                </li>
              ))}
            </ul>
            {run.status === 'ABANDONED' && (
              <p className="mt-3 text-xs text-warning">
                Rodada abandonada não pontua: parar no meio não é desempenho.
              </p>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <RunHeader run={run} />

      <div className="space-y-4">
        <p className="whitespace-pre-line text-sm leading-relaxed">{question.statement}</p>
        <ul className="space-y-2">
          {question.alternatives.map((alternative) => (
            <li key={alternative.public_id}>
              <button
                type="button"
                disabled={pending}
                onClick={() =>
                  onAnswer(
                    alternative.letter,
                    Math.max(1, Math.round((Date.now() - startedAt.current) / 1000)),
                  )
                }
                className="flex w-full gap-3 rounded-md border border-border p-3 text-left text-sm transition hover:border-primary hover:bg-surface-muted disabled:opacity-60"
              >
                <span className="font-semibold text-primary">{alternative.letter}</span>
                <span>{alternative.content}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex gap-2">
        <Button variant="ghost" onClick={() => onFinish(true)} disabled={pending}>
          Abandonar rodada
        </Button>
      </div>
    </div>
  )
}

export function ChallengesPage() {
  const queryClient = useQueryClient()
  const [feedback, setFeedback] = useState<string | null>(null)

  const modes = useQuery({
    queryKey: queryKeys.gameChallengeModes,
    queryFn: () => gameApi.challengeModes(),
  })
  const current = useQuery({
    queryKey: queryKeys.gameCurrentRun,
    queryFn: () => gameApi.currentRun(),
  })
  const history = useQuery({
    queryKey: queryKeys.gameRunHistory,
    queryFn: () => gameApi.runHistory(),
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['game'] })

  const start = useMutation({
    mutationFn: (mode: string) => gameApi.startRun(mode),
    onSuccess: invalidate,
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível começar a rodada.',
      ),
  })

  const answer = useMutation({
    mutationFn: (input: {
      publicId: string
      questionId: string
      letter: string
      seconds: number
    }) =>
      gameApi.answerRun(input.publicId, {
        question_public_id: input.questionId,
        letter: input.letter,
        time_seconds: input.seconds,
      }),
    onSuccess: (result) => {
      setFeedback(
        result.is_correct
          ? 'Certo.'
          : `Errado — a resposta era ${result.correct_letter ?? '—'}.`,
      )
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível responder.'),
  })

  const finish = useMutation({
    mutationFn: (input: { publicId: string; abandon: boolean }) =>
      gameApi.finishRun(input.publicId, input.abandon),
    onSuccess: invalidate,
  })

  if (modes.isLoading) return <SkeletonList rows={3} />
  if (modes.isError) return <ErrorState error={modes.error} onRetry={() => modes.refetch()} />

  const run = current.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Desafios"
        description="Rodadas curtas com questões reais do banco. O placar sai das suas respostas."
      />

      {run ? (
        <Card>
          <CardContent className="space-y-4 pt-6">
            <RunBoard
              run={run}
              pending={answer.isPending || finish.isPending}
              onAnswer={(letter, seconds) =>
                answer.mutate({
                  publicId: run.public_id,
                  questionId: run.question!.public_id,
                  letter,
                  seconds,
                })
              }
              onFinish={(abandon) => finish.mutate({ publicId: run.public_id, abandon })}
            />
            {feedback && <p className="text-sm text-muted">{feedback}</p>}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {modes.data!.map((mode) => {
            const Icon = MODE_ICON[mode.mode]
            return (
              <Card key={mode.mode}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Icon className="size-4 text-primary" aria-hidden />
                    {mode.name}
                  </CardTitle>
                  <CardDescription>{mode.description}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <p className="text-xs text-muted">{mode.rule}</p>
                  <div className="flex flex-wrap gap-2 text-xs text-subtle">
                    <span>{mode.questions} questões</span>
                    {mode.lives !== null && <span>{mode.lives} vidas</span>}
                    {mode.time_limit_seconds !== null && (
                      <span>{Math.round(mode.time_limit_seconds / 60)} minutos</span>
                    )}
                  </div>
                  <Button onClick={() => start.mutate(mode.mode)} disabled={start.isPending}>
                    Começar
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {history.data && history.data.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Rodadas anteriores</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {history.data.map((item) => (
                <li
                  key={item.public_id}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border pb-2 text-sm last:border-b-0 last:pb-0"
                >
                  <span className="font-medium">{item.mode_name}</span>
                  <span className="flex items-center gap-3 text-xs text-muted">
                    <span className="tabular-nums">{item.score} pontos</span>
                    <span className="tabular-nums">+{item.xp_awarded} XP</span>
                    {item.status === 'ABANDONED' && <span>abandonada</span>}
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
