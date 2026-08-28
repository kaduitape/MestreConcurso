import { CalendarClock, Gift, Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Season, SeasonReward } from '@/lib/api/types'

function RewardRow({ reward, earned }: { reward: SeasonReward; earned: boolean }) {
  return (
    <li className="flex items-start gap-3 border-t border-border py-3 first:border-t-0">
      <span
        className={cn(
          'mt-0.5 rounded-full p-1.5',
          earned ? 'bg-success-soft text-success' : 'bg-surface-muted text-subtle',
        )}
      >
        {earned ? (
          <Gift className="size-3.5" aria-hidden />
        ) : (
          <Lock className="size-3.5" aria-hidden />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn('text-sm font-medium', !earned && 'text-subtle')}>{reward.label}</p>
        <p className="text-xs text-muted">{reward.utility}</p>
        <p className="mt-0.5 text-xs text-subtle">
          {earned ? 'Critério cumprido' : reward.criterion}
        </p>
      </div>
    </li>
  )
}

/**
 * O andamento da temporada. Nenhuma recompensa é surpresa: as que ainda não
 * vieram aparecem com o critério à vista.
 */
export function SeasonProgress({ season }: { season: Season }) {
  const standing = season.standing

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width]"
            style={{ width: `${Math.round(season.progress * 100)}%` }}
          />
        </div>
        <p className="flex items-center gap-1.5 text-xs text-subtle">
          <CalendarClock className="size-3.5" aria-hidden />
          {season.days_left === 0
            ? 'Último dia da temporada.'
            : `Faltam ${season.days_left} dias para o fim da temporada.`}
        </p>
      </div>

      {standing && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-sm text-muted">XP na temporada</p>
            <p className="text-2xl font-semibold tabular-nums">{standing.seasonal_xp}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Dias qualificados</p>
            <p className="text-2xl font-semibold tabular-nums">{standing.qualified_days}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Questões</p>
            <p className="text-2xl font-semibold tabular-nums">{standing.questions}</p>
          </div>
          <div>
            <p className="text-sm text-muted">Desafios</p>
            <p className="text-2xl font-semibold tabular-nums">{standing.challenges}</p>
          </div>
        </div>
      )}

      <div>
        <p className="mb-1 text-sm font-medium">Recompensas</p>
        <ul>
          {season.rewards.map((item) => (
            <RewardRow key={item.slug} reward={item} earned />
          ))}
          {season.missed_rewards.map((item) => (
            <RewardRow key={item.slug} reward={item} earned={false} />
          ))}
        </ul>
      </div>

      <p className="rounded-md bg-surface-muted p-3 text-xs text-muted">{season.note}</p>
    </div>
  )
}
