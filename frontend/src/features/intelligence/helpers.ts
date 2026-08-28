import type { ErrorCause } from '@/lib/api/types'

export const CAUSE_TONE: Record<ErrorCause, 'danger' | 'warning' | 'info' | 'neutral'> = {
  UNKNOWN_CONTENT: 'danger',
  INTERPRETATION: 'warning',
  CONFUSION: 'warning',
  FORGETTING: 'info',
  RUSH: 'warning',
  TRAP: 'danger',
  ALTERNATIVE_DOUBT: 'neutral',
}

/** Ordem em que as causas aparecem no seletor — da mais comum à mais específica. */
export const CAUSE_ORDER: ErrorCause[] = [
  'UNKNOWN_CONTENT',
  'INTERPRETATION',
  'FORGETTING',
  'RUSH',
  'CONFUSION',
  'ALTERNATIVE_DOUBT',
  'TRAP',
]

/** Faixa do Priority Score. Os cortes são de leitura, não de cálculo. */
export function priorityTone(score: number): 'danger' | 'warning' | 'success' {
  if (score >= 60) return 'danger'
  if (score >= 35) return 'warning'
  return 'success'
}

export function priorityLabel(score: number): string {
  if (score >= 60) return 'Prioridade alta'
  if (score >= 35) return 'Prioridade média'
  return 'Prioridade baixa'
}

/** 0.18 → "18%". Só formata: o número vem calculado do backend. */
export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function trendLabel(trend: number | null): string | null {
  if (trend === null) return null
  const signal = trend > 0 ? '+' : ''
  return `${signal}${(trend * 100).toFixed(1)} p.p. entre a metade antiga e a recente do período`
}
