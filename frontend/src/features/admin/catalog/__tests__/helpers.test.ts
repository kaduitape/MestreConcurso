import { describe, expect, it, vi } from 'vitest'
import { STATUS_LABEL, daysUntil, formatCurrency, formatDate } from '../helpers'

describe('formatCurrency', () => {
  it('converte centavos em reais', () => {
    expect(formatCurrency(815700)).toContain('8.157,00')
  })

  it('mostra traço quando o valor não foi informado', () => {
    // Ausência de dado nunca vira zero ou estimativa.
    expect(formatCurrency(null)).toBe('—')
  })
})

describe('formatDate', () => {
  it('formata no padrão brasileiro', () => {
    expect(formatDate('2026-03-15')).toBe('15/03/2026')
  })

  it('mostra traço sem data', () => {
    expect(formatDate(null)).toBe('—')
  })
})

describe('daysUntil', () => {
  it('conta os dias restantes até a prova', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-01T10:00:00'))
    expect(daysUntil('2026-03-15')).toBe(14)
    vi.useRealTimers()
  })

  it('devolve valor negativo para datas passadas', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-03-20T10:00:00'))
    expect(daysUntil('2026-03-15')).toBe(-5)
    vi.useRealTimers()
  })

  it('devolve nulo sem data', () => {
    expect(daysUntil(null)).toBeNull()
  })
})

describe('STATUS_LABEL', () => {
  it('cobre todos os estados de concurso', () => {
    expect(Object.keys(STATUS_LABEL)).toEqual([
      'ANNOUNCED',
      'OPEN',
      'IN_PROGRESS',
      'CONCLUDED',
      'CANCELED',
    ])
  })
})
