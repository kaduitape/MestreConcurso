import type { CardOrigin, CardRating, CardState } from '@/lib/api/types'

export const ORIGIN_LABEL: Record<CardOrigin, string> = {
  USER: 'Escrito por você',
  AI: 'Gerado por IA',
  QUESTION: 'De uma questão',
  ERROR: 'De um erro seu',
  NOTICE: 'Do edital',
  EDITORIAL: 'Curadoria da equipe',
}

export const ORIGIN_TONE: Record<CardOrigin, 'neutral' | 'info' | 'warning' | 'success'> = {
  USER: 'neutral',
  AI: 'info',
  QUESTION: 'info',
  ERROR: 'warning',
  NOTICE: 'success',
  EDITORIAL: 'success',
}

export const RATING_LABEL: Record<CardRating, string> = {
  AGAIN: 'Não lembrei',
  HARD: 'Difícil',
  GOOD: 'Lembrei',
  EASY: 'Fácil',
}

export const RATING_TONE: Record<CardRating, 'danger' | 'warning' | 'primary' | 'success'> = {
  AGAIN: 'danger',
  HARD: 'warning',
  GOOD: 'primary',
  EASY: 'success',
}

export const STATE_LABEL: Record<CardState, string> = {
  NEW: 'Novo',
  LEARNING: 'Aprendendo',
  REVIEW: 'Em revisão',
  RELEARNING: 'Reaprendendo',
}

/** 1 → "amanhã"; 14 → "em 14 dias"; 0 → "ainda hoje". */
export function intervalLabel(days: number): string {
  if (days <= 0) return 'ainda hoje'
  if (days === 1) return 'amanhã'
  if (days < 30) return `em ${days} dias`
  const months = Math.round(days / 30)
  return months === 1 ? 'em cerca de 1 mês' : `em cerca de ${months} meses`
}

/**
 * Traduz o `breakdown` da revisão em frases legíveis.
 * Cada linha corresponde a um número real — nada é inventado aqui.
 */
export function explainInterval(breakdown: Record<string, unknown>): string[] {
  const lines: string[] = []
  const motivo = String(breakdown.motivo ?? '')

  if (motivo === 'erro') {
    lines.push(
      `Você não lembrou, então o intervalo caiu de ${breakdown.intervalo_anterior} para ` +
        `${breakdown.intervalo_final} dia(s) — sem apagar o progresso anterior.`,
    )
  } else if (motivo === 'passo de aprendizado') {
    lines.push(`Cartão ainda em aprendizado: passo ${breakdown.passo}.`)
  } else if (motivo === 'saiu do aprendizado') {
    lines.push('O cartão saiu do aprendizado e entrou em revisão.')
  } else if (motivo === 'revisão') {
    lines.push(
      `${breakdown.intervalo_anterior} dia(s) × fator ${breakdown.fator_aplicado} = ` +
        `${breakdown.intervalo_calculado} dia(s).`,
    )
  }

  const speed = Number(breakdown.ajuste_de_velocidade ?? 1)
  if (Number.isFinite(speed) && speed !== 1) {
    const percent = ((speed - 1) * 100).toFixed(0)
    lines.push(
      speed > 1
        ? `Você respondeu rápido (${breakdown.tempo_de_resposta_s}s): +${percent}% no intervalo.`
        : `Você demorou (${breakdown.tempo_de_resposta_s}s): ${percent}% no intervalo.`,
    )
  }

  if (breakdown.teto_aplicado !== undefined) {
    lines.push(`Teto de ${breakdown.teto_aplicado} dias aplicado.`)
  }

  const before = Number(breakdown.facilidade_anterior)
  const after = Number(breakdown.facilidade_nova)
  if (Number.isFinite(before) && Number.isFinite(after) && before !== after) {
    lines.push(`Facilidade do cartão: ${before} → ${after}.`)
  }

  return lines
}
