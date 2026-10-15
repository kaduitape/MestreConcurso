import { Trophy } from 'lucide-react'
import { EmptyState } from '@/components/feedback/empty-state'
import { cn } from '@/lib/utils'
import type { BattleRanking } from '@/lib/api/types'

/**
 * A tabela das batalhas.
 *
 * Herda as duas proteções da liga: compara **dentro do mesmo contexto** e some
 * inteira para quem desligou a comparação. E a ordem é o número de batalhas
 * vencidas **pelo acerto** — equipamento e classe não sobem ninguém aqui.
 *
 * Não há percentual: uma batalha pode terminar antes das questões acabarem, e
 * dividir por um denominador incerto seria fabricar estatística.
 */
export function RankingTable({ ranking }: { ranking: BattleRanking }) {
  if (ranking.empty_reason) {
    return (
      <EmptyState icon={Trophy} title="Sem tabela ainda" description={ranking.empty_reason} />
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-semibold">{ranking.context_label}</p>
        <p className="text-xs text-subtle">{ranking.note}</p>
      </div>

      <ul className="space-y-1.5">
        {ranking.members.map((member) => (
          <li
            key={member.position}
            className={cn(
              'flex flex-wrap items-center gap-3 rounded-lg border p-2.5 text-sm',
              member.is_you
                ? 'border-game-purple/40 bg-game-purple/[0.08]'
                : 'border-white/[0.07]',
            )}
          >
            <span className="w-7 font-mono tabular-nums text-subtle">{member.position}</span>
            <span className="min-w-0 flex-1 truncate font-medium">{member.label}</span>
            <span className="font-mono text-xs tabular-nums text-muted">
              {member.wins} vitória(s) · {member.battles} batalha(s) · {member.correct} acertos
            </span>
          </li>
        ))}
      </ul>

      {ranking.your_position !== null && (
        <p className="text-xs text-subtle">
          Você está em {ranking.your_position}º entre {ranking.participants} candidato(s) com
          batalhas suficientes.
        </p>
      )}
    </div>
  )
}
