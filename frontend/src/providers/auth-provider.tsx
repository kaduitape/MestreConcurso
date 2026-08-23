import * as React from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { authApi } from '@/lib/api/auth'
import { ApiError, onUnauthorized, tokenStorage } from '@/lib/api/client'
import type { CurrentUser } from '@/lib/api/types'
import { queryKeys } from '@/lib/query-client'

interface AuthContextValue {
  user: CurrentUser | null
  isLoading: boolean
  isAuthenticated: boolean
  hasPermission: (permission: string) => boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

/** Rótulo simples do dispositivo, útil na tela de sessões ativas. */
function deviceLabel(): string {
  const ua = navigator.userAgent
  const os = /Windows/.test(ua)
    ? 'Windows'
    : /Mac OS X/.test(ua)
      ? 'macOS'
      : /Android/.test(ua)
        ? 'Android'
        : /iPhone|iPad/.test(ua)
          ? 'iOS'
          : /Linux/.test(ua)
            ? 'Linux'
            : 'Desconhecido'
  const browser = /Edg\//.test(ua)
    ? 'Edge'
    : /Chrome\//.test(ua)
      ? 'Chrome'
      : /Safari\//.test(ua)
        ? 'Safari'
        : /Firefox\//.test(ua)
          ? 'Firefox'
          : 'Navegador'
  return `${browser} · ${os}`
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const [hasToken, setHasToken] = React.useState(() => Boolean(tokenStorage.access))

  const { data, isLoading, isFetched } = useQuery({
    queryKey: queryKeys.me,
    queryFn: authApi.me,
    enabled: hasToken,
    retry: false,
    staleTime: 60_000,
  })

  React.useEffect(
    () =>
      onUnauthorized(() => {
        setHasToken(false)
        queryClient.setQueryData(queryKeys.me, null)
        queryClient.clear()
      }),
    [queryClient],
  )

  const login = React.useCallback(
    async (email: string, password: string) => {
      await authApi.login(email, password, deviceLabel())
      setHasToken(true)
      const user = await authApi.me()
      queryClient.setQueryData(queryKeys.me, user)
    },
    [queryClient],
  )

  const logout = React.useCallback(async () => {
    try {
      await authApi.logout()
    } catch (error) {
      // Sessão já inválida no servidor: seguimos limpando o estado local.
      if (!(error instanceof ApiError)) throw error
    }
    setHasToken(false)
    queryClient.clear()
  }, [queryClient])

  const refresh = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.me })
  }, [queryClient])

  const user = (data as CurrentUser | undefined) ?? null

  const hasPermission = React.useCallback(
    (permission: string) => {
      if (!user) return false
      if (user.is_superuser || user.permissions.includes('*')) return true
      if (user.permissions.includes(permission)) return true
      const [resource] = permission.split(':')
      return user.permissions.includes(`${resource}:*`)
    },
    [user],
  )

  const value = React.useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading: hasToken && !isFetched && isLoading,
      isAuthenticated: Boolean(user),
      hasPermission,
      login,
      logout,
      refresh,
    }),
    [user, hasToken, isFetched, isLoading, hasPermission, login, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext)
  if (!context) throw new Error('useAuth precisa estar dentro de AuthProvider')
  return context
}
