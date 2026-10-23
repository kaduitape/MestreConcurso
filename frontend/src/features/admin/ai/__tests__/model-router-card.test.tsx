/**
 * A tela do roteador tem duas obrigações acima das outras: **"não avaliada"
 * não pode parecer "não atendeu"** e **regra ligada com modelo indisponível
 * não pode parecer uma regra que vale**.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type {
  AIFeatureBinding,
  AIModelRoute,
  AIProvider,
  AIRoutingDecision,
} from '@/lib/api/types'

const { aiApi } = vi.hoisted(() => ({
  aiApi: {
    features: vi.fn(),
    routes: vi.fn(),
    routeDecisions: vi.fn(),
    updateRoute: vi.fn(),
    deleteRoute: vi.fn(),
    createRoute: vi.fn(),
  },
}))
vi.mock('@/lib/api/ai', () => ({ aiApi }))

const { ModelRouterCard } = await import('../model-router-card')

function feature(overrides: Partial<AIFeatureBinding> = {}): AIFeatureBinding {
  return {
    feature: 'question.classify',
    label: 'Classificação de questões',
    description: 'Sugere disciplina e assunto.',
    kind: 'chat',
    is_routable: true,
    is_enabled: true,
    provider_slug: 'openai',
    model_slug: 'gpt-4o-mini',
    fallback_provider_slug: null,
    fallback_model_slug: null,
    fallback_is_usable: false,
    temperature: '0.20',
    max_output_tokens: null,
    cache_ttl_hours: null,
    min_support: null,
    ...overrides,
  }
}

function route(overrides: Partial<AIModelRoute> = {}): AIModelRoute {
  return {
    id: 1,
    feature: 'question.classify',
    feature_label: 'Classificação de questões',
    label: 'Enunciado longo',
    priority: 10,
    is_enabled: true,
    provider_slug: 'openai',
    model_slug: 'gpt-4o',
    model_is_usable: true,
    min_input_chars: 50_000,
    max_input_chars: null,
    requires_json: null,
    min_budget_used_pct: null,
    required_signals: ['INPUT_CHARS'],
    ...overrides,
  }
}

function decision(overrides: Partial<AIRoutingDecision> = {}): AIRoutingDecision {
  return {
    id: 1,
    feature: 'question.classify',
    feature_label: 'Classificação de questões',
    model_slug: 'gpt-4o-mini',
    provider_slug: 'openai',
    reason: 'BINDING_DEFAULT',
    route_id: null,
    route_label: null,
    explanation: 'nenhuma regra se aplicou: valeu o modelo vinculado à funcionalidade',
    signals: { input_chars: 312, needs_json: true },
    trace: [],
    created_at: '2026-10-21T18:00:00Z',
    ...overrides,
  }
}

const providers: AIProvider[] = [
  {
    slug: 'openai',
    display_name: 'OpenAI (ChatGPT)',
    base_url: null,
    organization: null,
    is_active: true,
    has_api_key: true,
    api_key_hint: 'sk-…7890',
    api_key_set_at: null,
    last_tested_at: null,
    last_test_status: null,
    last_test_message: null,
    models: [],
  },
]

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <ModelRouterCard providers={providers} />
    </QueryClientProvider>,
  )
}

describe('ModelRouterCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    aiApi.features.mockResolvedValue([feature()])
    aiApi.routes.mockResolvedValue([])
    aiApi.routeDecisions.mockResolvedValue([])
  })

  it('diz que nenhuma IA participa da escolha do modelo', async () => {
    renderCard()
    await waitFor(() => expect(aiApi.routes).toHaveBeenCalled())
    expect(screen.getByText(/Nenhuma IA participa dessa escolha/)).toBeInTheDocument()
  })

  it('sem regra cadastrada, explica que vale o vínculo da funcionalidade', async () => {
    renderCard()
    expect(await screen.findByText('Nenhuma regra cadastrada')).toBeInTheDocument()
  })

  it('mostra as condições da regra e os sinais de que ela depende', async () => {
    aiApi.routes.mockResolvedValue([route()])
    renderCard()

    expect(await screen.findByText('Enunciado longo')).toBeInTheDocument()
    expect(screen.getByText(/entrada ≥ 50\.000 caracteres/)).toBeInTheDocument()
    expect(screen.getByText(/Depende de: tamanho da entrada/)).toBeInTheDocument()
  })

  it('uma regra sem condição avisa que vale para toda chamada', async () => {
    aiApi.routes.mockResolvedValue([
      route({ min_input_chars: null, required_signals: [] }),
    ])
    renderCard()

    expect(
      await screen.findByText(/sem condição: vale para toda chamada da funcionalidade/),
    ).toBeInTheDocument()
  })

  it('denuncia a regra ligada cujo modelo não está disponível', async () => {
    aiApi.routes.mockResolvedValue([route({ model_is_usable: false })])
    renderCard()

    expect(await screen.findByText('Regra ligada apontando para modelo indisponível')).toBeInTheDocument()
    expect(screen.getByText('modelo indisponível')).toBeInTheDocument()
  })

  it('"não avaliada" aparece com rótulo próprio, não como "não atendeu"', async () => {
    aiApi.routeDecisions.mockResolvedValue([
      decision({
        signals: { input_chars: 312, needs_json: true },
        trace: [
          {
            rule_id: 7,
            label: 'Orçamento apertado',
            priority: 50,
            outcome: 'NOT_EVALUATED',
            detail: 'esta chamada não informou: percentual do teto mensal já gasto',
            missing_signals: ['BUDGET_USED_PCT'],
            conditions: [],
          },
        ],
      }),
    ])
    renderCard()

    expect(await screen.findByText(/Orçamento apertado — não avaliada:/)).toBeInTheDocument()
    expect(screen.queryByText(/Orçamento apertado — não atendeu/)).not.toBeInTheDocument()
    expect(
      screen.getByText(/1 regra ficou sem avaliação por falta de sinal/),
    ).toBeInTheDocument()
  })

  it('o rastro traz as regras que não venceram, não só a vencedora', async () => {
    aiApi.routeDecisions.mockResolvedValue([
      decision({
        reason: 'RULE_MATCHED',
        model_slug: 'gpt-4o',
        route_id: 1,
        route_label: 'Enunciado longo',
        explanation: 'regra "Enunciado longo": entrada com 50.000 caracteres ou mais',
        trace: [
          {
            rule_id: 1,
            label: 'Enunciado longo',
            priority: 10,
            outcome: 'MATCHED',
            detail: 'entrada com 50.000 caracteres ou mais — observado: 80.000 caracteres',
            missing_signals: [],
            conditions: [],
          },
          {
            rule_id: 2,
            label: 'Enunciado curto',
            priority: 20,
            outcome: 'NOT_MATCHED',
            detail: 'entrada com até 1.000 caracteres — observado: 80.000 caracteres',
            missing_signals: [],
            conditions: [],
          },
        ],
      }),
    ])
    renderCard()

    expect(await screen.findByText(/Enunciado longo — atendeu:/)).toBeInTheDocument()
    expect(screen.getByText(/Enunciado curto — não atendeu:/)).toBeInTheDocument()
    expect(screen.getByText('regra aplicada')).toBeInTheDocument()
  })

  it('declara quando a chamada não informou nenhum sinal', async () => {
    aiApi.routeDecisions.mockResolvedValue([decision({ signals: {} })])
    renderCard()

    expect(
      await screen.findByText('Esta chamada não informou nenhum sinal.'),
    ).toBeInTheDocument()
  })

  it('a reserva depois de erro aparece como decisão própria', async () => {
    aiApi.routeDecisions.mockResolvedValue([
      decision({
        reason: 'FALLBACK_AFTER_ERROR',
        model_slug: 'gpt-4o',
        explanation:
          'o modelo gpt-4o-mini falhou (ai_provider_rate_limited) e o modelo de reserva atendeu no lugar dele',
      }),
    ])
    renderCard()

    expect(await screen.findByText('reserva depois de erro')).toBeInTheDocument()
    expect(screen.getByText(/ai_provider_rate_limited/)).toBeInTheDocument()
  })

  it('não oferece regra para funcionalidade que não aceita roteamento', async () => {
    aiApi.features.mockResolvedValue([
      feature({ feature: 'embeddings.default', label: 'Embeddings', kind: 'embedding', is_routable: false }),
    ])
    renderCard()

    await waitFor(() => expect(aiApi.features).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /Nova regra/ })).toBeDisabled()
    expect(screen.queryByRole('option', { name: 'Embeddings' })).not.toBeInTheDocument()
  })
})
