import { useCallback, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { Check, ChevronLeft, ChevronRight, Flag, Pause, Play } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { SkeletonList } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/feedback/error-state'
import { ApiError } from '@/lib/api/client'
import { simulationsApi } from '@/lib/api/questions'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import { formatSeconds } from '@/features/study/helpers'
import { DIFFICULTY_LABEL } from '@/features/questions/helpers'

export function SimulationRunPage() {
  const { attemptId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [index, setIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, string | null>>({})
  const [remaining, setRemaining] = useState<number | null>(null)
  const [confirmFinish, setConfirmFinish] = useState(false)
  const [questionStartedAt, setQuestionStartedAt] = useState(() => Date.now())

  const run = useQuery({
    queryKey: queryKeys.simulationAttempt(attemptId),
    queryFn: () => simulationsApi.attempt(attemptId),
    enabled: Boolean(attemptId),
  })

  // O estado salvo no servidor manda: recarregar a página retoma de onde parou.
  useEffect(() => {
    if (!run.data) return
    setAnswers(
      Object.fromEntries(
        run.data.questions.map((item) => [item.question.public_id, item.selected_letter]),
      ),
    )
    setRemaining(run.data.remaining_seconds)
  }, [run.data])

  const paused = run.data?.attempt.status === 'PAUSED'
  const finished = run.data?.attempt.status === 'FINISHED'

  const finish = useMutation({
    mutationFn: () => simulationsApi.finish(attemptId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['simulations'] })
      navigate(`/simulados/resultado/${attemptId}`, { replace: true })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível encerrar.'),
  })

  const finishNow = useCallback(() => finish.mutate(), [finish])

  // Cronômetro local; o tempo oficial é o que o servidor acumula a cada pausa.
  useEffect(() => {
    if (remaining === null || paused || finished) return
    if (remaining <= 0) {
      finishNow()
      return
    }
    const timer = setInterval(
      () => setRemaining((value) => (value === null ? null : value - 1)),
      1000,
    )
    return () => clearInterval(timer)
  }, [remaining, paused, finished, finishNow])

  useEffect(() => {
    if (finished) navigate(`/simulados/resultado/${attemptId}`, { replace: true })
  }, [finished, attemptId, navigate])

  const save = useMutation({
    mutationFn: (input: { questionId: string; letter: string | null; seconds: number }) =>
      simulationsApi.saveAnswer(attemptId, {
        question_public_id: input.questionId,
        letter: input.letter,
        time_seconds: input.seconds,
      }),
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'A resposta não foi salva. Tente de novo.',
      ),
  })

  const toggle = useMutation({
    mutationFn: () =>
      paused ? simulationsApi.resume(attemptId) : simulationsApi.pause(attemptId),
    onSuccess: () => run.refetch(),
  })

  const questions = useMemo(() => run.data?.questions ?? [], [run.data])
  const currentItem = questions[index]
  const answeredCount = Object.values(answers).filter((letter) => letter !== null).length

  function mark(letter: string | null) {
    if (!currentItem || paused) return
    const questionId = currentItem.question.public_id
    setAnswers((previous) => ({ ...previous, [questionId]: letter }))
    const seconds = Math.min(3600, Math.round((Date.now() - questionStartedAt) / 1000))
    save.mutate({ questionId, letter, seconds })
  }

  function goTo(next: number) {
    setIndex(Math.max(0, Math.min(questions.length - 1, next)))
    setQuestionStartedAt(Date.now())
  }

  if (run.isLoading) return <SkeletonList rows={5} />
  if (run.isError) return <ErrorState error={run.error} onRetry={() => run.refetch()} />
  if (!currentItem) return null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface p-4">
        <div>
          <p className="font-medium">{run.data?.attempt.simulation?.name ?? 'Simulado'}</p>
          <p className="text-sm text-muted">
            {answeredCount} de {questions.length} respondidas
          </p>
        </div>
        <div className="flex items-center gap-3">
          {remaining !== null && (
            <span
              className={cn(
                'font-mono text-2xl tabular-nums',
                remaining <= 300 && 'text-danger',
              )}
              aria-label="Tempo restante"
            >
              {formatSeconds(remaining)}
            </span>
          )}
          <Button variant="outline" loading={toggle.isPending} onClick={() => toggle.mutate()}>
            {paused ? <Play /> : <Pause />}
            {paused ? 'Retomar' : 'Pausar'}
          </Button>
          <Button variant="danger" onClick={() => setConfirmFinish(true)}>
            <Flag /> Encerrar
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {questions.map((item, position) => {
          const answered = answers[item.question.public_id] != null
          return (
            <button
              key={item.question.public_id}
              type="button"
              onClick={() => goTo(position)}
              aria-label={`Ir para a questão ${position + 1}`}
              className={cn(
                'size-8 rounded-md border text-xs font-medium transition',
                position === index && 'border-primary ring-2 ring-primary/40',
                answered
                  ? 'border-primary bg-primary-soft text-primary'
                  : 'border-border text-muted hover:bg-surface-muted',
              )}
            >
              {position + 1}
            </button>
          )
        })}
      </div>

      {paused && (
        <p className="rounded-md border border-warning bg-warning-soft/40 p-3 text-sm">
          Simulado pausado. O cronômetro está parado e as respostas ficam bloqueadas até você
          retomar.
        </p>
      )}

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">
              Questão {index + 1} de {questions.length}
            </Badge>
            {currentItem.question.subject_name && (
              <Badge variant="primary">{currentItem.question.subject_name}</Badge>
            )}
            <Badge variant="neutral">{DIFFICULTY_LABEL[currentItem.question.difficulty]}</Badge>
          </div>

          <p className="text-sm leading-relaxed whitespace-pre-line">
            {currentItem.question.statement}
          </p>

          <ul className="space-y-2">
            {currentItem.question.alternatives.map((alternative) => {
              const selected = answers[currentItem.question.public_id] === alternative.letter
              return (
                <li key={alternative.public_id}>
                  <button
                    type="button"
                    disabled={paused}
                    onClick={() => mark(selected ? null : alternative.letter)}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-md border p-3 text-left text-sm transition',
                      selected
                        ? 'border-primary bg-primary-soft/40'
                        : 'border-border hover:bg-surface-muted',
                      paused && 'cursor-not-allowed opacity-60',
                    )}
                  >
                    <span className="mt-0.5 font-semibold">{alternative.letter}</span>
                    <span className="flex-1">{alternative.content}</span>
                    {selected && <Check className="size-4 shrink-0 text-primary" />}
                  </button>
                </li>
              )
            })}
          </ul>

          <p className="text-xs text-subtle">
            {save.isPending ? 'Salvando…' : 'Cada marcação é salva automaticamente.'}
          </p>

          <div className="flex items-center justify-between">
            <Button variant="outline" disabled={index === 0} onClick={() => goTo(index - 1)}>
              <ChevronLeft /> Anterior
            </Button>
            <Button
              variant="outline"
              disabled={index >= questions.length - 1}
              onClick={() => goTo(index + 1)}
            >
              Próxima <ChevronRight />
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={confirmFinish} onOpenChange={setConfirmFinish}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Encerrar o simulado?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted">
            {questions.length - answeredCount > 0
              ? `${questions.length - answeredCount} questão(ões) ficarão em branco e contarão como não respondidas na correção.`
              : 'Todas as questões foram respondidas. A correção completa aparece na sequência.'}
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setConfirmFinish(false)}>
              Voltar ao simulado
            </Button>
            <Button variant="danger" loading={finish.isPending} onClick={() => finish.mutate()}>
              Encerrar e corrigir
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
