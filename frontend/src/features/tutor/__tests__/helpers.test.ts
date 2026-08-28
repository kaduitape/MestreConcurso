import { describe, expect, it } from 'vitest'
import { CLAIM_LABEL, groundingLabel, groundingTone } from '../helpers'

describe('groundingLabel', () => {
  it('descreve a cobertura da resposta', () => {
    expect(groundingLabel(1)).toBe('todas as afirmações com origem conferida')
    expect(groundingLabel(0)).toBe('nenhuma afirmação com origem conferida')
    expect(groundingLabel(0.5)).toBe('50% das afirmações com origem conferida')
  })

  it('resposta sem afirmação factual não é tratada como falha', () => {
    expect(groundingLabel(null)).toBe('sem afirmações factuais')
    expect(groundingTone(null)).toBe('success')
  })
})

describe('groundingTone', () => {
  it('piora conforme a resposta perde origem', () => {
    expect(groundingTone(1)).toBe('success')
    expect(groundingTone(0.6)).toBe('warning')
    expect(groundingTone(0.2)).toBe('danger')
  })
})

describe('CLAIM_LABEL', () => {
  it('distingue origem conferida de cálculo e de ausência', () => {
    expect(CLAIM_LABEL.CITED).toMatch(/conferida/)
    expect(CLAIM_LABEL.COMPUTED).toMatch(/plataforma/)
    expect(CLAIM_LABEL.UNSOURCED).toMatch(/[Ss]em origem/)
  })
})
