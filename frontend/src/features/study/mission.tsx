import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, ChevronRight, HelpCircle, Play, SkipForward, Undo2 } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ApiError } from '@/lib/api/client'
import { studyApi } from '@/lib/api/study'
import type { StudyTask, TodayMission } from '@/lib/api/types'
import { cn } from '@/lib/utils'
import { KIND_TONE, STATUS_LABEL, explainTask, formatMinutes } from './helpers'
import { StudyTimer } from './timer'

/**
 * "Sua missão de hoje": a lista que responde o que estudar agora.
 * Cada item abre o porquê — os mesmos números que o planejador usou.
 */
export function MissionPanel({ mission }: { mission: TodayMission }) {
  const queryClient = useQueryClient()
  const [explaining, setExplaining] = useState<StudyTask | null>(null)

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['study'] })

  const complete = useMutation({
    mutationFn: (publicId: string) => studyApi.completeTask(publicId),
    onSuccess: () => {
      toast.success('Tarefa concluída.')
      invalidate()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível concluir.'),
  })

  const skip = useMutation({
    mutationFn: (publicId: string) => studyApi.skipTask(publicId),
    onSuccess: invalidate,
  })

  const reopen = useMutation({
    mutationFn: (publicId: string) => studyApi.reopenTask(publicId),
    onSuccess: invalidate,
  })

  const pending = mission.tasks.filter((task) => task.status === 'PENDING')
  const remaining = pending.reduce((total, task) => total + task.planned_minutes, 0)

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-xl">Sua missão de hoje</CardTitle>
            <CardDescription>
              {mission.tasks.length === 0
                ? 'Nenhuma tarefa agendada para hoje.'
                : `${formatMinutes(mission.planned_minutes)} planejados · ${formatMinutes(remaining)} restantes`}
            </CardDescription>
          </div>
          {mission.days_until_exam !== null && mission.days_until_exam >= 0 && (
            <Badge variant="primary">{mission.days_until_exam} dias para a prova</Badge>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {mission.tasks.length === 0 && (
          <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted">
            Hoje não é um dia de estudo na sua disponibilidade. Você pode montar um sprint se
            tiver tempo livre.
          </p>
        )}

        <ul className="divide-y divide-border">
          {mission.tasks.map((task) => {
            const done = task.status === 'DONE'
            return (
              <li key={task.public_id} className="flex items-center gap-3 py-3">
                <span
                  className="h-10 w-1 shrink-0 rounded-full"
                  style={{ backgroundColor: `var(--${task.color_token})` }}
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p
                    className={cn(
                      'flex flex-wrap items-center gap-2 font-medium',
                      done && 'text-muted line-through',
                    )}
                  >
                    {task.subject_label ?? task.kind_label}
                    {/* Sem disciplina, o título já é o tipo: repetir seria ruído. */}
                    {task.subject_label && (
                      <span
                        className={cn(
                          'rounded-full px-2 py-0.5 text-[11px] font-semibold',
                          KIND_TONE[task.kind],
                        )}
                      >
                        {task.kind_label}
                      </span>
                    )}
                    {task.status !== 'PENDING' && task.status !== 'DONE' && (
                      <Badge variant="neutral">{STATUS_LABEL[task.status]}</Badge>
                    )}
                    {task.reschedule_count > 0 && <Badge variant="warning">remarcada</Badge>}
                  </p>
                  <p className="text-xs text-muted">
                    {formatMinutes(task.planned_minutes)}
                    {task.actual_minutes > 0 &&
                      ` · ${formatMinutes(task.actual_minutes)} registrados`}
                  </p>
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Por que esta tarefa: ${task.subject_label ?? task.kind_label}`}
                  onClick={() => setExplaining(task)}
                >
                  <HelpCircle />
                </Button>

                {done ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => reopen.mutate(task.public_id)}
                    loading={reopen.isPending && reopen.variables === task.public_id}
                  >
                    <Undo2 />
                  </Button>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => skip.mutate(task.public_id)}
                      loading={skip.isPending && skip.variables === task.public_id}
                    >
                      <SkipForward />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => complete.mutate(task.public_id)}
                      loading={complete.isPending && complete.variables === task.public_id}
                    >
                      <Check /> Concluir
                    </Button>
                  </>
                )}
              </li>
            )
          })}
        </ul>

        <div className="flex flex-wrap items-center gap-3">
          <StudyTimer taskPublicId={pending[0]?.public_id} />
          {pending.length > 0 && (
            <span className="flex items-center gap-1 text-sm text-muted">
              <Play className="size-3.5" aria-hidden /> começa por{' '}
              {pending[0]?.subject_label ?? pending[0]?.kind_label}
              <ChevronRight className="size-3.5" aria-hidden />
            </span>
          )}
        </div>
      </CardContent>

      <Dialog open={Boolean(explaining)} onOpenChange={(open) => !open && setExplaining(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Por que “{explaining?.subject_label ?? explaining?.kind_label}” está aqui?
            </DialogTitle>
            <DialogDescription>
              Estes são os números que o planejador usou. Nenhum deles vem de estimativa de
              modelo — são dados do edital e da sua disponibilidade.
            </DialogDescription>
          </DialogHeader>

          <ul className="space-y-2">
            {explainTask(explaining?.score_breakdown ?? {}).map((line) => (
              <li key={line} className="rounded-md bg-surface-muted p-3 text-sm">
                {line}
              </li>
            ))}
            {explainTask(explaining?.score_breakdown ?? {}).length === 0 && (
              <li className="text-sm text-muted">
                Esta tarefa não guarda detalhamento — foi criada manualmente.
              </li>
            )}
          </ul>

          <p className="mt-4 text-xs text-subtle">
            A priorização por desempenho e retenção (Mestre Priority Score) entra na Fase 6. Até
            lá, a distribuição é baseada no edital e no tempo disponível.
          </p>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
