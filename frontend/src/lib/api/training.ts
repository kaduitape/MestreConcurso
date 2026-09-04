import { api } from './client'
import type {
  TrainingScript,
  Page,
  Training,
  TrainingInput,
  TrainingMetrics,
  TrainingProgress,
} from './types'

export const trainingApi = {
  published: (params: { page: number; page_size: number }) =>
    api.get<Page<Training>>(`/training?page=${params.page}&page_size=${params.page_size}`),
  training: (publicId: string) => api.get<Training>(`/training/${publicId}`),
  startProgress: (publicId: string) =>
    api.post<TrainingProgress>(`/training/${publicId}/progress/start`),
  saveProgress: (publicId: string, current_scene: number) =>
    api.put<TrainingProgress>(`/training/${publicId}/progress`, { current_scene }),
  complete: (publicId: string) => api.post<TrainingProgress>(`/training/${publicId}/complete`),
  adminList: (params: { page: number; page_size: number }) =>
    api.get<Page<Training>>(
      `/admin/training?page=${params.page}&page_size=${params.page_size}`,
    ),
  adminTraining: (publicId: string) => api.get<Training>(`/admin/training/${publicId}`),
  metrics: (publicId: string) =>
    api.get<TrainingMetrics>(`/admin/training/${publicId}/metrics`),
  create: (input: TrainingInput) => api.post<Training>('/admin/training', input),
  generate: (publicId: string) => api.post<Training>(`/admin/training/${publicId}/generate`),
  saveScript: (publicId: string, input: { title: string; script: TrainingScript }) =>
    api.put<Training>(`/admin/training/${publicId}/script`, input),
  publish: (publicId: string) => api.post<Training>(`/admin/training/${publicId}/publish`),
}
