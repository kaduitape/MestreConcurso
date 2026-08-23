import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
  {
    variants: {
      variant: {
        neutral: 'bg-surface-muted text-muted',
        primary: 'bg-primary-soft text-primary',
        success: 'bg-success-soft text-success',
        warning: 'bg-warning-soft text-warning',
        danger: 'bg-danger-soft text-danger',
        info: 'bg-info-soft text-info',
        outline: 'border border-border-strong text-muted',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

/**
 * Procedência do dado exibido. A plataforma nunca mistura o que veio do edital
 * com o que foi estimado — o selo torna a diferença visível.
 */
export type Provenance = 'OFICIAL' | 'HISTORICO' | 'IA' | 'ESTIMATIVA'

const provenanceMap: Record<Provenance, { label: string; className: string }> = {
  OFICIAL: { label: 'Oficial', className: 'bg-success-soft text-success' },
  HISTORICO: { label: 'Histórico', className: 'bg-info-soft text-info' },
  IA: { label: 'Gerado por IA', className: 'bg-secondary-soft text-secondary' },
  ESTIMATIVA: { label: 'Estimativa', className: 'bg-warning-soft text-warning' },
}

export function ProvenanceBadge({ kind }: { kind: Provenance }) {
  const item = provenanceMap[kind]
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase',
        item.className,
      )}
    >
      {item.label}
    </span>
  )
}
