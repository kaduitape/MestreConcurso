import type { QuestionDifficulty, SimulationKind } from '@/lib/api/types'

export const DIFFICULTY_LABEL: Record<QuestionDifficulty, string> = {
  EASY: 'Fácil',
  MEDIUM: 'Média',
  HARD: 'Difícil',
}

export const DIFFICULTY_TONE: Record<QuestionDifficulty, 'success' | 'warning' | 'danger'> = {
  EASY: 'success',
  MEDIUM: 'warning',
  HARD: 'danger',
}

export const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Rascunho',
  PUBLISHED: 'Publicada',
  ARCHIVED: 'Arquivada',
  NEEDS_REVIEW: 'Aguardando revisão',
}

export interface SimulationKindInfo {
  label: string
  description: string
  /** Tipos que dependem de dados do próprio candidato para existir. */
  requires?: string
}

export const SIMULATION_KINDS: Record<SimulationKind, SimulationKindInfo> = {
  OFFICIAL: {
    label: 'Oficial',
    description: 'Distribuição por disciplina igual à da sua prova.',
    requires: 'Exige um plano de estudo ativo com cargo escolhido.',
  },
  BOARD: {
    label: 'Da banca',
    description: 'Somente questões da banca selecionada.',
    requires: 'Exige questões cadastradas para a banca.',
  },
  ERRORS: {
    label: 'Dos erros',
    description: 'Só o que você errou e ainda não recuperou.',
    requires: 'Exige questões erradas registradas.',
  },
  FINAL_STRETCH: {
    label: 'Reta final',
    description: 'Foco no que mais cai, para os últimos dias.',
  },
  FLASH: {
    label: 'Relâmpago',
    description: 'Até 10 questões para uma revisão rápida.',
  },
  CUSTOM: {
    label: 'Personalizado',
    description: 'Você escolhe disciplina e quantidade.',
  },
  ADAPTIVE: {
    label: 'Adaptativo',
    description: 'A dificuldade acompanha o seu desempenho.',
  },
}

/** 0.6 → "60%". Só formata: o número vem calculado do backend. */
export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function formatDelta(value: number | null | undefined): string | null {
  if (value === null || value === undefined) return null
  const signal = value > 0 ? '+' : ''
  return `${signal}${(value * 100).toFixed(1)} p.p.`
}
