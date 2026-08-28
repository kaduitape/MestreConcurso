import { cn } from '@/lib/utils'
import type { League } from '@/lib/api/types'

/**
 * A tabela da divisão. Quem não escolheu aparecer com nome é uma posição, não
 * uma pessoa — e a comparação só existe entre candidatos ao mesmo cargo.
 */
export function LeagueTable({ league }: { league: League }) {
  if (league.members.length === 0) {
    return <p className="text-sm text-muted">{league.empty_reason}</p>
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        {league.context_label} · {league.division_label} · {league.participants} candidatos no
        contexto
      </p>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[26rem] text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-subtle">
              <th className="w-12 py-2 font-medium">#</th>
              <th className="py-2 font-medium">Candidato</th>
              <th className="py-2 text-right font-medium">XP</th>
              <th className="py-2 text-right font-medium">Dias ativos</th>
            </tr>
          </thead>
          <tbody>
            {league.members.map((member) => (
              <tr
                key={member.position}
                className={cn(
                  'border-b border-border last:border-b-0',
                  member.is_you && 'bg-primary-soft/40 font-medium',
                )}
              >
                <td className="py-2 tabular-nums text-subtle">{member.position}</td>
                <td className="py-2">
                  {member.label}
                  {member.is_you && <span className="ml-2 text-xs text-primary">você</span>}
                </td>
                <td className="py-2 text-right tabular-nums">{member.seasonal_xp}</td>
                <td className="py-2 text-right tabular-nums text-subtle">
                  {member.active_days}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-muted">{league.note}</p>
    </div>
  )
}
