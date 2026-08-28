import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, CheckCircle2, Clock, Layers, Sparkles, Zap } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { reviewApi } from '@/lib/api/flashcards'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import type { CardRating, ReviewResult } from '@/lib/api/types'
import {
  ORIGIN_LABEL,
  ORIGIN_TONE,
  RATING_LABEL,
  RATING_TONE,
  STATE_LABEL,
  explainInterval,
  intervalLabel,
} from './helpers'

const RATINGS: CardRating[] = ['AGAIN', 'HARD', 'GOOD', 'EASY']

export function ReviewPage() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<'queue' | 'flash'>('queue')
  const [index, setIndex] = useState(0)
  const [revealed, setRevealed] = useState(false)
  const [last, setLast] = useState<ReviewResult | null>(null)
  const [done, setDone] = useState(0)
  const shownAt = useRef(Date.now())

  const params = { mode }
  const queue = useQuery({
    queryKey: queryKeys.reviewQueue(params),
    queryFn: () => (mode === 'flash' ? reviewApi.flash(10) : reviewApi.queue()),
  })

  const items = useMemo(() => queue.data?.items ?? [], [queue.data])
  const current = items[index]

  useEffect(() => {
    setIndex(0)
    setRevealed(false)
    setDone(0)
    setLast(null)
  }, [mode])

  useEffect(() => {
    shownAt.current = Date.now()
  }, [current?.card.public_id, revealed])

  const answer = useMutation({
    mutationFn: (rating: CardRating) =>
      reviewApi.answer(current!.card.public_id, {
        rating,
        time_seconds: Math.min(3600, Math.round((Date.now() - shownAt.current) / 1000)),
      }),
    onSuccess: (result) => {
      setLast(result)
      setDone((value) => value + 1)
      setRevealed(false)
      setIndex((value) => value + 1)
      queryClient.invalidateQueries({ queryKey: queryKeys.reviewStats })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível registrar.'),
  })

  const postpone = useMutation({
    mutationFn: () => reviewApi.postpone(1),
    onSuccess: (result) => {
      toast.success(result.message)
      queryClient.invalidateQueries({ queryKey: ['review'] })
    },
  })

  if (queue.isLoading) return <SkeletonList rows={4} />
  if (queue.isError) return <ErrorState error={queue.error} onRetry={() => queue.refetch()} />

  const plan = queue.data!.plan
  const finished = index >= items.length

  return (
    <div className="space-y-6">
      <PageHeader
        title="Revisão"
        description="A fila respeita um teto diário. O que não cabe hoje é redistribuído, nunca empilhado."
        actions={
          <div className="flex items-center gap-2">
            <Button
              variant={mode === 'queue' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setMode('queue')}
            >
              <Layers /> Fila do dia
            </Button>
            <Button
              variant={mode === 'flash' ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setMode('flash')}
            >
              <Zap /> Relâmpago
            </Button>
          </div>
        }
      />

      <Card>
        <CardContent className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-6 text-sm">
          <span className="flex items-center gap-2">
            <Layers className="size-4 text-muted" aria-hidden />
            {queue.data!.total_cards} cartão(ões) no baralho
          </span>
          <span className="flex items-center gap-2">
            <CheckCircle2 className="size-4 text-success" aria-hidden />
            {queue.data!.reviewed_today + done} revisado(s) hoje
          </span>
          {plan.overdue_count > 0 && (
            <Badge variant="warning">{plan.overdue_count} vencido(s)</Badge>
          )}
          {plan.rescheduled_count > 0 && (
            <Badge variant="info">{plan.rescheduled_count} redistribuído(s)</Badge>
          )}
          <span className="w-full text-xs text-muted">{plan.summary}</span>
        </CardContent>
      </Card>

      {items.length === 0 && (
        <EmptyState
          icon={CheckCircle2}
          title="Nada para revisar agora"
          description={plan.summary}
        />
      )}

      {items.length > 0 && finished && (
        <EmptyState
          icon={Sparkles}
          title="Sessão concluída"
          description={`Você revisou ${done} cartão(ões). O próximo encontro de cada um já está agendado.`}
          action={
            <Button onClick={() => queue.refetch()}>
              <CalendarClock /> Ver a fila novamente
            </Button>
          }
        />
      )}

      {current && !finished && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm text-muted">
            <span>
              Cartão {index + 1} de {items.length}
            </span>
            <span className="flex items-center gap-2">
              <Badge variant={ORIGIN_TONE[current.card.origin]}>
                {ORIGIN_LABEL[current.card.origin]}
              </Badge>
              <Badge variant="outline">{STATE_LABEL[current.state.state]}</Badge>
            </span>
          </div>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${(index / items.length) * 100}%` }}
            />
          </div>

          <Card>
            <CardContent className="space-y-5 pt-6">
              <p className="text-lg leading-relaxed whitespace-pre-line">
                {current.card.front}
              </p>

              {current.card.hint && !revealed && (
                <p className="text-sm text-muted">Pista: {current.card.hint}</p>
              )}

              {revealed && (
                <div className="space-y-3 border-t border-border pt-4">
                  <p className="leading-relaxed whitespace-pre-line">{current.card.back}</p>
                  {current.card.source_quote && (
                    <p className="rounded-md bg-surface-muted p-3 text-xs text-muted italic">
                      “{current.card.source_quote}”
                      {current.card.source_document && (
                        <span className="mt-1 block not-italic text-subtle">
                          {current.card.source_document}
                          {current.card.source_page !== null &&
                            `, p. ${current.card.source_page}`}
                        </span>
                      )}
                    </p>
                  )}
                </div>
              )}

              {!revealed ? (
                <Button className="w-full" onClick={() => setRevealed(true)}>
                  Mostrar resposta
                </Button>
              ) : (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {RATINGS.map((rating) => (
                    <Button
                      key={rating}
                      variant={rating === 'GOOD' ? 'primary' : 'outline'}
                      loading={answer.isPending}
                      onClick={() => answer.mutate(rating)}
                      className={cn(
                        rating === 'AGAIN' && 'border-danger text-danger',
                        rating === 'EASY' && 'border-success text-success',
                      )}
                    >
                      {RATING_LABEL[rating]}
                    </Button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {last && (
        <Card className="border-primary">
          <CardContent className="space-y-2 pt-6">
            <p className="flex items-center gap-2 text-sm font-medium">
              <Clock className="size-4 text-primary" aria-hidden />
              Você verá este cartão de novo {intervalLabel(last.interval_days)}.
              <Badge variant={RATING_TONE[(last.breakdown.resposta as CardRating) ?? 'GOOD']}>
                {RATING_LABEL[(last.breakdown.resposta as CardRating) ?? 'GOOD']}
              </Badge>
            </p>
            <ul className="space-y-1 text-xs text-muted">
              {explainInterval(last.breakdown).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {items.length > 0 && !finished && (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            loading={postpone.isPending}
            onClick={() => postpone.mutate()}
          >
            Não vou conseguir hoje — adiar a fila
          </Button>
        </div>
      )}
    </div>
  )
}
