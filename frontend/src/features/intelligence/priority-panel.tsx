import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronDown, RefreshCw, Target } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { ApiError } from '@/lib/api/client'
import { intelligenceApi } from '@/lib/api/intelligence'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import type { Priority } from '@/lib/api/types'
import { priorityLabel, priorityTone } from './helpers'

function PriorityRow({ item }: { item: Priority }) {
  const [open, setOpen] = useState(false)
  const tone = priorityTone(item.score)

  return (
    <li className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-center gap-3 p-3 text-left"
      >
        <span
          className="size-3 shrink-0 rounded-full"
          style={{ backgroundColor: `var(--${item.color_token})` }}
          aria-hidden
        />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{item.label}</span>
          <span className="text-xs text-subtle">{priorityLabel(item.score)}</span>
        </span>
        <Badge variant={tone}>{item.score}</Badge>
        <ChevronDown
          className={cn('size-4 shrink-0 text-subtle transition', open && 'rotate-180')}
          aria-hidden
        />
      </button>

      {open && (
        <div className="space-y-3 border-t border-border p-3">
          <p className="text-xs text-muted">
            As parcelas abaixo somam exatamente {item.score} pontos.
          </p>
          <ul className="space-y-2">
            {item.contributions.map((part) => (
              <li key={part.key} className="space-y-1">
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className={cn(part.points === 0 && 'text-subtle')}>{part.label}</span>
                  <span className="font-mono text-xs tabular-nums">
                    {part.points} / {part.max_points}
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${(part.points / part.max_points) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-subtle">{part.detail}</p>
              </li>
            ))}
          </ul>
          {item.missing_signals.length > 0 && (
            <p className="rounded-md bg-warning-soft/40 p-2 text-xs">
              {item.missing_signals.length} sinal(is) ainda não existe(m) para você e valem
              zero. O score cresce conforme esses dados aparecem.
            </p>
          )}
        </div>
      )}
    </li>
  )
}

export function PriorityPanel() {
  const queryClient = useQueryClient()
  const priority = useQuery({
    queryKey: queryKeys.priority,
    queryFn: () => intelligenceApi.priority(),
  })

  const recompute = useMutation({
    mutationFn: () => intelligenceApi.recomputePriority(),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.priority, result)
      toast.success(
        result.items.length > 0 ? 'Prioridades recalculadas.' : 'Nada a priorizar ainda.',
        { description: result.notes[0] },
      )
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível recalcular.'),
  })

  const data = priority.data

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="space-y-1">
          <CardTitle>O que estudar primeiro</CardTitle>
          <CardDescription>
            Cada disciplina abre o “por quê?” com as parcelas que somam o número exibido.
          </CardDescription>
        </div>
        <Button
          variant="outline"
          size="sm"
          loading={recompute.isPending}
          onClick={() => recompute.mutate()}
        >
          <RefreshCw /> Recalcular
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {priority.isLoading && <SkeletonList rows={3} />}
        {priority.isError && (
          <ErrorState error={priority.error} onRetry={() => priority.refetch()} />
        )}

        {data && data.items.length === 0 && (
          <EmptyState
            icon={Target}
            title="Priority Score ainda não calculado"
            description={
              data.notes[0] ??
              'O score depende do seu plano de estudo ativo e dos sinais que você já gerou.'
            }
            action={
              <Button loading={recompute.isPending} onClick={() => recompute.mutate()}>
                Calcular agora
              </Button>
            }
          />
        )}

        {data && data.items.length > 0 && (
          <>
            <ul className="space-y-2">
              {data.items.map((item) => (
                <PriorityRow key={item.scope_key} item={item} />
              ))}
            </ul>
            {data.computed_at && (
              <p className="text-xs text-subtle">
                Calculado em {new Date(data.computed_at).toLocaleString('pt-BR')}.
              </p>
            )}
          </>
        )}

        {recompute.data?.notes.map((note) => (
          <p key={note} className="rounded-md bg-surface-muted p-2 text-xs text-muted">
            {note}
          </p>
        ))}
      </CardContent>
    </Card>
  )
}
