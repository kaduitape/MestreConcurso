/**
 * A tela de curadoria tem três obrigações acima das outras: **rascunho não pode
 * parecer publicado**, **cartão de IA continua marcado como de IA dentro de um
 * baralho oficial** e **o descarte da geração aparece**.
 */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Flashcard, OfficialDeck, OfficialDeckCards, Page } from '@/lib/api/types'

const { adminDecksApi, adminCatalogApi } = vi.hoisted(() => ({
  adminDecksApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    addCard: vi.fn(),
    generate: vi.fn(),
    reviewCard: vi.fn(),
    publish: vi.fn(),
    archive: vi.fn(),
    reopen: vi.fn(),
  },
  adminCatalogApi: { subjects: vi.fn(), topics: vi.fn() },
}))
vi.mock('@/lib/api/decks', () => ({ adminDecksApi }))
vi.mock('@/lib/api/catalog', () => ({ adminCatalogApi }))

const { DecksSection } = await import('../decks-section')

function deck(overrides: Partial<OfficialDeck> = {}): OfficialDeck {
  return {
    public_id: 'D1',
    title: 'Crase',
    description: null,
    status: 'DRAFT',
    source_kind: 'LESSON',
    source_ref: 'L1',
    topic_public_id: 'T1',
    topic_name: 'Crase',
    subject_name: 'Português',
    active_cards: 2,
    inactive_cards: 0,
    ai_cards: 2,
    subscribers: 0,
    is_subscribed: false,
    published_at: null,
    created_at: '2026-10-23T10:00:00Z',
    ...overrides,
  }
}

function card(overrides: Partial<Flashcard> = {}): Flashcard {
  return {
    public_id: 'C1',
    front: 'O que é crase?',
    back: 'A contração da preposição A com o artigo A.',
    hint: null,
    tags: [],
    subject_name: 'Português',
    origin: 'AI',
    source_ref: null,
    source_quote: 'A crase é a contração da preposição A com o artigo feminino A',
    source_page: null,
    source_document: 'Aula publicada: Aula de crase',
    model_slug: 'gpt-4o-mini',
    is_owned: false,
    is_official: true,
    deck_title: 'Crase',
    is_active: true,
    created_at: '2026-10-23T10:00:00Z',
    ...overrides,
  }
}

const page: Page<OfficialDeck> = {
  items: [deck()],
  total: 1,
  page: 1,
  page_size: 50,
  pages: 1,
}

const detail: OfficialDeckCards = { deck: deck(), cards: [card()] }

function renderSection() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <DecksSection />
    </QueryClientProvider>,
  )
}

describe('DecksSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    adminDecksApi.list.mockResolvedValue(page)
    adminDecksApi.get.mockResolvedValue(detail)
    adminDecksApi.publish.mockResolvedValue(deck({ status: 'PUBLISHED' }))
    adminCatalogApi.subjects.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 100,
      pages: 1,
    })
    adminCatalogApi.topics.mockResolvedValue([])
  })

  it('o rascunho diz que ninguém o vê', async () => {
    renderSection()

    expect(await screen.findByText('rascunho — ninguém vê')).toBeInTheDocument()
    expect(screen.getByText(/gerado de aula publicada/)).toBeInTheDocument()
  })

  it('o cartão de IA continua marcado como de IA dentro do baralho oficial', async () => {
    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /Ver cartões/ }))

    expect(await screen.findByText('Gerado por IA')).toBeInTheDocument()
    expect(screen.getByText(/Citação conferida no material/)).toBeInTheDocument()
  })

  it('publicar é um botão só do rascunho', async () => {
    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /Publicar/ }))

    expect(adminDecksApi.publish).toHaveBeenCalledWith('D1')
  })

  it('mostra o que a geração descartou', async () => {
    adminDecksApi.generate.mockResolvedValue({
      created: [card()],
      discarded: ['Qual a multa por errar a crase?'],
      duplicated: 0,
      skipped_reason: null,
      model: 'gpt-4o-mini',
      prompt_version: 'v1',
    })
    renderSection()

    await userEvent.click(await screen.findByRole('button', { name: /Ver cartões/ }))
    const material = await screen.findByLabelText(/Gerar por IA a partir de um material/)
    await userEvent.type(material, 'x'.repeat(90))
    await userEvent.click(screen.getByRole('button', { name: /Gerar cartões/ }))

    expect(
      await screen.findByText(/não citar o material literalmente/),
    ).toBeInTheDocument()
  })
})
