import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EvidenceBadge } from '../evidence'
import { EVIDENCE, formatFactValue } from '../evidence-meta'

describe('EvidenceBadge', () => {
  it('distingue visualmente os quatro níveis de prova', () => {
    const levels = ['OFFICIAL', 'CONFIRMED', 'INFERRED', 'NOT_FOUND'] as const
    const classNames = new Set(levels.map((level) => EVIDENCE[level].className))
    // Cada nível tem tratamento próprio: oficial nunca se confunde com inferido.
    expect(classNames.size).toBe(4)
  })

  it('mostra o rótulo do nível', () => {
    render(<EvidenceBadge level="INFERRED" />)
    expect(screen.getByText('Inferido')).toBeInTheDocument()
  })

  it('explica o significado no title', () => {
    render(<EvidenceBadge level="OFFICIAL" />)
    expect(screen.getByTitle(/Citação conferida literalmente/)).toBeInTheDocument()
  })
})

describe('formatFactValue', () => {
  it('converte centavos em reais', () => {
    expect(formatFactValue(815700, 'position.salary_cents')).toContain('8.157,00')
  })

  it('formata datas ISO no padrão brasileiro', () => {
    expect(formatFactValue('2026-03-15', 'exam.date')).toBe('15/03/2026')
  })

  it('mostra traço para campo ausente', () => {
    expect(formatFactValue(null, 'exam.date')).toBe('—')
    expect(formatFactValue('', 'exam.date')).toBe('—')
  })

  it('agrupa milhares em números', () => {
    expect(formatFactValue(1200, 'position.vacancies')).toBe('1.200')
  })
})
