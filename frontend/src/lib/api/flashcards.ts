import { api } from './client'
import type {
  CardGeneration,
  CardOrigin,
  CardRating,
  Flashcard,
  MessageResponse,
  Page,
  ReviewQueue,
  ReviewResult,
  ReviewStats,
} from './types'

export const flashcardsApi = {
  list: (params: {
    page: number
    page_size: number
    search?: string
    subject?: string
    origin?: CardOrigin | ''
  }) => {
    const search = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    for (const key of ['search', 'subject', 'origin'] as const) {
      const value = params[key]
      if (value) search.set(key, String(value))
    }
    return api.get<Page<Flashcard>>(`/flashcards?${search.toString()}`)
  },

  create: (input: {
    front: string
    back: string
    hint?: string | null
    tags?: string[]
    subject_public_id?: string | null
  }) => api.post<Flashcard>('/flashcards', input),

  update: (
    publicId: string,
    input: { front?: string; back?: string; hint?: string | null; tags?: string[] },
  ) => api.patch<Flashcard>(`/flashcards/${publicId}`, input),

  remove: (publicId: string) => api.delete<MessageResponse>(`/flashcards/${publicId}`),

  fromQuestion: (questionPublicId: string) =>
    api.post<Flashcard>('/flashcards/from-source', { question_public_id: questionPublicId }),

  fromError: (errorPublicId: string) =>
    api.post<Flashcard>('/flashcards/from-source', { error_public_id: errorPublicId }),

  generate: (input: {
    material: string
    quantity: number
    subject_public_id?: string | null
    source_document?: string | null
  }) => api.post<CardGeneration>('/flashcards/generate', input),
}

export const reviewApi = {
  queue: (params?: { daily_limit?: number; new_per_day?: number }) => {
    const search = new URLSearchParams()
    if (params?.daily_limit) search.set('daily_limit', String(params.daily_limit))
    if (params?.new_per_day !== undefined) search.set('new_per_day', String(params.new_per_day))
    const query = search.toString()
    return api.get<ReviewQueue>(`/review/queue${query ? `?${query}` : ''}`)
  },

  flash: (size = 10) => api.get<ReviewQueue>(`/review/flash?size=${size}`),

  answer: (publicId: string, input: { rating: CardRating; time_seconds?: number }) =>
    api.post<ReviewResult>(`/review/${publicId}/answer`, {
      rating: input.rating,
      time_seconds: input.time_seconds ?? 0,
    }),

  postpone: (days = 1) => api.post<MessageResponse>(`/review/postpone?days=${days}`),

  stats: () => api.get<ReviewStats>('/review/stats'),
}
