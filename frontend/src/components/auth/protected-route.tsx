import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '@/providers/auth-provider'
import { EmptyState } from '@/components/feedback/empty-state'
import { ShieldOff } from 'lucide-react'

function FullScreenLoader() {
  return (
    <div className="grid min-h-dvh place-items-center bg-background">
      <div className="flex items-center gap-3 text-muted">
        <Loader2 className="size-5 animate-spin" aria-hidden />
        <span className="text-sm">Carregando sua conta…</span>
      </div>
    </div>
  )
}

/** Exige sessão válida; preserva o destino para retornar após o login. */
export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) return <FullScreenLoader />
  if (!isAuthenticated) {
    return <Navigate to="/entrar" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

/** Exige uma permissão específica (RBAC também é verificado no servidor). */
export function RequirePermission({ permission }: { permission: string }) {
  const { hasPermission, isLoading } = useAuth()
  if (isLoading) return <FullScreenLoader />
  if (!hasPermission(permission)) {
    return (
      <EmptyState
        icon={ShieldOff}
        title="Acesso restrito"
        description="Sua conta não tem permissão para esta área. Se acredita que deveria ter, fale com um administrador."
      />
    )
  }
  return <Outlet />
}

/** Impede que quem já está autenticado veja as telas de login/cadastro. */
export function PublicOnlyRoute() {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return <FullScreenLoader />
  if (isAuthenticated) return <Navigate to="/hoje" replace />
  return <Outlet />
}
