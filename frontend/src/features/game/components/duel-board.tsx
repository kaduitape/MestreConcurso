import { cn } from '@/lib/utils'
import type { Duel, DuelSide } from '@/lib/api/types'

function Side({ side, highlight }: { side: DuelSide; highlight: boolean }) {
  return (
    <div
      className={cn(
        'flex-1 space-y-1 rounded-lg border border-border p-4',
        highlight && 'border-primary',
      )}
    >
      <p className="text-sm text-muted">{side.display_name}</p>
      <p className="font-mono text-3xl font-semibold tabular-nums">{side.correct}</p>
      <p className="text-xs text-subtle">
        {side.answered} respondidas
        {side.finished ? ' · rodada concluída' : ' · em andamento'}
      </p>
    </div>
  )
}

/**
 * O placar do duelo. Enquanto os dois lados não terminam, não há resultado — e a
 * tela diz isso em vez de mostrar quem está "ganhando" com meia rodada.
 */
export function DuelBoard({ duel }: { duel: Duel }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row">
        <Side side={duel.challenger} highlight={duel.is_challenger} />
        {duel.opponent ? (
          <Side side={duel.opponent} highlight={!duel.is_challenger} />
        ) : (
          <div className="flex-1 space-y-1 rounded-lg border border-dashed border-border p-4">
            <p className="text-sm text-muted">Adversário</p>
            <p className="text-sm">Aguardando alguém aceitar.</p>
            <p className="font-mono text-lg tracking-wider">{duel.code}</p>
            <p className="text-xs text-subtle">
              Compartilhe este código. O convite expira em 48 horas.
            </p>
          </div>
        )}
      </div>

      <div className="space-y-1 rounded-lg border border-border p-4">
        <p className="font-medium">{duel.headline}</p>
        <ul className="space-y-0.5">
          {duel.lines.map((line) => (
            <li key={line} className="text-xs text-muted">
              {line}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
