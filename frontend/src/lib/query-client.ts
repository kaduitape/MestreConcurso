import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './api/client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        // Erros de autenticação/permissão não melhoram com nova tentativa.
        if (error instanceof ApiError && error.status < 500) return false
        return failureCount < 2
      },
    },
    mutations: { retry: false },
  },
})

export const queryKeys = {
  me: ['me'] as const,
  sessions: ['sessions'] as const,
  adminOverview: ['admin', 'overview'] as const,
  adminUsers: (params: unknown) => ['admin', 'users', params] as const,
  adminRoles: ['admin', 'roles'] as const,
  adminAudit: (params: unknown) => ['admin', 'audit', params] as const,
}
