/**
 * A tela dos baralhos oficiais tem duas obrigações acima das outras:
 *
 * 1. **Entrar é escolha do candidato.** A tela não pode sugerir que o baralho
 *    já está na fila dele; o botão é o consentimento.
 * 2. **Sair não apaga memória.** A mensagem de saída diz isso, porque a dúvida
 *    "vou perder meu progresso?" é o que faz alguém nunca sair — e aí a fila
 *    deixa de ser sobre o concurso dele.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { DeckCatalogue, OfficialDeck } from '@/lib/api/types'

const { decksApi } = vi.hoisted(() => ({
  decksApi: {
    catalogue: vi.fn(),
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
  },
}))
vi.mock('@/lib/api/decks', () => ({ decksApi }))

const { OfficialDecksPage } = await import('../official-decks-page')

function deck(overrides: Partial<OfficialDeck> = {}): OfficialDeck {
  return {
    public_id: 'D1',
    title: 'Crase',
    description: 'Os casos de crase cobrados pela banca.',
    status: 'PUBLISHED',
    source_kind: 'LESSON',
    source_ref: 'L1',
    topic_public_id: 'T1',
    topic_name: 'Crase',
    subject_name: 'Português',
    active_cards: 12,
    inactive_cards: 0,
    ai_cards: 5,
    subscribers: 30,
    is_subscribed: false,
    published_at: '2026-10-23T10:00:00Z',
    created_at: '2026-10-20T10:00:00Z',
    ...overrides,
  }
}

function catalogue(overrides: Partial<DeckCatalogue> = {}): DeckCatalogue {
  return {
    items: [deck()],
    total: 1,
    scope: 'Baralhos dos tópicos do edital de Concurso da Árvore.',
    competition_name: 'Concurso da Árvore',
    ...overrides,
  }
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <OfficialDecksPage />
    </QueryClientProvider>,
  )
}

describe('OfficialDecksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    decksApi.catalogue.mockResolvedValue(catalogue())
    decksApi.subscribe.mockResolvedValue(deck({ is_subscribed: true }))
    decksApi.unsubscribe.mockResolvedValue(deck({ is_subscribed: false }))
  })

  it('diz de onde vem a lista e que o baralho tem cartão gerado por IA', async () => {
    renderPage()

    expect(
      await screen.findByText('Baralhos dos tópicos do edital de Concurso da Árvore.'),
    ).toBeInTheDocument()
    expect(screen.getByText('tem cartão gerado por IA')).toBeInTheDocument()
    expect(screen.getByText(/5 gerado\(s\) por IA/)).toBeInTheDocument()
  })

  it('entrar no baralho é uma ação do candidato, não um estado da plataforma', async () => {
    renderPage()

    const entrar = await screen.findByRole('button', { name: /Entrar no baralho/ })
    expect(screen.queryByText(/estão na sua fila de revisão/)).not.toBeInTheDocument()

    await userEvent.click(entrar)

    expect(decksApi.subscribe).toHaveBeenCalledWith('D1')
  })

  it('quem já assinou vê que os cartões estão na fila e pode sair', async () => {
    decksApi.catalogue.mockResolvedValue(catalogue({ items: [deck({ is_subscribed: true })] }))
    renderPage()

    expect(await screen.findByText(/estão na sua fila de revisão/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /Sair do baralho/ }))

    expect(decksApi.unsubscribe).toHaveBeenCalledWith('D1')
  })

  it('sem baralho publicado para os tópicos, não finge recomendação', async () => {
    decksApi.catalogue.mockResolvedValue(
      catalogue({
        items: [],
        total: 0,
        scope: 'Você ainda não escolheu um concurso principal: a lista traz só os baralhos que você já assinou.',
        competition_name: null,
      }),
    )
    renderPage()

    expect(await screen.findByText(/não escolheu um concurso principal/)).toBeInTheDocument()
    expect(
      screen.getByText('Nenhum baralho publicado para os seus tópicos'),
    ).toBeInTheDocument()
  })
})
