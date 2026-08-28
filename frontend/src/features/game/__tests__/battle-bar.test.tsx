import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BattleBar, BattleEvolution, SubjectScoreRow } from '../components/battle-bar'
import type { SubjectScore } from '@/lib/api/types'

const decidido: SubjectScore = {
  subject_id: 1,
  subject_name: 'Direito Penal',
  answers: 214,
  correct: 175,
  you: 82,
  board: 18,
  is_sufficient: true,
  insufficient_reason: null,
}

const insuficiente: SubjectScore = {
  subject_id: 2,
  subject_name: 'Informática',
  answers: 12,
  correct: 11,
  you: 0,
  board: 0,
  is_sufficient: false,
  insufficient_reason: '12 de 30 respostas para o placar desta disciplina existir.',
}

describe('BattleBar', () => {
  it('descreve o placar para leitores de tela', () => {
    render(<BattleBar you={73} board={27} boardName="Cebraspe" />)
    expect(
      screen.getByRole('img', { name: /Você 73 pontos, Cebraspe 27 pontos/ }),
    ).toBeInTheDocument()
  })
})

describe('SubjectScoreRow', () => {
  it('mostra o placar da disciplina com amostra', () => {
    render(
      <ul>
        <SubjectScoreRow subject={decidido} boardName="Cebraspe" />
      </ul>,
    )
    expect(screen.getByText('82 × 18')).toBeInTheDocument()
    expect(screen.getByText('214 respostas')).toBeInTheDocument()
  })

  it('disciplina sem amostra não recebe placar, e o motivo aparece', () => {
    render(
      <ul>
        <SubjectScoreRow subject={insuficiente} boardName="Cebraspe" />
      </ul>,
    )
    expect(screen.getByText('amostra insuficiente')).toBeInTheDocument()
    expect(screen.getByText(insuficiente.insufficient_reason!)).toBeInTheDocument()
    // Nenhum placar é desenhado para ela.
    expect(screen.queryByText('0 × 0')).not.toBeInTheDocument()
  })
})

describe('BattleEvolution', () => {
  it('uma semana só não vira tendência', () => {
    render(
      <BattleEvolution weeks={[{ week_start: '2026-03-16', answers: 10, accuracy: 0.6 }]} />,
    )
    expect(screen.getByText(/a partir da segunda semana/i)).toBeInTheDocument()
  })

  it('desenha a linha e descreve os pontos', () => {
    render(
      <BattleEvolution
        weeks={[
          { week_start: '2026-03-02', answers: 10, accuracy: 0.5 },
          { week_start: '2026-03-09', answers: 12, accuracy: 0.6 },
          { week_start: '2026-03-16', answers: 14, accuracy: 0.7 },
        ]}
      />,
    )
    expect(screen.getByRole('img', { name: /50%, 60%, 70%/ })).toBeInTheDocument()
    expect(screen.getByText(/70% agora/)).toBeInTheDocument()
  })
})
