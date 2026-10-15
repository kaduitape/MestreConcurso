import { Crown, LogOut, Swords, Volume2, VolumeX } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { Battle } from '@/lib/api/types'

/**
 * O cabeçalho da batalha: quem está lutando contra quem, e a saída.
 *
 * A saída fica sempre visível. Uma batalha da qual não se sai vira armadilha —
 * e o candidato precisa poder voltar a estudar sem fechar o navegador.
 */
export function BattleHeader({
  battle,
  onLeave,
  leaving,
  soundOn,
  onToggleSound,
  className,
}: {
  battle: Battle
  onLeave: () => void
  leaving: boolean
  soundOn: boolean
  onToggleSound: () => void
  className?: string
}) {
  const status = battle.status
  const answered = Math.min(status.answered + 1, status.questions)
  const progress = status.questions > 0 ? (status.answered / status.questions) * 100 : 0

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {battle.run.subject_label && (
            <span className="battle-plate max-w-full truncate">{battle.run.subject_label}</span>
          )}
          {/* O andamento vira placa, como nas mesas de RPG: número e barra na
              mesma peça, sem competir com o enunciado logo abaixo. */}
          <span className="battle-plate gap-3">
            <span className="tabular-nums">
              Questão {answered}/{status.questions}
            </span>
            <span
              className="h-1.5 w-16 overflow-hidden rounded-full bg-black/50"
              role="progressbar"
              aria-label="Andamento da batalha"
              aria-valuenow={status.answered}
              aria-valuemin={0}
              aria-valuemax={status.questions}
            >
              <span
                className="block h-full rounded-full bg-gradient-to-r from-game-blue to-game-cyan"
                style={{ width: `${progress}%` }}
              />
            </span>
          </span>
          {battle.is_boss && (
            <span className="battle-plate border-game-gold/60 text-game-gold">
              <Crown className="size-3.5" aria-hidden />
              Chefe
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* O som começa desligado: a plataforma é usada no trabalho e na
              biblioteca, e efeito que surpreende faz fechar a aba. */}
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggleSound}
            aria-pressed={soundOn}
            aria-label={soundOn ? 'Desligar os sons da batalha' : 'Ligar os sons da batalha'}
          >
            {soundOn ? (
              <Volume2 className="size-4" aria-hidden />
            ) : (
              <VolumeX className="size-4" aria-hidden />
            )}
          </Button>

          <Button variant="ghost" size="sm" onClick={onLeave} disabled={leaving}>
            <LogOut className="size-4" aria-hidden />
            Sair da batalha
          </Button>
        </div>
      </div>

      <h1 className="flex items-center gap-2 truncate text-lg font-bold">
        <Swords className="size-4 shrink-0 text-game-gold" aria-hidden />
        Guerreiro <span className="text-subtle">vs</span> {battle.enemy_name}
      </h1>
    </div>
  )
}
