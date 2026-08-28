import { describe, expect, it } from 'vitest'
import { CAUSE_ORDER, percent, priorityLabel, priorityTone, trendLabel } from '../helpers'

describe('percent', () => {
  it('formata a fração como percentual', () => {
    expect(percent(0.18, 1)).toBe('18.0%')
    expect(percent(0.75, 0)).toBe('75%')
  })

  it('não inventa número quando o dado não existe', () => {
    expect(percent(null)).toBe('—')
    expect(percent(undefined)).toBe('—')
  })
})

describe('trendLabel', () => {
  it('descreve a variação com o sinal', () => {
    expect(trendLabel(0.12)).toMatch(/^\+12\.0 p\.p\./)
    expect(trendLabel(-0.05)).toMatch(/^-5\.0 p\.p\./)
  })

  it('sem histórico suficiente, não afirma tendência', () => {
    expect(trendLabel(null)).toBeNull()
  })
})

describe('priorityTone', () => {
  it('classifica a faixa do score', () => {
    expect(priorityTone(75)).toBe('danger')
    expect(priorityTone(40)).toBe('warning')
    expect(priorityTone(10)).toBe('success')
    expect(priorityLabel(75)).toBe('Prioridade alta')
  })
})

describe('CAUSE_ORDER', () => {
  it('cobre a taxonomia sem repetição', () => {
    expect(new Set(CAUSE_ORDER).size).toBe(CAUSE_ORDER.length)
    expect(CAUSE_ORDER).toContain('TRAP')
    expect(CAUSE_ORDER).toHaveLength(7)
  })
})
