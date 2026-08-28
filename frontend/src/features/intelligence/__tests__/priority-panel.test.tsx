import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { PriorityPanel } from '../priority-panel'
import type { PriorityList } from '@/lib/api/types'

const complete: PriorityList = {
  computed_at: '2026-08-24T12:00:00Z',
  board_slug: 'cespe',
  notes: [],
  items: [
    {
      scope_key: 'sub:direito-penal',
      label: 'Direito Penal',
      color_token: 'subject-direito',
      score: 71,
      coverage: 1,
      missing_signals: [],
      computed_at: '2026-08-24T12:00:00Z',
      contributions: [
        {
          key: 'incidencia_na_banca',
          label: 'Incidência na banca',
          points: 22,
          max_points: 30,
          detail: '18,0% das questões da banca',
        },
        {
          key: 'peso_no_edital',
          label: 'Peso no edital',
          points: 20,
          max_points: 25,
          detail: '20,0% do plano de estudo',
        },
        {
          key: 'seu_desempenho',
          label: 'Seu desempenho',
          points: 14,
          max_points: 25,
          detail: '44,0% de acerto em 40 respostas',
        },
        {
          key: 'tempo_sem_estudar',
          label: 'Tempo sem estudar',
          points: 9,
          max_points: 12,
          detail: '16 dia(s) desde o último estudo',
        },
        {
          key: 'conteudo_pendente',
          label: 'Conteúdo ainda não coberto',
          points: 6,
          max_points: 8,
          detail: '25,0% do tempo planejado já cumprido',
        },
      ],
    },
  ],
}

const partial: PriorityList = {
  computed_at: '2026-08-24T12:00:00Z',
  board_slug: null,
  notes: [],
  items: [
    {
      scope_key: 'sub:informatica',
      label: 'Informática',
      color_token: 'subject-informatica',
      score: 12,
      coverage: 0.4,
      missing_signals: ['incidencia_na_banca', 'seu_desempenho', 'tempo_sem_estudar'],
      computed_at: '2026-08-24T12:00:00Z',
      contributions: [
        {
          key: 'incidencia_na_banca',
          label: 'Incidência na banca',
          points: 0,
          max_points: 30,
          detail: 'sem amostra de questões da banca',
        },
        {
          key: 'peso_no_edital',
          label: 'Peso no edital',
          points: 8,
          max_points: 25,
          detail: '8,0% do plano de estudo',
        },
        {
          key: 'seu_desempenho',
          label: 'Seu desempenho',
          points: 0,
          max_points: 25,
          detail: '2 resposta(s) registrada(s); mínimo de 5 para entrar na conta',
        },
        {
          key: 'tempo_sem_estudar',
          label: 'Tempo sem estudar',
          points: 0,
          max_points: 12,
          detail: 'ainda não estudada neste plano',
        },
        {
          key: 'conteudo_pendente',
          label: 'Conteúdo ainda não coberto',
          points: 4,
          max_points: 8,
          detail: '50,0% do tempo planejado já cumprido',
        },
      ],
    },
  ],
}

const priority = vi.hoisted(() => vi.fn())
vi.mock('@/lib/api/intelligence', () => ({
  intelligenceApi: {
    priority: () => priority(),
    recomputePriority: vi.fn(),
  },
}))

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <PriorityPanel />
    </QueryClientProvider>,
  )
}

describe('PriorityPanel', () => {
  beforeEach(() => priority.mockReset())

  it('as parcelas exibidas somam o score mostrado', async () => {
    priority.mockResolvedValue(complete)
    renderPanel()

    const row = await screen.findByRole('button', { name: /Direito Penal/ })
    expect(await screen.findByText('71')).toBeInTheDocument()

    await userEvent.click(row)
    expect(await screen.findByText(/somam exatamente 71 pontos/)).toBeInTheDocument()

    const sum = complete.items[0].contributions.reduce((total, item) => total + item.points, 0)
    expect(sum).toBe(complete.items[0].score)
  })

  it('mostra o motivo de cada parcela, inclusive quando ela vale zero', async () => {
    priority.mockResolvedValue(partial)
    renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: /Informática/ }))

    expect(screen.getByText('sem amostra de questões da banca')).toBeInTheDocument()
    expect(
      screen.getByText('2 resposta(s) registrada(s); mínimo de 5 para entrar na conta'),
    ).toBeInTheDocument()
    expect(screen.getByText(/3 sinal\(is\) ainda não existe/)).toBeInTheDocument()
  })

  it('sem score calculado, convida a calcular em vez de mostrar zero', async () => {
    priority.mockResolvedValue({
      items: [],
      computed_at: null,
      board_slug: null,
      notes: ['Sem plano de estudo ativo não há disciplinas para priorizar.'],
    })
    renderPanel()

    expect(await screen.findByText(/ainda não calculado/i)).toBeInTheDocument()
    expect(screen.getByText(/Sem plano de estudo ativo/)).toBeInTheDocument()
  })
})
