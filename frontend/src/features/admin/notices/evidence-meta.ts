import { CheckCircle2, CircleHelp, Sparkles, UserCheck } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import type { EvidenceLevel } from '@/lib/api/types'

interface EvidenceStyle {
  label: string
  description: string
  className: string
  icon: LucideIcon
}

/**
 * Os quatro níveis de prova têm tratamento visual distinto — é o que impede o
 * usuário de confundir o que está no edital com o que a IA deduziu.
 */
export const EVIDENCE: Record<EvidenceLevel, EvidenceStyle> = {
  OFFICIAL: {
    label: 'Oficial',
    description: 'Citação conferida literalmente no PDF do edital.',
    className: 'bg-success-soft text-success',
    icon: CheckCircle2,
  },
  CONFIRMED: {
    label: 'Confirmado',
    description: 'Revisado e confirmado por uma pessoa da equipe.',
    className: 'bg-info-soft text-info',
    icon: UserCheck,
  },
  INFERRED: {
    label: 'Inferido',
    description: 'A IA deduziu, mas a citação não foi localizada no documento.',
    className: 'bg-warning-soft text-warning',
    icon: Sparkles,
  },
  NOT_FOUND: {
    label: 'Não localizado',
    description: 'O campo não foi encontrado no edital.',
    className: 'bg-surface-muted text-muted',
    icon: CircleHelp,
  },
}

export function formatFactValue(value: unknown, fieldPath: string): string {
  if (value === null || value === undefined || value === '') return '—'
  if (fieldPath.endsWith('_cents') && typeof value === 'number') {
    return (value / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
  }
  if (typeof value === 'number') return value.toLocaleString('pt-BR')
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
  }
  return String(value)
}
