import { Lock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { GameAchievement } from '@/lib/api/types'

export function AchievementCard({ achievement }: { achievement: GameAchievement }) {
  return (
    <li
      className={cn(
        'space-y-2 rounded-lg border p-4 transition',
        achievement.unlocked ? 'border-success/40 bg-success-soft/20' : 'border-border',
      )}
    >
      <div className="flex items-start gap-3">
        <span
          className={cn('text-2xl', !achievement.unlocked && 'opacity-40 grayscale')}
          aria-hidden
        >
          {achievement.icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium">{achievement.name}</p>
          <p className="text-sm text-muted">{achievement.description}</p>
        </div>
        <Badge variant={achievement.unlocked ? 'success' : 'outline'}>
          {achievement.unlocked ? 'Desbloqueada' : `+${achievement.xp_reward} XP`}
        </Badge>
      </div>

      {!achievement.unlocked && achievement.ratio !== null && (
        <div className="space-y-1">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round(achievement.ratio * 100)}%` }}
            />
          </div>
          <p className="text-xs text-subtle tabular-nums">
            {Math.round(achievement.current)} / {Math.round(achievement.threshold)}
          </p>
        </div>
      )}

      {achievement.blocked_reason && (
        <p className="flex items-center gap-1.5 text-xs text-warning">
          <Lock className="size-3" aria-hidden />
          {achievement.blocked_reason}
        </p>
      )}

      {achievement.unlocked && achievement.unlocked_at && (
        <p className="text-xs text-subtle">
          Desbloqueada em {new Date(achievement.unlocked_at).toLocaleDateString('pt-BR')}.
        </p>
      )}
    </li>
  )
}
