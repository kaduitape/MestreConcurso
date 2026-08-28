import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Target } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { CountUp } from './xp-bar'
import { LevelBadge, RankBadge } from './rank-badge'
import { StreakCounter } from './streak-counter'

/** Faixa compacta da tela Hoje: sequência, nível, rank e progresso do dia. */
export function GameHeader() {
  const profile = useQuery({
    queryKey: queryKeys.gameProfile,
    queryFn: () => gameApi.profile(),
  })
  const board = useQuery({
    queryKey: queryKeys.gameMissions,
    queryFn: () => gameApi.missionsToday(),
  })

  if (!profile.data) return null
  const data = profile.data
  const missions = board.data
  const ratio = missions && missions.total > 0 ? missions.completed / missions.total : 0

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-border bg-surface p-4">
      <StreakCounter streak={data.streak} compact />
      <LevelBadge level={data.level.level} />
      <RankBadge rank={data.rank} size="sm" />

      <span className="text-sm text-muted">
        <CountUp value={data.xp_today} /> XP hoje
      </span>

      {missions && missions.total > 0 && (
        <div className="flex min-w-40 flex-1 items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${Math.round(ratio * 100)}%` }}
            />
          </div>
          <span className="text-xs text-subtle whitespace-nowrap">
            {missions.completed}/{missions.total} missões
          </span>
        </div>
      )}

      <Button variant="outline" size="sm" asChild className="ml-auto">
        <Link to="/missoes">
          <Target /> Missões
        </Link>
      </Button>
    </div>
  )
}
