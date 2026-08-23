import { Link, useNavigate } from 'react-router-dom'
import { LogOut, Search, Shield, User } from 'lucide-react'
import { Avatar } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { ThemeToggle } from './theme-toggle'
import { useAuth } from '@/providers/auth-provider'

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const { user, logout, hasPermission } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/entrar', { replace: true })
  }

  return (
    <header className="glass sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border px-4 lg:px-6">
      <button
        type="button"
        onClick={onOpenCommand}
        className="flex h-9 flex-1 items-center gap-2 rounded-md border border-border bg-surface-muted px-3 text-sm text-subtle transition hover:border-border-strong sm:max-w-md"
      >
        <Search className="size-4" aria-hidden />
        <span className="flex-1 text-left">Buscar ou executar uma ação…</span>
        <kbd className="hidden rounded border border-border-strong px-1.5 py-0.5 text-[10px] font-medium sm:inline">
          Ctrl K
        </kbd>
      </button>

      <div className="ml-auto flex items-center gap-1">
        <ThemeToggle />
        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="rounded-full transition hover:opacity-90"
                aria-label="Abrir menu da conta"
              >
                <Avatar name={user.full_name} src={user.profile?.avatar_url} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>
                <span className="block truncate text-sm font-medium text-foreground normal-case">
                  {user.full_name}
                </span>
                <span className="block truncate text-xs font-normal text-subtle normal-case">
                  {user.email}
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link to="/conta">
                  <User /> Minha conta
                </Link>
              </DropdownMenuItem>
              {hasPermission('admin_dashboard:read') && (
                <DropdownMenuItem asChild>
                  <Link to="/admin">
                    <Shield /> Administração
                  </Link>
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={handleLogout}>
                <LogOut /> Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  )
}
