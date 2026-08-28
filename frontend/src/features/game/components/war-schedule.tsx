import { cn } from '@/lib/utils'
import type { WarCampaign } from '@/lib/api/types'

/**
 * O calendário do período. Dia abaixo da meta aparece como fato, não como
 * acusação — e o dia corrente segue em aberto até acabar.
 */
export function WarSchedule({ campaign }: { campaign: WarCampaign }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {campaign.schedule.map((day) => (
          <span
            key={day.day}
            title={`${new Date(day.day).toLocaleDateString('pt-BR')} · ${day.minutes} min · ${day.questions} questões`}
            className={cn(
              'flex size-9 items-center justify-center rounded-md border text-xs tabular-nums',
              day.met && 'border-success bg-success-soft text-success',
              !day.met && day.is_future && 'border-dashed border-border text-subtle',
              !day.met && !day.is_future && 'border-border text-muted',
            )}
          >
            {new Date(day.day).getDate()}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-subtle">
        <span>meta diária: {campaign.daily_minutes} min</span>
        {campaign.daily_questions > 0 && <span>{campaign.daily_questions} questões</span>}
        <span>{campaign.days_met} cumpridos</span>
        {campaign.days_missed > 0 && <span>{campaign.days_missed} abaixo da meta</span>}
      </div>

      <p className="text-sm text-muted">{campaign.message}</p>

      {campaign.warnings.length > 0 && (
        <ul className="space-y-1 rounded-md bg-warning-soft/40 p-3">
          {campaign.warnings.map((warning) => (
            <li key={warning.message} className="text-xs">
              {warning.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
