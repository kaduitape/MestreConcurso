import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { StudyTerritory } from '../components/study-territory'
import type { Territory } from '@/lib/api/types'

const parcial: Territory = {
  subject_key: 'portugues',
  subject_name: 'Português',
  color_token: 'subject-portugues',
  subject_id: 3,
  state: 'STUDYING',
  mastery: 0.62,
  parts: [
    {
      key: 'cobertura',
      label: 'Tempo planejado cumprido',
      weight: 0.4,
      value: 0.62,
      points: 0.248,
      available: true,
      detail: '62% dos 600 minutos planejados',
    },
    {
      key: 'desempenho',
      label: 'Acerto na disciplina',
      weight: 0.4,
      value: null,
      points: 0,
      available: false,
      detail: '8 de 20 respostas para entrar na conta',
    },
    {
      key: 'retencao',
      label: 'Retenção na revisão',
      weight: 0.2,
      value: null,
      points: 0,
      available: false,
      detail: '0 de 10 revisões para entrar na conta',
    },
  ],
  missing_signals: ['desempenho', 'retencao'],
  studied_minutes: 372,
  planned_minutes: 600,
  days_since_studied: 2,
  note: 'Em andamento.',
}

const esfriando: Territory = {
  ...parcial,
  subject_key: 'constitucional',
  subject_name: 'Direito Constitucional',
  state: 'NEEDS_REVIEW',
  mastery: 0.81,
  days_since_studied: 26,
  note: 'Dominada, mas sem revisão há 26 dias. Domínio alto esfria em silêncio.',
}

describe('StudyTerritory', () => {
  it('mostra o estado e o domínio calculado', () => {
    render(<StudyTerritory territory={parcial} />)
    expect(screen.getByText('Em andamento')).toBeInTheDocument()
    expect(screen.getByText('domínio 62%')).toBeInTheDocument()
  })

  it('declara os sinais sem amostra em vez de escondê-los', async () => {
    render(<StudyTerritory territory={parcial} />)
    await userEvent.click(screen.getByRole('button', { name: /por quê/i }))

    expect(screen.getByText(/Apenas 1 de 3 sinais têm amostra/)).toBeInTheDocument()
    expect(screen.getByText('8 de 20 respostas para entrar na conta')).toBeInTheDocument()
    expect(screen.getByText('0 de 10 revisões para entrar na conta')).toBeInTheDocument()
  })

  it('disciplina dominada que esfriou aparece pedindo revisão', () => {
    render(<StudyTerritory territory={esfriando} />)
    expect(screen.getByText('Pede revisão')).toBeInTheDocument()
    expect(screen.getByText(/sem revisão há 26 dias/)).toBeInTheDocument()
  })
})
