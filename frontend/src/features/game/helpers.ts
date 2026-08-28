import type { MissionPriority, RankSlug } from '@/lib/api/types'

export const RANK_STYLE: Record<RankSlug, { label: string; from: string; to: string }> = {
  FERRO: { label: 'Ferro', from: '#6b7280', to: '#9ca3af' },
  BRONZE: { label: 'Bronze', from: '#92400e', to: '#d97706' },
  PRATA: { label: 'Prata', from: '#64748b', to: '#cbd5e1' },
  OURO: { label: 'Ouro', from: '#b45309', to: '#fbbf24' },
  PLATINA: { label: 'Platina', from: '#0e7490', to: '#67e8f9' },
  DIAMANTE: { label: 'Diamante', from: '#1d4ed8', to: '#93c5fd' },
  MESTRE: { label: 'Mestre', from: '#6d28d9', to: '#c4b5fd' },
  GRAO_MESTRE: { label: 'Grão-Mestre', from: '#9d174d', to: '#fda4af' },
}

export const PRIORITY_LABEL: Record<MissionPriority, string> = {
  HIGH: 'Alta',
  MEDIUM: 'Média',
  LOW: 'Baixa',
}

export const PRIORITY_TONE: Record<MissionPriority, 'danger' | 'warning' | 'neutral'> = {
  HIGH: 'danger',
  MEDIUM: 'warning',
  LOW: 'neutral',
}

export const EVENT_LABEL: Record<string, string> = {
  STUDY_SESSION: 'Estudo com foco',
  FLASHCARDS_REVIEWED: 'Revisão de flashcards',
  QUESTIONS_ANSWERED: 'Questões resolvidas',
  SIMULATION_FINISHED: 'Simulado concluído',
  ERROR_CLASSIFIED: 'Erro classificado',
  DAILY_MISSIONS_DONE: 'Missões do dia',
  WEEKLY_MISSION_DONE: 'Missão da semana',
  ACHIEVEMENT_UNLOCKED: 'Conquista',
}

/** 0.615 → "61,5%". Só formata: o número vem calculado do backend. */
export function scorePercent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits).replace('.', ',')}%`
}

export function formatEstimate(minutes: number): string {
  if (minutes < 60) return `~${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest === 0 ? `~${hours}h` : `~${hours}h${String(rest).padStart(2, '0')}`
}
