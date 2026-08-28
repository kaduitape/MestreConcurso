import { describe, expect, it } from 'vitest'
import { SIMULATION_KINDS, formatDelta, formatPercent } from '../helpers'

describe('formatPercent', () => {
  it('formata a fração como percentual', () => {
    expect(formatPercent(0.6, 0)).toBe('60%')
    expect(formatPercent(0.8125)).toBe('81.3%')
  })

  it('devolve travessão quando não há dado', () => {
    expect(formatPercent(null)).toBe('—')
    expect(formatPercent(undefined)).toBe('—')
  })
})

describe('formatDelta', () => {
  it('mostra o sinal da variação em pontos percentuais', () => {
    expect(formatDelta(0.4)).toBe('+40.0 p.p.')
    expect(formatDelta(-0.125)).toBe('-12.5 p.p.')
  })

  it('não inventa comparação quando não há execução anterior', () => {
    expect(formatDelta(null)).toBeNull()
  })
})

describe('SIMULATION_KINDS', () => {
  it('avisa o que cada tipo dependente exige', () => {
    expect(SIMULATION_KINDS.ERRORS.requires).toMatch(/erradas/)
    expect(SIMULATION_KINDS.OFFICIAL.requires).toMatch(/plano/)
    expect(SIMULATION_KINDS.CUSTOM.requires).toBeUndefined()
  })
})
