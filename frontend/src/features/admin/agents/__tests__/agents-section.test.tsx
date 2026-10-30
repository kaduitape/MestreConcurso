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
    status_label: '',
    attempts_exhausted: false,
    action: null,
    notes: [],
    attempts_history: [],
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
      // Falta de insumo tem estado próprio, e **não** consome tentativa.
      status: 'AWAITING_INPUT',
      status_label: 'aguardando insumo',
      detail: 'O concurso ainda não tem edital principal cadastrado.',
      attempts: 0,
      action: 'RESOLVE_INPUT',
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

  it('falta de insumo aparece como pendência, com o motivo, e nunca como concluído', async () => {
    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Tribunal de Teste/ }))

    await waitFor(() =>
      expect(screen.getAllByText('Aguardando insumo').length).toBeGreaterThan(0),
    )
    expect(
      screen.getByText('O concurso ainda não tem edital principal cadastrado.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('Concluído')).not.toBeInTheDocument()
    // E a tela oferece o caminho de saída, em vez de só mostrar o problema.
    expect(screen.getByText(/Anexe o PDF ou complete o cadastro/)).toBeInTheDocument()
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

describe('AgentsSection — diagnóstico', () => {
  /** A tela lê a lista e, ao abrir, o detalhe: as duas precisam concordar. */
  function comExecucao(execucao: AgentRun) {
    agentsApi.runs.mockResolvedValue({
      items: [execucao],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    })
    agentsApi.run.mockResolvedValue(execucao)
  }

  beforeEach(() => {
    vi.clearAllMocks()
    agentsApi.catalog.mockResolvedValue(catalog)
    adminCatalogApi.competitions.mockResolvedValue({
      items: [{ public_id: 'concurso-1', name: 'Tribunal de Teste', year: 2026 }],
      total: 1,
      page: 1,
      page_size: 50,
      pages: 1,
    })
  })

  it('tentativas esgotadas acompanham a causa, em vez de substituí-la', async () => {
    // O defeito original: a tela mostrava só "Esgotou as 2 tentativas".
    comExecucao({
      ...run,
      status: 'FAILED',
      error: 'Auditor de qualidade: relation "content_audits" does not exist',
      steps: [
        step({
          key: 'auditor',
          label: 'Auditor de qualidade',
          status: 'FAILED',
          status_label: 'falhou',
          detail: 'relation "content_audits" does not exist',
          attempts: 2,
          max_attempts: 2,
          attempts_exhausted: true,
          action: 'RETRY_STEP',
          attempts_history: [
            {
              number: 1,
              status: 'FAILED',
              detail: 'conexão com o banco recusada',
              error_code: 'agent_unhandled_error',
              request_id: 'req-1',
              duration_ms: 1200,
              cost_cents: '0',
              provider: null,
              model_slug: null,
              started_at: null,
              finished_at: null,
            },
            {
              number: 2,
              status: 'FAILED',
              detail: 'relation "content_audits" does not exist',
              error_code: 'agent_unhandled_error',
              request_id: 'req-2',
              duration_ms: 90,
              cost_cents: '0',
              provider: null,
              model_slug: null,
              started_at: null,
              finished_at: null,
            },
          ],
        }),
      ],
    })

    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Tribunal de Teste/ }))

    await waitFor(() => expect(screen.getByText('Falhou')).toBeInTheDocument())
    // A causa está na tela.
    expect(screen.getByText('relation "content_audits" does not exist')).toBeInTheDocument()
    // E o aviso de tentativas esgotadas vem **junto**, não em lugar dela.
    expect(screen.getByText(/tentativas automáticas acabaram/)).toBeInTheDocument()

    // O histórico tem as duas causas, cada uma com o próprio id de correlação.
    await userEvent.click(screen.getByRole('button', { name: /histórico de 2 tentativa/ }))
    expect(screen.getByText('conexão com o banco recusada')).toBeInTheDocument()
    expect(screen.getByText('req-1')).toBeInTheDocument()
    expect(screen.getByText('req-2')).toBeInTheDocument()
  })

  it('bloqueio por dependência diz o que houve com a dependência', async () => {
    comExecucao({
      ...run,
      status: 'DONE_WITH_NOTES',
      steps: [
        step({
          key: 'teacher',
          label: 'Professor',
          status: 'BLOCKED',
          status_label: 'bloqueado por dependência',
          detail: 'Depende de Analista de editais (aguardando insumo: o edital está sem PDF)',
          depends_on: ['notice_analyst'],
          action: 'RESOLVE_DEPENDENCY',
        }),
      ],
    })

    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Tribunal de Teste/ }))

    await waitFor(() =>
      expect(screen.getByText('Bloqueado por dependência')).toBeInTheDocument(),
    )
    expect(screen.getByText(/o edital está sem PDF/)).toBeInTheDocument()
    // Sem duplicar a lista crua de dependências: o motivo já diz tudo.
    expect(screen.queryByText(/^Depende de: notice_analyst$/)).not.toBeInTheDocument()
  })

  it('concluído com ressalvas não passa por concluído', async () => {
    comExecucao({
      ...run,
      status: 'DONE_WITH_NOTES',
      steps: [
        step({
          key: 'improvements',
          label: 'Analista de melhorias',
          status: 'DONE_WITH_NOTES',
          status_label: 'concluído com ressalvas',
          detail: '0 achados novos.',
          attempts: 1,
          notes: ['SUSPECT_ANSWER_KEY: não rodou — sem amostra suficiente'],
        }),
      ],
    })

    renderSection()
    await userEvent.click(await screen.findByRole('button', { name: /Tribunal de Teste/ }))

    await waitFor(() => expect(screen.getByText('Concluído com ressalvas')).toBeInTheDocument())
    // Falta de amostra aparece nomeada, não como silêncio.
    expect(screen.getByText(/SUSPECT_ANSWER_KEY: não rodou/)).toBeInTheDocument()
    expect(screen.queryByText('Concluído')).not.toBeInTheDocument()
  })
})
