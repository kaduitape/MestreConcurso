import { cn } from '@/lib/utils'
import type { EvidenceLevel } from '@/lib/api/types'
import { EVIDENCE } from './evidence-meta'

export function EvidenceBadge({
  level,
  className,
}: {
  level: EvidenceLevel
  className?: string
}) {
  const style = EVIDENCE[level]
  const Icon = style.icon
  return (
    <span
      title={style.description}
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase',
        style.className,
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {style.label}
    </span>
  )
}
