/**
 * A tela da geração em massa tem uma obrigação acima das outras: **a estimativa
 * não pode parecer mais certa do que é**. Confirmar um plano de centenas de
 * tópicos acreditando num chute é como a fatura surpreende.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GenerationItem, GenerationPlan } from '@/lib/api/types'

const { generationApi } = vi.hoisted(() => ({
  generationApi: {
    plans: vi.fn(),
    plan: vi.fn(),
    create: vi.fn(),
    confirm: vi.fn(),
    cancel: vi.fn(),
  },
}))
const { adminCatalogApi } = vi.hoisted(() => ({ adminCatalogApi: { competitions: vi.fn() } }))
vi.mock('@/lib/api/generation', () => ({ generationApi }))
vi.mock('@/lib/api/catalog', () => ({ adminCatalogApi }))

const { GenerationSection } = await import('../generation-section')

function item(overrides: Partial<GenerationItem> = {}): GenerationItem {
  return {
    topic_name: 'Crase',
    subject_name: 'Português',
    kind: 'TRAINING_LESSON',
    decision: 'GENERATE',
    status: 'PENDING',
    reason: 'Não há conteúdo deste tipo para o tópico.',
    target_public_id: null,
    cost_cents: '0',
    ...overrides,
  }
}

function plano(overrides: Partial<GenerationPlan> = {}): GenerationPlan {
  return {
    public_id: 'plano1',
    competition_public_id: 'c1',
    status: 'DRAFT',
    kinds: ['TRAINING_LESSON'],
    options: {},
    estimate_cents: '0',
    estimate_is_known: false,
    estimate_basis: { unknown_features: ['training.script'] },
    spent_cents: '0',
    confirmed_at: null,
    finished_at: null,
    created_at: '2026-10-21T10:00:00Z',
    items: [item(), item({ topic_name: 'Regência' })],
    progress: { total: 2, pending: 2, done: 0, reused: 0, failed: 0, blocked: 0 },
    ...overrides,
  }
}

function renderSection(planos: GenerationPlan[]) {
  generationApi.plans.mockResolvedValue({
    items: planos,
    total: planos.length,
    page: 1,
    page_size: 10,
    pages: 1,
  })
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <GenerationSection />
    </QueryClientProvider>,
  )
}

describe('GenerationSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    adminCatalogApi.competitions.mockResolvedValue({
      items: [{ public_id: 'c1', name: 'TRT 5ª Região', year: 2026 }],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    })
  })

  it('sem histórico medido, diz que não dá para estimar em vez de mostrar número', async () => {
    renderSection([plano()])

    expect(
      await screen.findByText(/Não dá para estimar o custo deste plano/),
    ).toBeInTheDocument()
    expect(screen.getByText('training.script')).toBeInTheDocument()
  })

  it('com histórico, mostra a estimativa e diz de onde ela vem', async () => {
    renderSection([
      plano({
        estimate_cents: '2600',
        estimate_is_known: true,
        estimate_basis: {
          features: { 'training.script': { items: 2, samples: 4, median_cents: '13' } },
        },
      }),
    ])

    expect(await screen.findByText(/Estimativa: R\$\s?26,00/)).toBeInTheDocument()
    expect(screen.getByText(/mediana do custo medido/)).toBeInTheDocument()
  })

  it('deixa claro que montar o plano não gasta e que a saída é rascunho', async () => {
    renderSection([plano()])

    expect(await screen.findByText('Montar o plano não gasta nada')).toBeInTheDocument()
    expect(screen.getByText(/uma pessoa confirma/)).toBeInTheDocument()
  })

  it('o reaproveitado aparece com nome próprio, separado do gerado', async () => {
    renderSection([
      plano({
        status: 'DONE',
        items: [
          item({ status: 'DONE', reason: 'Rascunho gerado, aguardando revisão humana.' }),
          item({
            topic_name: 'Regência',
            decision: 'REUSE',
            status: 'REUSED',
            reason: 'Já existe conteúdo de outro concurso para este tópico.',
          }),
        ],
        progress: { total: 2, pending: 0, done: 1, reused: 1, failed: 0, blocked: 0 },
      }),
    ])

    await userEvent.click(await screen.findByText('Ver 2 itens'))

    expect(screen.getByText('Rascunho gerado')).toBeInTheDocument()
    expect(screen.getByText('Reaproveitado')).toBeInTheDocument()
    expect(screen.getAllByText(/outro concurso/).length).toBeGreaterThan(0)
  })

  it('confirmar é um ato explícito, e só aparece no rascunho', async () => {
    generationApi.confirm.mockResolvedValue(plano({ status: 'CONFIRMED' }))
    renderSection([plano()])

    await userEvent.click(await screen.findByRole('button', { name: /Confirmar e gerar/ }))

    await waitFor(() => expect(generationApi.confirm).toHaveBeenCalledWith('plano1'))
  })

  it('plano confirmado não oferece o botão de confirmar de novo', async () => {
    renderSection([plano({ status: 'RUNNING' })])

    await screen.findByText('Ver 2 itens')
    expect(screen.queryByRole('button', { name: /Confirmar e gerar/ })).not.toBeInTheDocument()
  })

  it('barrado pelo teto aparece destacado no progresso', async () => {
    renderSection([
      plano({
        status: 'DONE',
        progress: { total: 2, pending: 0, done: 1, reused: 0, failed: 0, blocked: 1 },
      }),
    ])

    expect(await screen.findByText('1 barrados')).toBeInTheDocument()
  })
})
