import type { ClaimStatus } from '@/lib/api/types'

export const CLAIM_TONE: Record<ClaimStatus, 'success' | 'info' | 'warning'> = {
  CITED: 'success',
  COMPUTED: 'info',
  UNSOURCED: 'warning',
}

export const CLAIM_LABEL: Record<ClaimStatus, string> = {
  CITED: 'Origem conferida',
  COMPUTED: 'Calculado pela plataforma',
  UNSOURCED: 'Sem origem conferida',
}

/** Etapas do pipeline, na ordem em que chegam pelo SSE. */
export const STAGE_ORDER = ['prepare', 'retrieve', 'compute', 'generate', 'verify', 'done']

export function groundingLabel(ratio: number | null): string {
  if (ratio === null) return 'sem afirmações factuais'
  if (ratio === 1) return 'todas as afirmações com origem conferida'
  if (ratio === 0) return 'nenhuma afirmação com origem conferida'
  return `${(ratio * 100).toFixed(0)}% das afirmações com origem conferida`
}

export function groundingTone(ratio: number | null): 'success' | 'warning' | 'danger' {
  if (ratio === null || ratio === 1) return 'success'
  if (ratio >= 0.5) return 'warning'
  return 'danger'
}
