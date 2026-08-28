import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { JourneyMap } from '../components/journey-map'
import type { Journey } from '@/lib/api/types'

const journey: Journey = {
  milestones: [
    {
      key: 'first_study',
      label: 'Primeiro estudo',
      description: 'Uma sessão de estudo com foco registrada.',
      state: 'DONE',
      current: 4,
      target: 1,
      ratio: 1,
      detail: '4 sessão',
    },
    {
      key: 'hundred_questions',
      label: '100 questões',
      description: 'Volume mínimo para o seu desempenho começar a significar algo.',
      state: 'CURRENT',
      current: 46,
      target: 100,
      ratio: 0.46,
      detail: '46 de 100 questões',
    },
    {
      key: 'coverage_25',
      label: '25% do edital',
      description: 'Um quarto do tempo planejado já cumprido.',
      state: 'PENDING',
      current: 8,
      target: 25,
      ratio: 0.32,
      detail: '8 de 25 % de cobertura',
    },
  ],
  current_key: 'hundred_questions',
  completed: 1,
  total: 3,
  days_until_exam: 87,
  disclaimer:
    'Os marcos medem cobertura e desempenho no seu material. Não são previsão de aprovação, e nenhum número aqui diz se você vai passar.',
  empty_reason: null,
}

describe('JourneyMap', () => {
  it('escreve o aviso na tela — ele não é opcional', () => {
    render(<JourneyMap journey={journey} />)
    expect(screen.getByText(/não são previsão de aprovação/i)).toBeInTheDocument()
  })

  it('destaca a etapa atual com o número real que falta', () => {
    render(<JourneyMap journey={journey} />)
    expect(screen.getByText('Etapa atual — 100 questões')).toBeInTheDocument()
    expect(screen.getByText('46% · 46 de 100 questões')).toBeInTheDocument()
  })

  it('nenhum texto promete aprovação', () => {
    const { container } = render(<JourneyMap journey={journey} />)
    const texto = container.textContent!.toLowerCase()
    for (const proibido of ['você será aprovado', 'aprovação garantida', 'chance de passar']) {
      expect(texto).not.toContain(proibido)
    }
  })
})
