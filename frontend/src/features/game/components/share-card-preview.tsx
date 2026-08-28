import type { ShareCard } from '@/lib/api/types'

/**
 * A prévia do card. O que não tem amostra aparece como lacuna declarada — é
 * justamente o que impediria o card de virar propaganda com número frágil.
 */
export function ShareCardPreview({ card }: { card: ShareCard }) {
  return (
    <div className="space-y-4">
      <div className="space-y-4 rounded-xl border border-border bg-surface-muted p-5">
        <p className="text-lg font-semibold">{card.headline}</p>

        <div className="grid grid-cols-2 gap-4">
          {card.stats.map((stat) => (
            <div key={stat.key}>
              <p className="text-xs text-muted">{stat.label}</p>
              <p className="text-2xl font-semibold tabular-nums">{stat.value}</p>
              <p className="text-[11px] text-subtle">{stat.detail}</p>
            </div>
          ))}
        </div>

        <p className="border-t border-border pt-3 text-xs text-muted">{card.footer}</p>
      </div>

      {card.omitted.length > 0 && (
        <div className="space-y-1 rounded-md border border-dashed border-border p-3">
          <p className="text-xs font-medium">Fora do card</p>
          <ul className="space-y-0.5">
            {card.omitted.map((item) => (
              <li key={item} className="text-xs text-muted">
                {item}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
