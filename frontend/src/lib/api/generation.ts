import { api } from './client'
import type { GenerationPlan, GenerationPlanInput, Page } from './types'

export const generationApi = {
  plans: (params: { page: number; page_size: number }) =>
    api.get<Page<GenerationPlan>>(
      `/admin/generation?page=${params.page}&page_size=${params.page_size}`,
    ),
  plan: (publicId: string) => api.get<GenerationPlan>(`/admin/generation/${publicId}`),
  create: (input: GenerationPlanInput) => api.post<GenerationPlan>('/admin/generation', input),
  confirm: (publicId: string) =>
    api.post<GenerationPlan>(`/admin/generation/${publicId}/confirm`),
  cancel: (publicId: string) =>
    api.post<GenerationPlan>(`/admin/generation/${publicId}/cancel`),
}
