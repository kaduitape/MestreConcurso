import { API_BASE, api, tokenStorage } from './client'
import type {
  AnalysisStarted,
  AnalysisState,
  MessageResponse,
  Notice,
  NoticeFact,
  Radiography,
} from './types'

export const noticeAnalysisApi = {
  analyze: (publicId: string) =>
    api.post<AnalysisStarted>(`/admin/notices/${publicId}/analyze`),

  state: (publicId: string) => api.get<AnalysisState>(`/admin/notices/${publicId}/analysis`),

  radiography: (publicId: string) =>
    api.get<Radiography>(`/admin/notices/${publicId}/radiography`),

  reviewFact: (publicId: string, factId: number, value: unknown) =>
    api.patch<NoticeFact>(`/admin/notices/${publicId}/facts/${factId}`, { value }),

  confirm: (publicId: string) => api.post<Notice>(`/admin/notices/${publicId}/confirm`),

  reset: (publicId: string) =>
    api.post<MessageResponse>(`/admin/notices/${publicId}/reset-analysis`),

  /**
   * Acompanhamento ao vivo por SSE.
   *
   * O `EventSource` do navegador não envia cabeçalho de autorização, então lemos o
   * stream por fetch e decodificamos os eventos manualmente.
   */
  stream: (
    publicId: string,
    handlers: {
      onProgress: (state: AnalysisState) => void
      onDone?: () => void
      onError?: (error: unknown) => void
    },
  ): (() => void) => {
    const controller = new AbortController()

    void (async () => {
      try {
        const response = await fetch(
          `${API_BASE}/admin/notices/${publicId}/analysis/stream`,
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
            if (eventName === 'progress') {
              handlers.onProgress(JSON.parse(data) as AnalysisState)
            } else if (eventName === 'done') {
              handlers.onDone?.()
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
