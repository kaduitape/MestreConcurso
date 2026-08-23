import { api } from './client'
import type {
  AIAvailableProviders,
  AICacheStats,
  AIFeatureBinding,
  AIModel,
  AIProvider,
  ConnectionCheck,
  MessageResponse,
} from './types'

export const aiApi = {
  providers: () => api.get<AIProvider[]>('/admin/ai/providers'),

  available: () => api.get<AIAvailableProviders>('/admin/ai/providers/available'),

  createProvider: (slug: string) => api.post<AIProvider>('/admin/ai/providers', { slug }),

  updateProvider: (
    slug: string,
    input: { is_active?: boolean; base_url?: string | null; organization?: string | null },
  ) => api.patch<AIProvider>(`/admin/ai/providers/${slug}`, input),

  /** A chave sobe uma única vez; a API devolve apenas a dica (`sk-…1234`). */
  setKey: (slug: string, apiKey: string) =>
    api.put<AIProvider>(`/admin/ai/providers/${slug}/key`, { api_key: apiKey }),

  removeKey: (slug: string) => api.delete<AIProvider>(`/admin/ai/providers/${slug}/key`),

  testProvider: (slug: string) => api.post<ConnectionCheck>(`/admin/ai/providers/${slug}/test`),

  syncModels: (slug: string) => api.post<AIModel[]>(`/admin/ai/providers/${slug}/models/sync`),

  features: () => api.get<AIFeatureBinding[]>('/admin/ai/features'),

  setFeature: (
    feature: string,
    input: {
      provider_slug: string | null
      model_slug: string | null
      is_enabled: boolean
      cache_ttl_hours?: number | null
    },
  ) => api.put<AIFeatureBinding>(`/admin/ai/features/${feature}`, input),

  cacheStats: () => api.get<AICacheStats>('/admin/ai/cache'),

  purgeCache: (expiredOnly = false) =>
    api.delete<MessageResponse>(`/admin/ai/cache?expired_only=${expiredOnly}`),
}
