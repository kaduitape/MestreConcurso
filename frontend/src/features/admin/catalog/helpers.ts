import type { CompetitionStatus } from '@/lib/api/types'

export const STATUS_LABEL: Record<CompetitionStatus, string> = {
  ANNOUNCED: 'Previsto',
  OPEN: 'Inscrições abertas',
  IN_PROGRESS: 'Em andamento',
  CONCLUDED: 'Concluído',
  CANCELED: 'Cancelado',
}

export const EDUCATION_LABEL: Record<string, string> = {
  FUNDAMENTAL: 'Fundamental',
  MEDIO: 'Médio',
  TECNICO: 'Técnico',
  SUPERIOR: 'Superior',
}

export function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(`${value}T00:00:00`).toLocaleDateString('pt-BR')
}

/** Valores monetários chegam em centavos; ausência é exibida como traço. */
export function formatCurrency(cents: number | null): string {
  if (cents === null || cents === undefined) return '—'
  return (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
}

export function daysUntil(value: string | null): number | null {
  if (!value) return null
  const target = new Date(`${value}T00:00:00`).getTime()
  const today = new Date().setHours(0, 0, 0, 0)
  return Math.round((target - today) / 86_400_000)
}
