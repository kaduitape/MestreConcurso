import { API_BASE, api, tokenStorage } from './client'
import type { MessageResponse, Notice, Page } from './types'

export interface NoticeInput {
  title: string
  competition_public_id?: string | null
  kind?: 'MAIN' | 'RECTIFICATION' | 'ADDENDUM' | 'RESULT'
  number?: string | null
  source_url?: string | null
  summary?: string | null
}

export const noticesApi = {
  list: (params: { page: number; page_size: number; status?: string }) => {
    const search = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.status) search.set('status', params.status)
    return api.get<Page<Notice>>(`/admin/notices?${search.toString()}`)
  },

  create: (input: NoticeInput) => api.post<Notice>('/admin/notices', input),

  get: (publicId: string) => api.get<Notice>(`/admin/notices/${publicId}`),

  update: (publicId: string, input: Partial<NoticeInput>) =>
    api.patch<Notice>(`/admin/notices/${publicId}`, input),

  remove: (publicId: string) => api.delete<MessageResponse>(`/admin/notices/${publicId}`),

  uploadFile: (publicId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<Notice['files'][number]>(`/admin/notices/${publicId}/files`, form)
  },

  removeFile: (filePublicId: string) =>
    api.delete<MessageResponse>(`/admin/notices/files/${filePublicId}`),

  /** Download autenticado: o arquivo nunca fica acessível por URL pública. */
  downloadFile: async (filePublicId: string, filename: string): Promise<void> => {
    const response = await fetch(`${API_BASE}/admin/notices/files/${filePublicId}/download`, {
      headers: { Authorization: `Bearer ${tokenStorage.access ?? ''}` },
    })
    if (!response.ok) throw new Error('Não foi possível baixar o arquivo.')
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    link.click()
    URL.revokeObjectURL(url)
  },
}
