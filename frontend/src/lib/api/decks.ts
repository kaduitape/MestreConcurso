import { api } from './client'
import type {
  DeckCatalogue,
  DeckGeneration,
  Flashcard,
  OfficialDeck,
  OfficialDeckCards,
  Page,
} from './types'

/** O lado de quem estuda: ver o que existe para o edital e entrar ou sair. */
export const decksApi = {
  catalogue: () => api.get<DeckCatalogue>('/decks'),

  subscribe: (publicId: string) => api.post<OfficialDeck>(`/decks/${publicId}/subscribe`, {}),

  unsubscribe: (publicId: string) => api.delete<OfficialDeck>(`/decks/${publicId}/subscribe`),
}

/** O lado da curadoria: montar, gerar, revisar cartão por cartão e publicar. */
export const adminDecksApi = {
  list: (params: { page: number; page_size: number; deck_status?: string }) => {
    const search = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.deck_status) search.set('deck_status', params.deck_status)
    return api.get<Page<OfficialDeck>>(`/admin/flashcard-decks?${search.toString()}`)
  },

  get: (publicId: string) => api.get<OfficialDeckCards>(`/admin/flashcard-decks/${publicId}`),

  create: (input: { topic_public_id: string; title?: string; description?: string }) =>
    api.post<OfficialDeck>('/admin/flashcard-decks', input),

  addCard: (publicId: string, input: { front: string; back: string; hint?: string }) =>
    api.post<Flashcard>(`/admin/flashcard-decks/${publicId}/cards`, input),

  generate: (
    publicId: string,
    input: { material: string; quantity: number; source_document?: string },
  ) => api.post<DeckGeneration>(`/admin/flashcard-decks/${publicId}/generate`, input),

  reviewCard: (publicId: string, cardPublicId: string, isActive: boolean) =>
    api.patch<Flashcard>(`/admin/flashcard-decks/${publicId}/cards/${cardPublicId}`, {
      is_active: isActive,
    }),

  publish: (publicId: string) =>
    api.post<OfficialDeck>(`/admin/flashcard-decks/${publicId}/publish`, {}),

  archive: (publicId: string) =>
    api.post<OfficialDeck>(`/admin/flashcard-decks/${publicId}/archive`, {}),

  reopen: (publicId: string) =>
    api.post<OfficialDeck>(`/admin/flashcard-decks/${publicId}/reopen`, {}),
}
