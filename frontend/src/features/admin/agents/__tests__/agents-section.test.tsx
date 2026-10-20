/**
 * A tela do orquestrador tem uma obrigação acima das outras: **pulado não pode
 * parecer concluído**. Um passo verde que não fez nada é pior que um passo
 * vermelho, porque ninguém investiga o verde. É isso que estes testes cobram.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AgentCatalog, AgentRun, AgentStep } from '@/lib/api/types'

const { agentsApi } = vi.hoisted(() => ({
  agentsApi: {
    catalog: vi.fn(),
    runs: vi.fn(),
    run: vi.fn(),
    create: vi.fn(),
    execute: vi.fn(),
    executeOne: vi.fn(),
  },
}))
const { adminCatalogApi } = vi.hoisted(() => ({
  adminCatalogApi: { competitions: vi.fn() },
}))

vi.mock('@/lib/api/agents', () => ({ agentsApi }))
vi.mock('@/lib/api/catalog', () => ({ adminCatalogApi }))

const { AgentsSection } = await import('../agents-section')

function step(overrides: Partial<AgentStep>): AgentStep {
  return {
    key: 'notice_analyst',
    label: 'Analista de editais',
    description: 'Lê o PDF e estrutura o edital.',
    status: 'PENDING',
    depends_on: [],
    attempts: 0,
    max_attempts: 2,
    detail: null,
    is_implemented: true,
    ...overrides,
  }
}

const catalog: AgentCatalog = {
  layers: [['notice_analyst'], ['statistics']],
  agents: [
    {
      key: 'notice_analyst',
      label: 'Analista de editais',
      description: 'Lê o PDF e estrutura o edital.',
      depends_on: [],
      is_implemented: true,
      pending_reason: null,
    },
    {
      key: 'auditor',
      label: 'Auditor de qualidade',
      description: 'Confere o que os outros produziram.',
      depends_on: [],
      is_implemented: false,
      pending_reason: 'O auditor é a Fase 3, e vem antes de qualquer geração em massa.',
    },
  ],
}

const run: AgentRun = {
  public_id: 'exec12345678',
  competition_public_id: 'concurso-1',
  status: 'DONE',
  error: null,
  cost_cents: '0',
  started_at: '2026-10-20T12:00:00Z',
  finished_at: '2026-10-20T12:01:00Z',
  created_at: '2026-10-20T12:00:00Z',
  steps: [
    step({
      key: 'notice_analyst',
      status: 'SKIPPED',
      detail: 'O concurso ainda não tem edital principal cadastrado.',
      attempts: 1,
    }),
    step({
      key: 'auditor',
      label: 'Auditor de qualidade',
      status: 'SKIPPED',
      detail: 'O auditor é a Fase 3, e vem antes de qualquer geração em massa.',
      is_implemented: false,
    }),
    step({
      key: 'teacher',
      label: 'Professor',
      status: 'BUDGET_BLOCKED',
      detail: 'O teto mensal de gasto com IA foi atingido.',
      is_implemented: false,
    }),
  ],
}

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AgentsSection />
    </QueryClientProvider>,
  )
}

describe('AgentsSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    agentsApi.catalog.mockResolvedValue(catalog)
    agentsApi.runs.mockResolvedValue({
      items: [run],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    })
    agentsApi.run.mockResolvedValue(run)
    adminCatalogApi.competitions.mockResolvedValue({
      items: [{ public_id: 'concurso-1', name: 'Tribunal de Teste', year: 2026 }],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    })
  })

  it('conta os agentes construídos a partir do catálogo, sem número escrito à mão', async () => {
    renderSection()
    expect(await screen.findByText(/Hoje 1 dos 2 agentes rodam/)).toBeInTheDocument()
  })

  it('mostra o agente que ainda não existe com o motivo escrito', async () => {
    renderSection()
    expect(await screen.findByText('Auditor de qualidade')).toBeInTheDocument()
    expect(
      screen.getAllByText(/O auditor é a Fase 3/).length,
      'o motivo precisa aparecer, não só o estado',
    ).toBeGreaterThan(0)
  })

  it('passo pulado aparece como pulado, com o motivo, e nunca como concluído', async () => {
    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Tribunal de Teste/ }))

    await waitFor(() => expect(screen.getAllByText('Pulado').length).toBeGreaterThan(0))
    expect(
      screen.getByText('O concurso ainda não tem edital principal cadastrado.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Concluído')).not.toBeInTheDocument()
    // Dois passos desta execução não têm implementação: os dois dizem isso.
    expect(screen.getAllByText('ainda não existe')).toHaveLength(2)
  })

  it('barrado pelo teto não se confunde com falha', async () => {
    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Tribunal de Teste/ }))

    await waitFor(() => expect(screen.getByText('Barrado pelo teto')).toBeInTheDocument())
    expect(screen.queryByText('Falhou')).not.toBeInTheDocument()
  })
})
