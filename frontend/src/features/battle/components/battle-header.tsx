import { LogOut, Swords } from 'lucide-react'
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
  className,
}: {
  battle: Battle
  onLeave: () => void
  leaving: boolean
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-3', className)}>
      <div className="min-w-0">
        <p className="flex items-center gap-2 text-xs tracking-wide text-subtle uppercase">
          <Swords className="size-3.5" aria-hidden />
          Batalha RPG
        </p>
        <h1 className="truncate text-lg font-bold">
          Guerreiro <span className="text-subtle">vs</span> {battle.enemy_name}
        </h1>
        {battle.run.subject_label && (
          <p className="truncate text-sm text-muted">{battle.run.subject_label}</p>
        )}
      </div>

      <Button variant="ghost" size="sm" onClick={onLeave} disabled={leaving}>
        <LogOut className="size-4" aria-hidden />
        Sair da batalha
      </Button>
    </div>
  )
}
