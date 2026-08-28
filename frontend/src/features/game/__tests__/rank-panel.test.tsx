import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { RankPanel } from '../components/rank-badge'
import type { RankInfo } from '@/lib/api/types'

const complete: RankInfo = {
  slug: 'OURO',
  name: 'Ouro',
  color_token: 'rank-ouro',
  score: 0.6587,
  coverage: 1,
  missing_signals: [],
  next_tier: 'PLATINA',
  next_tier_name: 'Platina',
  progress_to_next: 0.786,
  components: [
    {
      key: 'acerto',
      label: 'Taxa de acerto',
      weight: 0.3,
      value: 0.71,
      points: 0.213,
      available: true,
      detail: '71,0% em 200 respostas',
    },
    {
      key: 'retencao',
      label: 'Retenção na revisão',
      weight: 0.25,
      value: 0.82,
      points: 0.205,
      available: true,
      detail: '82,0% de recordação em 100 revisões',
    },
    {
      key: 'cobertura',
      label: 'Cobertura do edital',
      weight: 0.2,
      value: 0.46,
      points: 0.092,
      available: true,
      detail: '46,0% do plano cumprido',
    },
    {
      key: 'simulados',
      label: 'Desempenho em simulados',
      weight: 0.15,
      value: 0.68,
      points: 0.102,
      available: true,
      detail: '68,0% de média em 3 simulado(s)',
    },
    {
      key: 'consistencia',
      label: 'Consistência de estudo',
      weight: 0.1,
      value: 0.4667,
      points: 0.0467,
      available: true,
      detail: '14 dias ativos nos últimos 30',
    },
  ],
}

const empty: RankInfo = {
  slug: 'FERRO',
  name: 'Ferro',
  color_token: 'rank-ferro',
  score: 0,
  coverage: 0,
  missing_signals: ['acerto', 'retencao', 'cobertura', 'simulados', 'consistencia'],
  next_tier: 'BRONZE',
  next_tier_name: 'Bronze',
  progress_to_next: 0,
  components: [
    {
      key: 'acerto',
      label: 'Taxa de acerto',
      weight: 0.3,
      value: null,
      points: 0,
      available: false,
      detail: '0 de 30 respostas para entrar na conta',
    },
    {
      key: 'retencao',
      label: 'Retenção na revisão',
      weight: 0.25,
      value: null,
      points: 0,
      available: false,
      detail: '0 de 20 revisões para entrar na conta',
    },
    {
      key: 'cobertura',
      label: 'Cobertura do edital',
      weight: 0.2,
      value: null,
      points: 0,
      available: false,
      detail: 'sem plano de estudo ativo para medir cobertura',
    },
    {
      key: 'simulados',
      label: 'Desempenho em simulados',
      weight: 0.15,
      value: null,
      points: 0,
      available: false,
      detail: 'nenhum simulado concluído ainda',
    },
    {
      key: 'consistencia',
      label: 'Consistência de estudo',
      weight: 0.1,
      value: null,
      points: 0,
      available: false,
      detail: '0 de 7 dias ativos para entrar na conta',
    },
  ],
}

describe('RankPanel', () => {
  it('as parcelas somam exatamente o score exibido', async () => {
    render(<RankPanel rank={complete} />)
    expect(screen.getByText('score 65,9%')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /por quê/i }))
    expect(screen.getByText(/somam exatamente 65,9%/)).toBeInTheDocument()

    const sum = complete.components.reduce((total, item) => total + item.points, 0)
    expect(Number(sum.toFixed(4))).toBe(complete.score)
  })

  it('deixa explícito que XP não entra na conta do rank', async () => {
    render(<RankPanel rank={complete} />)
    await userEvent.click(screen.getByRole('button', { name: /por quê/i }))
    expect(screen.getByText(/XP não entra nesta conta/)).toBeInTheDocument()
  })

  it('mostra o caminho para o próximo rank', () => {
    render(<RankPanel rank={complete} />)
    expect(screen.getByText(/79% do caminho para Platina/)).toBeInTheDocument()
  })

  it('sinal sem amostra aparece com o motivo, não como desempenho zero', async () => {
    render(<RankPanel rank={empty} />)
    await userEvent.click(screen.getByRole('button', { name: /por quê/i }))

    expect(screen.getByText('0 de 30 respostas para entrar na conta')).toBeInTheDocument()
    expect(
      screen.getByText('sem plano de estudo ativo para medir cobertura'),
    ).toBeInTheDocument()
    expect(screen.getByText(/5 sinal\(is\) ainda sem amostra/)).toBeInTheDocument()
  })
})
