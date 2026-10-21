import { api } from './client'
import type { NoticeDiff, Page } from './types'

export const noticeDiffApi = {
  list: (params: { page: number; page_size: number; competition_public_id?: string }) => {
    const query = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.competition_public_id)
      query.set('competition_public_id', params.competition_public_id)
    return api.get<Page<NoticeDiff>>(`/admin/notice-diffs?${query.toString()}`)
  },
  compare: (competition_public_id: string) =>
    api.post<NoticeDiff>('/admin/notice-diffs', { competition_public_id }),
  markReviewed: (publicId: string) =>
    api.post<NoticeDiff>(`/admin/notice-diffs/${publicId}/reviewed`),
}
