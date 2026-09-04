import { BookOpen, Shield } from 'lucide-react'
import { cn } from '@/lib/utils'

export function BrandMark({
  compact = false,
  className,
}: {
  compact?: boolean
  className?: string
}) {
  return (
    <div className={cn('flex items-center gap-3', className)}>
      <span className="relative grid size-11 shrink-0 place-items-center text-white">
        <Shield className="absolute size-11 fill-game-purple/25 text-game-purple-light" />
        <BookOpen className="relative size-5 text-game-gold" strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="min-w-0 leading-none">
          <span className="block text-[10px] font-extrabold tracking-[0.28em] text-game-purple-light">
            GAME OF
          </span>
          <span className="mt-1 block truncate text-[17px] font-black tracking-[0.08em] text-white">
            CONCURSOS
          </span>
          <span className="mt-1.5 block text-[9px] font-medium tracking-[0.09em] text-slate-500">
            SUA APROVAÇÃO É A MISSÃO
          </span>
        </span>
      )}
    </div>
  )
}
