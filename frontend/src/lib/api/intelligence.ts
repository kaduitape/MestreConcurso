import { api } from './client'
import type {
  BoardDna,
  CauseSuggestion,
  ErrorAnalysis,
  ErrorCause,
  ErrorNotebook,
  IncidenceMap,
  MessageResponse,
  Page,
  PendingAttempt,
  PriorityList,
  RecomputeResult,
  TrapPattern,
} from './types'

export const intelligenceApi = {
  incidence: (boardSlug: string) =>
    api.get<IncidenceMap>(`/intelligence/incidence/${boardSlug}`),

  boardDna: (boardSlug: string) => api.get<BoardDna>(`/intelligence/board-dna/${boardSlug}`),

  priority: () => api.get<PriorityList>('/intelligence/priority'),

  recomputePriority: () => api.post<PriorityList>('/intelligence/priority/recompute'),

  recomputeBoards: (boardSlug?: string) =>
    api.post<RecomputeResult[]>(
      `/admin/intelligence/recompute${boardSlug ? `?board=${boardSlug}` : ''}`,
    ),
}

export const errorsApi = {
  notebook: () => api.get<ErrorNotebook>('/errors/notebook'),

  pending: () => api.get<PendingAttempt[]>('/errors/pending'),

  traps: () => api.get<TrapPattern[]>('/errors/traps'),

  list: (params: { page: number; page_size: number; cause?: string; pending?: boolean }) => {
    const search = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.cause) search.set('cause', params.cause)
    if (params.pending) search.set('pending', 'true')
    return api.get<Page<ErrorAnalysis>>(`/errors?${search.toString()}`)
  },

  classify: (
    attemptPublicId: string,
    input: { cause: ErrorCause; trap_slug?: string | null; note?: string | null },
  ) =>
    api.post<ErrorAnalysis>(`/errors/attempts/${attemptPublicId}`, {
      cause: input.cause,
      trap_slug: input.trap_slug ?? null,
      note: input.note ?? null,
    }),

  suggestCause: (attemptPublicId: string) =>
    api.post<CauseSuggestion>(`/errors/attempts/${attemptPublicId}/suggest-cause`),

  confirm: (publicId: string) => api.post<ErrorAnalysis>(`/errors/${publicId}/confirm`),

  resolve: (publicId: string) => api.post<ErrorAnalysis>(`/errors/${publicId}/resolve`),

  remove: (publicId: string) => api.delete<MessageResponse>(`/errors/${publicId}`),
}
