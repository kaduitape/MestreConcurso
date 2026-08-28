import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SkeletonList } from '@/components/ui/skeleton'
import { EmptyState } from '@/components/feedback/empty-state'
import { ErrorState } from '@/components/feedback/error-state'
import { PageHeader } from '@/components/feedback/page-header'
import { ApiError } from '@/lib/api/client'
import { studyApi } from '@/lib/api/study'
import { queryKeys } from '@/lib/query-client'
import { cn } from '@/lib/utils'
import { KIND_TONE, formatMinutes } from './helpers'

function isoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function startOfWeek(reference: Date): Date {
  const date = new Date(reference)
  const offset = (date.getDay() + 6) % 7 // segunda como primeiro dia
  date.setDate(date.getDate() - offset)
  date.setHours(0, 0, 0, 0)
  return date
}

export function StudyCalendarPage() {
  const [anchor, setAnchor] = useState(() => startOfWeek(new Date()))

  const start = isoDate(anchor)
  const endDate = new Date(anchor)
  endDate.setDate(endDate.getDate() + 27)
  const end = isoDate(endDate)

  const calendar = useQuery({
    queryKey: queryKeys.studyCalendar(start, end),
    queryFn: () => studyApi.calendar(start, end),
    retry: false,
  })

  if (calendar.isLoading) return <SkeletonList rows={4} />

  if (calendar.isError) {
    const noPlan =
      calendar.error instanceof ApiError && calendar.error.code === 'no_active_plan'
    if (!noPlan) {
      return <ErrorState error={calendar.error} onRetry={() => calendar.refetch()} />
    }
    return (
      <EmptyState
        icon={CalendarDays}
        title="Sem plano, sem agenda"
        description="Monte seu plano de estudo para ver a distribuição das próximas semanas."
        action={
          <Button asChild>
            <Link to="/plano/novo">Montar meu plano</Link>
          </Button>
        }
      />
    )
  }

  const data = calendar.data!
  const byDay = new Map(data.days.map((day) => [day.day, day]))
  const today = isoDate(new Date())

  const weeks: Date[][] = []
  for (let week = 0; week < 4; week += 1) {
    const days: Date[] = []
    for (let day = 0; day < 7; day += 1) {
      const current = new Date(anchor)
      current.setDate(current.getDate() + week * 7 + day)
      days.push(current)
    }
    weeks.push(days)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Calendário de estudo"
        description="Quatro semanas de agenda, com o que está planejado e o que já foi cumprido."
        actions={
          <>
            <Button
              variant="outline"
              size="icon"
              aria-label="Semanas anteriores"
              onClick={() => {
                const previous = new Date(anchor)
                previous.setDate(previous.getDate() - 28)
                setAnchor(previous)
              }}
            >
              <ChevronLeft />
            </Button>
            <Button variant="outline" onClick={() => setAnchor(startOfWeek(new Date()))}>
              Hoje
            </Button>
            <Button
              variant="outline"
              size="icon"
              aria-label="Próximas semanas"
              onClick={() => {
                const next = new Date(anchor)
                next.setDate(next.getDate() + 28)
                setAnchor(next)
              }}
            >
              <ChevronRight />
            </Button>
          </>
        }
      />

      {data.exam_date && (
        <Badge variant="primary">
          Prova em {new Date(`${data.exam_date}T00:00:00`).toLocaleDateString('pt-BR')}
        </Badge>
      )}

      <div className="grid grid-cols-7 gap-1 text-center text-xs font-semibold tracking-wide text-subtle uppercase">
        {['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'].map((label) => (
          <span key={label}>{label}</span>
        ))}
      </div>

      <div className="space-y-1">
        {weeks.map((week, index) => (
          <div key={index} className="grid grid-cols-7 gap-1">
            {week.map((date) => {
              const key = isoDate(date)
              const day = byDay.get(key)
              const isToday = key === today
              const isExam = data.exam_date === key
              return (
                <Card
                  key={key}
                  className={cn(
                    'min-h-28',
                    isToday && 'border-primary',
                    isExam && 'border-danger',
                  )}
                >
                  <CardContent className="space-y-1 p-2">
                    <div className="flex items-center justify-between">
                      <span
                        className={cn(
                          'text-xs font-semibold',
                          isToday ? 'text-primary' : 'text-muted',
                        )}
                      >
                        {date.getDate()}
                      </span>
                      {day && day.planned_minutes > 0 && (
                        <span className="text-[10px] text-subtle">
                          {formatMinutes(day.planned_minutes)}
                        </span>
                      )}
                    </div>

                    {isExam && (
                      <span className="block rounded bg-danger-soft px-1.5 py-0.5 text-[10px] font-semibold text-danger">
                        PROVA
                      </span>
                    )}

                    {day?.tasks.slice(0, 3).map((task) => (
                      <span
                        key={task.public_id}
                        className={cn(
                          'block truncate rounded px-1.5 py-0.5 text-[10px]',
                          KIND_TONE[task.kind],
                          task.status === 'DONE' && 'line-through opacity-60',
                        )}
                        title={`${task.subject_label ?? task.kind_label} · ${formatMinutes(task.planned_minutes)}`}
                      >
                        {task.subject_label ?? task.kind_label}
                      </span>
                    ))}
                    {day && day.tasks.length > 3 && (
                      <span className="block text-[10px] text-subtle">
                        +{day.tasks.length - 3}
                      </span>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
