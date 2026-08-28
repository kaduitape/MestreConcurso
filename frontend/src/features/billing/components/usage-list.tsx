import { cn } from '@/lib/utils'
import type { Quota } from '@/lib/api/types'

/**
 * O que o plano concede e quanto já foi usado.
 *
 * Recurso ilimitado não desenha barra: uma barra vazia sugeriria um teto que não
 * existe. E recurso fora do plano aparece com o motivo, não escondido.
 */
export function UsageList({ items }: { items: Quota[] }) {
  return (
    <ul className="space-y-3">
      {items.map((item) => {
        const ratio = item.limit && item.limit > 0 ? Math.min(1, item.used / item.limit) : null
        return (
          <li key={item.feature} className="space-y-1">
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span className={cn(!item.allowed && !item.limit && 'text-subtle')}>
                {item.label}
              </span>
              <span className="font-mono text-xs tabular-nums text-muted">
                {item.limit === null
                  ? item.allowed
                    ? 'sem limite'
                    : 'não incluído'
                  : `${item.used} / ${item.limit}`}
              </span>
            </div>

            {ratio !== null && (
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-muted">
                <div
                  className={cn('h-full rounded-full', ratio >= 1 ? 'bg-danger' : 'bg-primary')}
                  style={{ width: `${Math.round(ratio * 100)}%` }}
                />
              </div>
            )}

            {item.reason && <p className="text-xs text-warning">{item.reason}</p>}
            {item.allowed && item.resets_on && (
              <p className="text-xs text-subtle">
                Renova em {new Date(item.resets_on).toLocaleDateString('pt-BR')}.
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}
