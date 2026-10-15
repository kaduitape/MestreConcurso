import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { GameButton } from '@/components/game/game-button'
import type { Battle } from '@/lib/api/types'

/**
 * O fim da batalha.
 *
 * O texto fala da batalha e do desempenho medido — nunca de aprovação. Vencer
 * um monstro é vencer um monstro: sugerir que isso diz algo sobre a prova seria
 * inventar uma conclusão que os dados não sustentam.
 */
export function ResultModal({
  battle,
  open,
  onClose,
  onRestart,
  restarting,
}: {
  battle: Battle
  open: boolean
  onClose: () => void
  onRestart: () => void
  restarting: boolean
}) {
  const status = battle.status
  const score = battle.run.score
  const victory = status.victory

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className={victory ? 'text-success' : 'text-danger'}>
            {victory ? 'Monstro derrotado' : 'Você caiu'}
          </DialogTitle>
          <DialogDescription>
            {status.outcome_reason ??
              `${status.correct} acerto(s) em ${status.answered} questão(ões).`}
          </DialogDescription>
        </DialogHeader>

        <dl className="grid grid-cols-3 gap-3 text-center">
          <div>
            <dt className="text-xs text-subtle">Acertos</dt>
            <dd className="font-mono text-lg tabular-nums">
              {status.correct}/{status.answered}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">Sua vida</dt>
            <dd className="font-mono text-lg tabular-nums">
              {status.player_hp}/{status.player_max_hp}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-subtle">XP</dt>
            <dd className="font-mono text-lg tabular-nums">+{battle.run.xp_awarded}</dd>
          </div>
        </dl>

        {score && score.breakdown.length > 0 && (
          <div className="mt-4 rounded-lg border border-border p-3">
            <p className="mb-2 text-xs font-semibold tracking-wide text-subtle uppercase">
              De onde veio o XP
            </p>
            <ul className="space-y-1">
              {score.breakdown.map((line) => (
                <li key={line.label} className="flex justify-between gap-4 text-sm">
                  <span className="text-muted">{line.label}</span>
                  <span className="tabular-nums">{line.value}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <GameButton onClick={onRestart} loading={restarting}>
            Nova batalha
          </GameButton>
          <GameButton variant="ghost" onClick={onClose}>
            Fechar
          </GameButton>
        </div>
      </DialogContent>
    </Dialog>
  )
}
