import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ComboCounter, LivesCounter, RunClock } from '../components/combo-counter'
import type { RunState } from '@/lib/api/types'

const base: RunState = {
  answered: 0,
  correct: 0,
  wrong: 0,
  lives_left: null,
  combo: 0,
  best_combo: 0,
  multiplier: 1,
  elapsed_seconds: 0,
  seconds_left: null,
  questions_left: 25,
  accuracy: null,
  is_over: false,
  over_reason: null,
}

describe('ComboCounter', () => {
  it('sem sequência não anuncia multiplicador', () => {
    render(<ComboCounter state={base} />)
    expect(screen.getByText('sem sequência')).toBeInTheDocument()
  })

  it('mostra a sequência e o multiplicador em curso', () => {
    render(<ComboCounter state={{ ...base, combo: 6, multiplier: 1.5 }} />)
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByText(/sequência · 1.5×/)).toBeInTheDocument()
  })
})

describe('LivesCounter', () => {
  it('descreve as vidas para leitores de tela', () => {
    render(<LivesCounter left={1} total={3} />)
    expect(screen.getByRole('img', { name: '1 de 3 vidas' })).toBeInTheDocument()
  })
})

describe('RunClock', () => {
  it('formata o tempo restante', () => {
    render(<RunClock seconds={125} />)
    expect(screen.getByText('2:05')).toBeInTheDocument()
  })
})
