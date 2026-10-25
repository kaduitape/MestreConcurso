import { api } from './client'
import type { Competition, CompetitionIntake, IntakeApplyInput, Page } from './types'

export const intakeApi = {
  list: (params: { page: number; page_size: number; status?: string }) => {
    const search = new URLSearchParams({
      page: String(params.page),
      page_size: String(params.page_size),
    })
    if (params.status) search.set('status', params.status)
    return api.get<Page<CompetitionIntake>>(`/admin/competition-intakes?${search.toString()}`)
  },

  start: (url: string, autoApply: boolean) =>
    api.post<CompetitionIntake>('/admin/competition-intakes', { url, auto_apply: autoApply }),

  /** Sobe o PDF do edital. Não há link para escolher: o documento veio apontado. */
  upload: (file: File, autoApply: boolean) => {
    const form = new FormData()
    form.append('file', file)
    form.append('auto_apply', String(autoApply))
    return api.post<CompetitionIntake>('/admin/competition-intakes/upload', form)
  },

  get: (publicId: string) =>
    api.get<CompetitionIntake>(`/admin/competition-intakes/${publicId}`),

  /** Quando o serviço recusou escolher, uma pessoa aponta o PDF. */
  choose: (publicId: string, url: string, autoApply: boolean) =>
    api.post<CompetitionIntake>(`/admin/competition-intakes/${publicId}/choose`, {
      url,
      auto_apply: autoApply,
    }),

  apply: (publicId: string, input: IntakeApplyInput) =>
    api.post<Competition>(`/admin/competition-intakes/${publicId}/apply`, input),

  reject: (publicId: string, reason: string) =>
    api.post<CompetitionIntake>(`/admin/competition-intakes/${publicId}/reject`, { reason }),
}
