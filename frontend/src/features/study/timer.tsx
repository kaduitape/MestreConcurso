import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pause, Play, Square, Timer as TimerIcon } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { GameButton } from '@/components/game/game-button'
import { ApiError } from '@/lib/api/client'
import { studyApi } from '@/lib/api/study'
import { queryKeys } from '@/lib/query-client'
import type { StudySession } from '@/lib/api/types'
import { formatSeconds } from './helpers'

/** Segundos já acumulados + o trecho corrente, quando a sessão está rodando. */
function elapsedSeconds(session: StudySession, now: number): number {
  if (session.status !== 'RUNNING') return session.focus_seconds
  const started = new Date(session.started_at).getTime()
  return session.focus_seconds + Math.max(0, Math.floor((now - started) / 1000))
}

export function StudyTimer({ taskPublicId }: { taskPublicId?: string }) {
  const queryClient = useQueryClient()
  const [now, setNow] = useState(() => Date.now())

  const session = useQuery({
    queryKey: queryKeys.studySession,
    queryFn: studyApi.currentSession,
    refetchInterval: 60_000,
  })

  const current = session.data ?? null
  const isRunning = current?.status === 'RUNNING'

  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [isRunning])

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['study'] })
  }

  const start = useMutation({
    mutationFn: () => studyApi.startSession(taskPublicId),
    onSuccess: invalidate,
    onError: (error: unknown) =>
      toast.error(
        error instanceof ApiError ? error.message : 'Não foi possível iniciar o cronômetro.',
      ),
  })

  const pause = useMutation({
    mutationFn: () => studyApi.pauseSession(current!.public_id),
    onSuccess: invalidate,
  })

  const resume = useMutation({
    mutationFn: () => studyApi.resumeSession(current!.public_id),
    onSuccess: invalidate,
  })

  const finish = useMutation({
    mutationFn: () => studyApi.finishSession(current!.public_id),
    onSuccess: (finished) => {
      toast.success(
        `Sessão registrada: ${Math.round(finished.focus_seconds / 60)} minuto(s) de foco.`,
      )
      invalidate()
    },
  })

  if (!current) {
    return (
      <GameButton size="lg" onClick={() => start.mutate()} loading={start.isPending}>
        <Play /> Começar missão
      </GameButton>
    )
  }

  return (
    <Card className="border-primary/40">
      <CardContent className="flex flex-wrap items-center gap-4 p-4">
        <TimerIcon className="size-5 text-primary" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-mono text-2xl font-semibold tabular-nums">
            {formatSeconds(elapsedSeconds(current, now))}
          </p>
          <p className="truncate text-xs text-muted">
            {current.subject_label ?? 'Sessão livre'}
            {current.status === 'PAUSED' && ' · pausada'}
          </p>
        </div>

        {current.status === 'PAUSED' && <Badge variant="warning">Pausada</Badge>}

        <div className="flex gap-2">
          {isRunning ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => pause.mutate()}
              loading={pause.isPending}
            >
              <Pause /> Pausar
            </Button>
          ) : (
            <Button
              variant="outline"
              size="sm"
              onClick={() => resume.mutate()}
              loading={resume.isPending}
            >
              <Play /> Retomar
            </Button>
          )}
          <Button size="sm" onClick={() => finish.mutate()} loading={finish.isPending}>
            <Square /> Encerrar
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
