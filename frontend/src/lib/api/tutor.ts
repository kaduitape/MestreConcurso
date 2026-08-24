import { API_BASE, api, tokenStorage } from './client'
import type {
  AskResult,
  ChatMode,
  Conversation,
  ConversationDetail,
  MessageResponse,
  Page,
  TutorStage,
  VideoAdmin,
  VocabularyTerm,
} from './types'

export interface ConversationInput {
  title?: string | null
  mode?: ChatMode
  notice_public_id?: string | null
  subject_public_id?: string | null
}

export const tutorApi = {
  conversations: () => api.get<Conversation[]>('/tutor/conversations'),

  createConversation: (input: ConversationInput) =>
    api.post<Conversation>('/tutor/conversations', input),

  conversation: (publicId: string) =>
    api.get<ConversationDetail>(`/tutor/conversations/${publicId}`),

  archive: (publicId: string) =>
    api.delete<MessageResponse>(`/tutor/conversations/${publicId}`),

  ask: (publicId: string, question: string) =>
    api.post<AskResult>(`/tutor/conversations/${publicId}/ask`, { question }),

  /**
   * Pergunta acompanhando cada etapa (SSE).
   *
   * Lido por fetch, e não por `EventSource`, porque o token vai no cabeçalho:
   * token em URL vaza para histórico e log de servidor.
   */
  askStream: (
    publicId: string,
    question: string,
    handlers: {
      onStage: (stage: TutorStage) => void
      onAnswer: (result: AskResult) => void
      onError?: (error: unknown) => void
    },
  ): (() => void) => {
    const controller = new AbortController()

    void (async () => {
      try {
        const search = new URLSearchParams({ question })
        const response = await fetch(
          `${API_BASE}/tutor/conversations/${publicId}/ask/stream?${search.toString()}`,
          {
            headers: {
              Authorization: `Bearer ${tokenStorage.access ?? ''}`,
              Accept: 'text/event-stream',
            },
            signal: controller.signal,
          },
        )
        if (!response.ok || !response.body) throw new Error('stream indisponível')

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        for (;;) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })

          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() ?? ''

          for (const block of blocks) {
            const eventName = /^event: (.+)$/m.exec(block)?.[1] ?? 'message'
            const data = /^data: (.+)$/m.exec(block)?.[1]
            if (!data) continue
            if (eventName === 'stage') {
              handlers.onStage(JSON.parse(data) as TutorStage)
            } else if (eventName === 'answer') {
              handlers.onAnswer(JSON.parse(data) as AskResult)
            } else if (eventName === 'error') {
              handlers.onError?.(JSON.parse(data))
              return
            }
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) handlers.onError?.(error)
      }
    })()

    return () => controller.abort()
  },
}

export const vocabularyApi = {
  list: (params: { page: number; page_size: number; search?: string }) => {
    const search = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.search) search.set('search', params.search)
    return api.get<Page<VocabularyTerm>>(`/vocabulary?${search.toString()}`)
  },

  add: (input: {
    term: string
    definition: string
    subject_public_id?: string | null
    message_public_id?: string | null
  }) => api.post<VocabularyTerm>('/vocabulary', input),

  review: (publicId: string) => api.post<VocabularyTerm>(`/vocabulary/${publicId}/review`),

  remove: (publicId: string) => api.delete<MessageResponse>(`/vocabulary/${publicId}`),
}

export const videosApi = {
  list: (params: { page: number; page_size: number }) =>
    api.get<Page<VideoAdmin>>(
      `/admin/videos?page=${params.page}&page_size=${params.page_size}`,
    ),

  create: (input: {
    title: string
    url: string
    provider?: string
    channel?: string | null
    subject_public_id?: string | null
    summary?: string | null
  }) => api.post<VideoAdmin>('/admin/videos', input),

  verify: (publicId: string) => api.post<VideoAdmin>(`/admin/videos/${publicId}/verify`),

  remove: (publicId: string) => api.delete<MessageResponse>(`/admin/videos/${publicId}`),
}
