import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Gift, Sparkles, Target } from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import type { Mission } from '@/lib/api/types'
import { CountUp, XPBar } from './components/xp-bar'
import { LevelBadge, RankBadge } from './components/rank-badge'
import { MissionCard } from './components/mission-card'
import { StreakCounter } from './components/streak-counter'

export function MissionsPage() {
  const queryClient = useQueryClient()
  const reduce = useReducedMotion()
  const [flash, setFlash] = useState<string | null>(null)

  const board = useQuery({
    queryKey: queryKeys.gameMissions,
    queryFn: () => gameApi.missionsToday(),
  })
  const profile = useQuery({
    queryKey: queryKeys.gameProfile,
    queryFn: () => gameApi.profile(),
  })

  const claim = useMutation({
    mutationFn: (mission: Mission) => gameApi.claim(mission.public_id),
    onSuccess: (result) => {
      setFlash(`+${result.xp_awarded} XP`)
      window.setTimeout(() => setFlash(null), 2200)

      if (result.leveled_up) {
        toast.success(`Nível ${result.level} alcançado.`)
      }
      if (result.bonus) {
        toast.success(`Bônus de ${result.bonus.amount} XP`, {
          description: result.bonus.reason,
        })
      }
      queryClient.invalidateQueries({ queryKey: ['game'] })
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : 'Não foi possível resgatar.'),
  })

  if (board.isLoading) return <SkeletonList rows={4} />
  if (board.isError) return <ErrorState error={board.error} onRetry={() => board.refetch()} />

  const data = board.data!
  const ratio = data.total > 0 ? data.completed / data.total : 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="Central de Missões"
        description="Cada missão nasce de um sinal real do seu estudo — e diz qual."
        actions={
          profile.data && (
            <div className="flex items-center gap-2">
              <StreakCounter streak={profile.data.streak} compact />
              <LevelBadge level={profile.data.level.level} />
              <RankBadge rank={profile.data.rank} size="sm" />
            </div>
          )
        }
      />

      <Card>
        <CardContent className="space-y-4 pt-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-medium">Progresso de hoje</p>
            <p className="text-sm text-muted">
              {data.completed} de {data.total} missões
            </p>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-muted">
            <motion.div
              className="h-full rounded-full bg-primary"
              initial={reduce ? false : { width: 0 }}
              animate={{ width: `${Math.round(ratio * 100)}%` }}
              transition={{ duration: reduce ? 0 : 0.7, ease: 'easeOut' }}
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-sm text-muted">
              XP hoje: <CountUp value={data.xp_today} /> XP
            </span>
            {profile.data && (
              <div className="min-w-56 flex-1">
                <XPBar level={profile.data.level} compact />
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {data.missions.length === 0 && (
        <EmptyState
          icon={Target}
          title={data.has_plan ? 'Nenhuma missão para hoje' : 'Monte o seu plano de estudo'}
          description={data.empty_reason ?? 'Sem sinais para gerar missão hoje.'}
          action={
            !data.has_plan && (
              <Button asChild>
                <a href="/plano/novo">Montar plano</a>
              </Button>
            )
          }
        />
      )}

      {data.missions.length > 0 && (
        <ul className="space-y-3">
          {data.missions.map((mission) => (
            <MissionCard
              key={mission.public_id}
              mission={mission}
              claiming={claim.isPending && claim.variables?.public_id === mission.public_id}
              onClaim={(item) => claim.mutate(item)}
            />
          ))}
        </ul>
      )}

      {data.total > 0 && (
        <Card className={data.all_done ? 'border-success' : undefined}>
          <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
            <div className="flex items-center gap-3">
              <Gift className="size-5 text-primary" aria-hidden />
              <div>
                <p className="text-sm font-medium">Bônus do dia</p>
                <p className="text-xs text-muted">
                  {data.bonus_claimed
                    ? 'Bônus já creditado hoje.'
                    : data.all_done
                      ? 'Resgate a última missão para receber o bônus.'
                      : `Falta${data.total - data.completed > 1 ? 'm' : ''} ${
                          data.total - data.completed
                        } missão(ões).`}
                </p>
              </div>
            </div>
            <Badge variant={data.bonus_claimed ? 'success' : 'primary'}>
              +{data.bonus_xp} XP
            </Badge>
          </CardContent>
        </Card>
      )}

      <AnimatePresence>
        {flash && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="pointer-events-none fixed bottom-8 left-1/2 z-50 -translate-x-1/2 rounded-full bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-soft"
          >
            <span className="inline-flex items-center gap-2">
              <Sparkles className="size-4" aria-hidden />
              {flash}
            </span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
