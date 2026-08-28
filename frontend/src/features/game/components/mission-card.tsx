import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { CheckCircle2, ChevronDown, Clock, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Mission } from '@/lib/api/types'
import { PRIORITY_LABEL, PRIORITY_TONE, formatEstimate } from '../helpers'

export function MissionProgress({ mission }: { mission: Mission }) {
  const reduce = useReducedMotion()
  return (
    <div className="space-y-1">
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-muted">
        <motion.div
          className={cn(
            'h-full rounded-full',
            mission.status === 'PENDING' ? 'bg-primary' : 'bg-success',
          )}
          initial={reduce ? false : { width: 0 }}
          animate={{ width: `${Math.round(mission.progress_ratio * 100)}%` }}
          transition={{ duration: reduce ? 0 : 0.6, ease: 'easeOut' }}
        />
      </div>
      <p className="text-xs text-subtle tabular-nums">
        {mission.current_value} / {mission.target_value}
      </p>
    </div>
  )
}

export function MissionCard({
  mission,
  onClaim,
  claiming = false,
}: {
  mission: Mission
  onClaim?: (mission: Mission) => void
  claiming?: boolean
}) {
  const [showWhy, setShowWhy] = useState(false)
  const claimed = mission.status === 'CLAIMED'
  const done = mission.status === 'DONE'

  return (
    <li
      className={cn(
        'space-y-3 rounded-lg border p-4 transition',
        claimed ? 'border-success/40 bg-success-soft/20' : 'border-border',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            {claimed ? (
              <Badge variant="success">
                <CheckCircle2 className="size-3" aria-hidden /> Concluída
              </Badge>
            ) : (
              <Badge variant={PRIORITY_TONE[mission.priority]}>
                {PRIORITY_LABEL[mission.priority]}
              </Badge>
            )}
            <span className="inline-flex items-center gap-1 text-xs text-subtle">
              <Clock className="size-3" aria-hidden />
              {formatEstimate(mission.estimated_minutes)}
            </span>
          </div>
          <p className={cn('font-medium', claimed && 'text-muted line-through')}>
            {mission.title}
          </p>
          <p className="text-sm text-muted">{mission.description}</p>
        </div>
        <Badge variant="primary">+{mission.xp_reward} XP</Badge>
      </div>

      {!claimed && <MissionProgress mission={mission} />}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setShowWhy((value) => !value)}
          aria-expanded={showWhy}
          className="flex items-center gap-1 text-xs font-medium text-primary"
        >
          por quê?
          <ChevronDown
            className={cn('size-3 transition', showWhy && 'rotate-180')}
            aria-hidden
          />
        </button>

        {done && onClaim && (
          <Button
            size="sm"
            className="ml-auto"
            loading={claiming}
            onClick={() => onClaim(mission)}
          >
            <Sparkles /> Resgatar {mission.xp_reward} XP
          </Button>
        )}
      </div>

      {showWhy && (
        <p className="rounded-md bg-surface-muted p-3 text-xs text-muted">
          {mission.rationale}
        </p>
      )}
    </li>
  )
}
