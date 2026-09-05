import { describe, expect, it } from 'vitest'
import type { BattleLayoutSettings, Question } from '@/lib/api/types'
import { MOBILE_MAX_WIDTH, TABLET_MAX_WIDTH, selectBattleLayout, viewportOf } from '../layout'

const settings: BattleLayoutSettings = {
  short_answer_max: 45,
  short_average_max: 30,
  tablet_short_answer_max: 38,
  tablet_short_average_max: 26,
  mobile_short_answer_max: 30,
  mobile_short_average_max: 20,
  max_options_for_arena: 5,
  chars_per_line_desktop: 34,
  chars_per_line_tablet: 28,
  chars_per_line_mobile: 22,
  max_lines_for_arena: 2,
}

function question(contents: string[]): Pick<Question, 'alternatives'> {
  return {
    alternatives: contents.map((content, index) => ({
      public_id: `alt-${index}`,
      letter: 'ABCDE'[index],
      content,
    })),
  }
}

describe('viewportOf', () => {
  it('separa celular, tablet e desktop pelas larguras de corte', () => {
    expect(viewportOf(MOBILE_MAX_WIDTH)).toBe('mobile')
    expect(viewportOf(MOBILE_MAX_WIDTH + 1)).toBe('tablet')
    expect(viewportOf(TABLET_MAX_WIDTH)).toBe('tablet')
    expect(viewportOf(TABLET_MAX_WIDTH + 1)).toBe('desktop')
  })
})

describe('selectBattleLayout', () => {
  it('alternativas curtas vão para a arena', () => {
    const decision = selectBattleLayout(
      question(['Sim', 'Não', 'Depende', 'Nenhuma']),
      'desktop',
      settings,
    )
    expect(decision.layout).toBe('monster-arena')
    expect(decision.reason).toContain('cabem')
  })

  it('alternativa longa força o modo compacto', () => {
    const decision = selectBattleLayout(
      question([
        'Sim',
        'Não',
        'Compete privativamente à União legislar sobre direito processual civil e penal.',
        'Talvez',
      ]),
      'desktop',
      settings,
    )
    expect(decision.layout).toBe('compact-answer')
    expect(decision.reason).toContain('caracteres')
  })

  it('excesso de alternativas tira a arena mesmo com texto curto', () => {
    const decision = selectBattleLayout(
      question(['A', 'B', 'C', 'D', 'E', 'F']),
      'desktop',
      settings,
    )
    expect(decision.layout).toBe('compact-answer')
    expect(decision.reason).toContain('6 alternativas')
  })

  it('o mesmo conjunto pode mudar de layout entre desktop e celular', () => {
    const set = question(['Sim', 'Não', 'Talvez', 'Competência privativa da União.'])
    expect(selectBattleLayout(set, 'desktop', settings).layout).toBe('monster-arena')
    expect(selectBattleLayout(set, 'mobile', settings).layout).toBe('compact-answer')
  })

  it('a régua vem do banco: baixar o limite muda a decisão sem tocar no código', () => {
    const set = question(['Sim', 'Não', 'Depende', 'Nenhuma'])
    expect(selectBattleLayout(set, 'desktop', settings).layout).toBe('monster-arena')
    expect(
      selectBattleLayout(set, 'desktop', { ...settings, short_answer_max: 3 }).layout,
    ).toBe('compact-answer')
  })

  it('sem alternativas não quebra a conta', () => {
    const decision = selectBattleLayout(question([]), 'desktop', settings)
    expect(decision.options).toBe(0)
    expect(decision.estimatedLines).toBe(1)
  })
})
