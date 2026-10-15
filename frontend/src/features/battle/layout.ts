import type {
  BattleLayout,
  BattleLayoutSettings,
  BattleViewport,
  Question,
} from '@/lib/api/types'

/**
 * Escolha do layout de batalha — a mesma régua do servidor, refeita no cliente.
 *
 * O servidor sugere um layout, mas só o navegador sabe a largura real da tela.
 * Por isso a conta é refeita aqui com os limiares que vieram do banco: a régua é
 * uma só, e continua ajustável sem deploy.
 *
 * A decisão olha **as alternativas**, não a pergunta. O enunciado tem painel
 * próprio e rola quando precisa; quem decide se a arena cabe é o texto que vai
 * embaixo de cada monstro.
 */

/** Larguras de corte. Abaixo de 640px não há espaço horizontal para a arena. */
export const MOBILE_MAX_WIDTH = 640
export const TABLET_MAX_WIDTH = 1024

export function viewportOf(width: number): BattleViewport {
  if (width <= MOBILE_MAX_WIDTH) return 'mobile'
  if (width <= TABLET_MAX_WIDTH) return 'tablet'
  return 'desktop'
}

export interface LayoutDecision {
  layout: BattleLayout
  /** Por que este layout. A decisão não é opaca nem para quem depura. */
  reason: string
  maxLength: number
  averageLength: number
  estimatedLines: number
  options: number
  viewport: BattleViewport
}

function answerMaxFor(settings: BattleLayoutSettings, viewport: BattleViewport): number {
  if (viewport === 'mobile') return settings.mobile_short_answer_max
  if (viewport === 'tablet') return settings.tablet_short_answer_max
  return settings.short_answer_max
}

function averageMaxFor(settings: BattleLayoutSettings, viewport: BattleViewport): number {
  if (viewport === 'mobile') return settings.mobile_short_average_max
  if (viewport === 'tablet') return settings.tablet_short_average_max
  return settings.short_average_max
}

function charsPerLineFor(settings: BattleLayoutSettings, viewport: BattleViewport): number {
  if (viewport === 'mobile') return settings.chars_per_line_mobile
  if (viewport === 'tablet') return settings.chars_per_line_tablet
  return settings.chars_per_line_desktop
}

export function selectBattleLayout(
  question: Pick<Question, 'alternatives'>,
  viewport: BattleViewport,
  settings: BattleLayoutSettings,
): LayoutDecision {
  const texts = question.alternatives.map((item) => item.content.trim())
  const lengths = texts.length > 0 ? texts.map((item) => item.length) : [0]

  const maxLength = Math.max(...lengths)
  const averageLength =
    Math.round((lengths.reduce((total, item) => total + item, 0) / lengths.length) * 100) / 100
  const estimatedLines = Math.max(1, Math.ceil(maxLength / charsPerLineFor(settings, viewport)))

  const base = { maxLength, averageLength, estimatedLines, options: texts.length, viewport }
  const compact = (reason: string): LayoutDecision => ({
    ...base,
    layout: 'compact-answer',
    reason,
  })

  if (texts.length > settings.max_options_for_arena) {
    return compact(`${texts.length} alternativas não cabem na arena.`)
  }
  if (maxLength > answerMaxFor(settings, viewport)) {
    return compact(
      `A maior alternativa tem ${maxLength} caracteres, acima de ${answerMaxFor(settings, viewport)} para ${viewport}.`,
    )
  }
  if (averageLength > averageMaxFor(settings, viewport)) {
    return compact(
      `A média de ${Math.round(averageLength)} caracteres passa de ${averageMaxFor(settings, viewport)} para ${viewport}.`,
    )
  }
  if (estimatedLines > settings.max_lines_for_arena) {
    return compact(
      `O texto ocuparia ${estimatedLines} linhas embaixo do monstro, acima de ${settings.max_lines_for_arena}.`,
    )
  }

  return {
    ...base,
    layout: 'monster-arena',
    reason: `Alternativas curtas (maior com ${maxLength} caracteres): cabem embaixo dos monstros.`,
  }
}
