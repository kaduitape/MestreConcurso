import { Coins, Eraser, Lightbulb, Shield } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { BattlePowerKey, BattlePowerOffer } from '@/lib/api/types'

const ICON: Record<BattlePowerKey, LucideIcon> = {
  SHIELD: Shield,
  ELIMINATE: Eraser,
  HINT: Lightbulb,
}

/**
 * Os três poderes e o saldo da batalha.
 *
 * As moedas são da rodada e morrem com ela: não há loja, não há saldo entre
 * batalhas e não se compra nada com dinheiro. Isso é deliberado — uma moeda que
 * atravessasse batalhas viraria economia, e economia num produto de estudo
 * acaba virando conteúdo atrás de pagamento.
 *
 * O preço aparece antes do clique. Poder que se descobre caro depois de gasto é
 * armadilha, não recurso.
 */
export function PowerBar({
  powers,
  coins,
  disabled,
  pending,
  onUse,
  className,
}: {
  powers: BattlePowerOffer[]
  coins: number
  disabled: boolean
  pending: BattlePowerKey | null
  onUse: (power: BattlePowerKey) => void
  className?: string
}) {
  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <span
        className="flex items-center gap-1.5 rounded-lg bg-game-gold/10 px-2.5 py-1.5 text-sm font-bold text-game-gold"
        aria-label={`${coins} moedas nesta batalha`}
      >
        <Coins className="size-4" aria-hidden />
        <span className="font-mono tabular-nums">{coins}</span>
      </span>

      {powers.map((offer) => {
        const Icon = ICON[offer.power]
        const blocked = disabled || offer.used || !offer.affordable
        return (
          <button
            key={offer.power}
            type="button"
            disabled={blocked || pending !== null}
            onClick={() => onUse(offer.power)}
            title={`${offer.description} Custa ${offer.cost} moedas.`}
            // O nome acessível é escrito à mão: a leitura do conteúdo daria
            // "Escudo25", que não diz nada a quem ouve a tela.
            aria-label={
              offer.used
                ? `${offer.label}: já usado nesta questão.`
                : `${offer.label}: ${offer.description} Custa ${offer.cost} moedas.`
            }
            className={cn(
              'flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors',
              'focus-visible:outline-2 focus-visible:outline-offset-2',
              'focus-visible:outline-game-purple-light',
              offer.used
                ? 'border-success/40 bg-success-soft/10 text-success'
                : blocked
                  ? 'border-white/10 text-subtle'
                  : 'border-white/15 hover:border-game-purple/50 hover:bg-white/[0.05]',
            )}
          >
            <Icon className="size-4" aria-hidden />
            <span className="font-semibold">{offer.label}</span>
            <span className="font-mono text-xs tabular-nums opacity-70">
              {offer.used ? 'usado' : offer.cost}
            </span>
          </button>
        )
      })}
    </div>
  )
}

/** A dica comprada. Sempre texto que já estava cadastrado na questão. */
export function HintPanel({ hint, className }: { hint: string; className?: string }) {
  return (
    <p
      className={cn(
        'flex items-start gap-2 rounded-xl border border-game-gold/25 bg-game-gold/[0.06]',
        'p-3 text-sm',
        className,
      )}
      role="note"
    >
      <Lightbulb className="mt-0.5 size-4 shrink-0 text-game-gold" aria-hidden />
      <span>
        <span className="font-semibold text-game-gold">Dica: </span>
        {hint}
      </span>
    </p>
  )
}
