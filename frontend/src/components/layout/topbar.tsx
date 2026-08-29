import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Bell, Flame, LogOut, Search, Shield, Sparkles, User } from 'lucide-react'
import { Avatar } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { useAuth } from '@/providers/auth-provider'

export function Topbar({ onOpenCommand }: { onOpenCommand: () => void }) {
  const { user, logout, hasPermission } = useAuth()
  const navigate = useNavigate()
  const profile = useQuery({ queryKey: queryKeys.gameProfile, queryFn: gameApi.profile })
  const game = profile.data

  const handleLogout = async () => {
    await logout()
    navigate('/entrar', { replace: true })
  }

  return (
    <header className="sticky top-0 z-30 flex min-h-[74px] items-center gap-3 border-b border-white/[0.07] bg-[#050816]/80 px-4 backdrop-blur-2xl lg:px-6">
      <div className="hidden min-w-0 flex-1 items-center gap-3 xl:flex">
        <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-game-orange/10 text-game-orange">
          <Flame className="size-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold text-white">Foco total, guerreiro.</p>
          <p className="truncate text-[11px] text-slate-500">Sua aprovação é a missão.</p>
        </div>
      </div>

      <button
        type="button"
        onClick={onOpenCommand}
        className="flex h-11 min-w-0 flex-1 items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.035] px-3 text-sm text-slate-500 transition hover:border-game-purple/35 hover:bg-white/[0.055] sm:max-w-sm xl:flex-none"
      >
        <Search className="size-4 shrink-0" aria-hidden />
        <span className="flex-1 truncate text-left">Buscar ou comandar…</span>
        <kbd className="hidden rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 text-[10px] font-bold sm:inline">
          Ctrl K
        </kbd>
      </button>

      {game && (
        <div className="hidden items-center divide-x divide-white/[0.08] rounded-xl border border-white/[0.08] bg-white/[0.035] lg:flex">
          <div className="px-4 py-2">
            <p className="game-label text-[9px]">XP total</p>
            <p className="mt-0.5 text-sm font-extrabold text-white tabular-nums">
              {game.level.xp_total.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="px-4 py-2">
            <p className="game-label text-[9px]">Sequência</p>
            <p className="mt-0.5 flex items-center gap-1 text-sm font-extrabold text-game-orange">
              <Flame className="size-3.5" /> {game.streak.current} dias
            </p>
          </div>
          <div className="min-w-28 px-4 py-2">
            <div className="flex items-center justify-between gap-3">
              <p className="game-label text-[9px]">Nível {game.level.level}</p>
              <span className="text-[9px] font-bold text-game-purple-light">
                {game.rank.name}
              </span>
            </div>
            <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-gradient-to-r from-game-purple to-game-blue"
                style={{ width: `${Math.round(game.level.ratio * 100)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      <div className="ml-auto flex items-center gap-1">
        <button
          type="button"
          className="relative grid size-10 place-items-center rounded-xl text-slate-400 transition hover:bg-white/5 hover:text-white"
          aria-label="Notificações"
        >
          <Bell className="size-[18px]" />
          <span className="absolute top-2 right-2 size-1.5 rounded-full bg-game-purple-light shadow-[0_0_8px_rgb(168_85_247/0.8)]" />
        </button>
        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="ml-1 flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.035] p-1.5 pr-2 transition hover:border-game-purple/35"
                aria-label="Abrir menu da conta"
              >
                <Avatar name={user.full_name} src={user.profile?.avatar_url} />
                <span className="hidden text-left sm:block">
                  <span className="block max-w-28 truncate text-xs font-bold text-white">
                    {user.full_name}
                  </span>
                  <span className="flex items-center gap-1 text-[9px] font-bold text-game-purple-light uppercase">
                    <Sparkles className="size-2.5" /> {game?.rank.name ?? 'Candidato'}
                  </span>
                </span>
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
