import { cn } from '@/lib/utils'
import type { BattleWeek, SubjectScore } from '@/lib/api/types'

/**
 * A barra do placar. Uma barra só, dividida: a fatia da banca é literalmente o
 * que sobrou dos acertos do candidato — por isso as duas somam 100.
 */
export function BattleBar({
  you,
  board,
  boardName,
  size = 'md',
}: {
  you: number
  board: number
  boardName: string
  size?: 'sm' | 'md'
}) {
  return (
    <div className="space-y-1.5">
      <div
        className={cn(
          'flex w-full overflow-hidden rounded-full bg-surface-muted',
          size === 'sm' ? 'h-2.5' : 'h-4',
        )}
        role="img"
        aria-label={`Você ${you} pontos, ${boardName} ${board} pontos.`}
      >
        <div className="h-full bg-primary transition-[width]" style={{ width: `${you}%` }} />
        <div
          className="h-full bg-danger/70 transition-[width]"
          style={{ width: `${board}%` }}
        />
      </div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-primary">Você {you}</span>
        <span className="font-medium text-danger">
          {boardName} {board}
        </span>
      </div>
    </div>
  )
}

export function SubjectScoreRow({
  subject,
  boardName,
}: {
  subject: SubjectScore
  boardName: string
}) {
  if (!subject.is_sufficient) {
    return (
      <li className="space-y-1 border-t border-border py-3 first:border-t-0">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm text-subtle">{subject.subject_name}</span>
          <span className="text-xs text-subtle">amostra insuficiente</span>
        </div>
        <p className="text-xs text-subtle">{subject.insufficient_reason}</p>
      </li>
    )
  }

  return (
    <li className="space-y-1.5 border-t border-border py-3 first:border-t-0">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-medium">{subject.subject_name}</span>
        <span className="font-mono text-xs tabular-nums text-muted">
          {subject.you} × {subject.board}
        </span>
      </div>
      <BattleBar you={subject.you} board={subject.board} boardName={boardName} size="sm" />
      <p className="text-xs text-subtle">{subject.answers} respostas</p>
    </li>
  )
}

/** Evolução semanal do acerto. Sem eixo inventado: a escala é 0 a 100%. */
export function BattleEvolution({ weeks }: { weeks: BattleWeek[] }) {
  if (weeks.length < 2) {
    return (
      <p className="text-xs text-subtle">
        A evolução aparece a partir da segunda semana com respostas desta banca.
      </p>
    )
  }

  const width = 100
  const height = 32
  const step = width / (weeks.length - 1)
  const points = weeks
    .map((week, index) => `${index * step},${height - week.accuracy * height}`)
    .join(' ')

  return (
    <div className="space-y-1">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="h-10 w-full"
        role="img"
        aria-label={`Acerto por semana: ${weeks
          .map((week) => `${Math.round(week.accuracy * 100)}%`)
          .join(', ')}.`}
      >
        <polyline
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          className="text-primary"
        />
      </svg>
      <div className="flex justify-between text-[11px] text-subtle">
        <span>{Math.round(weeks[0].accuracy * 100)}%</span>
        <span>
          {weeks.length} semanas · {Math.round(weeks[weeks.length - 1].accuracy * 100)}% agora
        </span>
      </div>
    </div>
  )
}
