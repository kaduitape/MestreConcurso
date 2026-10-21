import { api } from './client'
import type {
  AIBudget,
  AIBudgetInput,
  AIAvailableProviders,
  AICacheStats,
  AIFeatureBinding,
  AIModel,
  AIModelRoute,
  AIProvider,
  AIRoutingDecision,
  ConnectionCheck,
  MessageResponse,
} from './types'

/** Condições de uma regra de roteamento, como a API as recebe. */
export interface AIModelRouteConditions {
  min_input_chars?: number | null
  max_input_chars?: number | null
  requires_json?: boolean | null
  min_budget_used_pct?: number | null
}

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
      /**
       * A reserva viaja em toda gravação. Omitir o campo apaga a reserva no
       * servidor — trocar o modelo principal não pode esquecer a reserva por
       * efeito colateral.
       */
      fallback_provider_slug?: string | null
      fallback_model_slug?: string | null
      cache_ttl_hours?: number | null
    },
  ) => api.put<AIFeatureBinding>(`/admin/ai/features/${feature}`, input),

  routes: (feature?: string) =>
    api.get<AIModelRoute[]>(
      feature ? `/admin/ai/routes?feature=${encodeURIComponent(feature)}` : '/admin/ai/routes',
    ),

  createRoute: (
    input: {
      feature: string
      label: string
      priority: number
      is_enabled: boolean
      provider_slug: string
      model_slug: string
    } & AIModelRouteConditions,
  ) => api.post<AIModelRoute>('/admin/ai/routes', input),

  updateRoute: (
    routeId: number,
    input: {
      label?: string
      priority?: number
      is_enabled?: boolean
      provider_slug?: string
      model_slug?: string
      clear_conditions?: boolean
    } & AIModelRouteConditions,
  ) => api.patch<AIModelRoute>(`/admin/ai/routes/${routeId}`, input),

  deleteRoute: (routeId: number) =>
    api.delete<MessageResponse>(`/admin/ai/routes/${routeId}`),

  routeDecisions: (feature?: string, limit = 25) =>
    api.get<AIRoutingDecision[]>(
      `/admin/ai/routes/decisions?limit=${limit}${
        feature ? `&feature=${encodeURIComponent(feature)}` : ''
      }`,
    ),

  budget: () => api.get<AIBudget>('/admin/ai/budget'),
  setBudget: (input: AIBudgetInput) => api.put<AIBudget>('/admin/ai/budget', input),

  cacheStats: () => api.get<AICacheStats>('/admin/ai/cache'),

  purgeCache: (expiredOnly = false) =>
    api.delete<MessageResponse>(`/admin/ai/cache?expired_only=${expiredOnly}`),
}
