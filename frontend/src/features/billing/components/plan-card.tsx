import { Check, Minus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { BillingPlan } from '@/lib/api/types'
import { formatPrice } from '../format'

/**
 * Um plano com **todos** os direitos à vista — inclusive os que ele não dá.
 *
 * Esconder o que não está incluído é a forma educada de mentir num pricing.
 * Aqui cada linha diz o que o plano concede, e a diferença entre "sem acesso" e
 * "sem limite" aparece no ícone e no texto.
 */
export function PlanCard({
  plan,
  current,
  onChoose,
  disabled,
}: {
  plan: BillingPlan
  current?: boolean
  onChoose?: (slug: string) => void
  disabled?: boolean
}) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 rounded-lg border border-border p-5',
        current && 'border-primary',
      )}
    >
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold">{plan.name}</h3>
          {current && <Badge variant="primary">plano atual</Badge>}
          {plan.trial_days > 0 && !current && (
            <Badge variant="info">{plan.trial_days} dias de teste</Badge>
          )}
        </div>
        <p className="text-2xl font-semibold tabular-nums">
          {formatPrice(plan.price_cents, plan.months)}
        </p>
        <p className="text-sm text-muted">{plan.description}</p>
      </div>

      <ul className="flex-1 space-y-1.5">
        {plan.entitlements.map((item) => (
          <li key={item.feature} className="flex items-start gap-2 text-sm">
            {item.enabled ? (
              <Check className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            ) : (
              <Minus className="mt-0.5 size-4 shrink-0 text-subtle" aria-hidden />
            )}
            <span className={cn(!item.enabled && 'text-subtle')}>{item.description}</span>
          </li>
        ))}
      </ul>

      {onChoose && !current && (
        <Button onClick={() => onChoose(plan.slug)} disabled={disabled}>
          {plan.price_cents === 0 ? 'Usar o gratuito' : 'Assinar'}
        </Button>
      )}
    </div>
  )
}
