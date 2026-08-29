import { useQuery } from '@tanstack/react-query'
import { Link, NavLink } from 'react-router-dom'
import {
  ChevronRight,
  LayoutDashboard,
  Medal,
  PanelLeftClose,
  PanelLeftOpen,
  Target,
  Trophy,
  User,
} from 'lucide-react'
import { navigation } from './navigation'
import { BrandMark } from '@/components/game/brand-mark'
import { Tooltip } from '@/components/ui/tooltip'
import { gameApi } from '@/lib/api/game'
import { queryKeys } from '@/lib/query-client'
import { useAuth } from '@/providers/auth-provider'
import { cn } from '@/lib/utils'

const mobileNavigation = [
  { label: 'Hoje', to: '/hoje', icon: LayoutDashboard },
  { label: 'Missões', to: '/missoes', icon: Target },
  { label: 'Treinar', to: '/questoes', icon: Trophy },
  { label: 'Ranking', to: '/temporada', icon: Medal },
  { label: 'Perfil', to: '/progresso', icon: User },
]

function BattlePass({ collapsed }: { collapsed: boolean }) {
  const season = useQuery({ queryKey: queryKeys.gameSeason, queryFn: gameApi.season })
  const data = season.data

  if (collapsed) {
    return (
      <Tooltip side="right" content={data?.name ?? 'Passe de batalha'}>
        <Link
          to="/temporada"
          className="mx-auto grid size-11 place-items-center rounded-xl border border-game-gold/25 bg-game-gold/10 text-game-gold transition hover:border-game-gold/50"
        >
          <Medal className="size-5" aria-hidden />
        </Link>
      </Tooltip>
    )
  }

  const progress = Math.round((data?.progress ?? 0) * 100)
  return (
    <Link
      to="/temporada"
      className="group mx-3 block rounded-2xl border border-game-gold/25 bg-gradient-to-br from-game-gold/12 to-game-purple/10 p-4 shadow-[0_0_24px_rgb(245_158_11/0.08)] transition hover:-translate-y-0.5 hover:border-game-gold/45"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="game-label text-game-gold">Passe de batalha</span>
        <Medal className="size-5 text-game-gold" aria-hidden />
      </div>
      <p className="mt-2 truncate text-sm font-bold text-white">
        {season.isLoading ? 'Carregando temporada…' : (data?.name ?? 'Nenhuma temporada ativa')}
      </p>
      {data?.name && (
        <>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-game-gold to-game-orange transition-[width]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
            <span>{data.standing?.seasonal_xp.toLocaleString('pt-BR') ?? 0} XP</span>
            <span>{progress}%</span>
          </div>
        </>
      )}
      <span className="mt-3 flex items-center gap-1 text-[11px] font-bold text-game-gold">
        Ver temporada
        <ChevronRight className="size-3 transition group-hover:translate-x-0.5" />
      </span>
    </Link>
  )
}

export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { hasPermission } = useAuth()

  return (
    <>
      <aside
        className={cn(
          'sticky top-0 z-40 hidden h-dvh shrink-0 flex-col border-r border-white/[0.07] bg-[#070b18]/95 shadow-[12px_0_40px_rgb(0_0_0/0.18)] backdrop-blur-xl transition-[width] duration-200 lg:flex',
          collapsed ? 'w-[82px]' : 'w-[272px]',
        )}
      >
        <div
          className={cn(
            'flex h-[82px] items-center border-b border-white/[0.06] px-4',
            collapsed && 'justify-center px-2',
          )}
        >
          <BrandMark compact={collapsed} />
        </div>

        <nav className="game-scrollbar flex-1 space-y-6 overflow-y-auto px-3 py-5">
          {navigation.map((group) => {
            const items = group.items.filter(
              (item) => !item.permission || hasPermission(item.permission),
            )
            if (items.length === 0) return null

            return (
              <div key={group.title} className="space-y-1">
                {!collapsed && <p className="game-label px-3 pb-2">{group.title}</p>}
                {items.map((item) => {
                  const link = (
                    <NavLink
                      key={item.label}
                      to={item.to!}
                      className={({ isActive }) =>
                        cn(
                          'group relative flex min-h-11 items-center gap-3 overflow-hidden rounded-xl px-3 text-sm font-semibold transition-[color,background,border-color,box-shadow,transform] duration-200',
                          isActive
                            ? 'border border-game-purple/40 bg-gradient-to-r from-game-purple/85 to-game-blue/70 text-white shadow-[0_0_20px_rgb(124_58_237/0.3)]'
                            : 'border border-transparent text-slate-400 hover:translate-x-0.5 hover:border-white/[0.06] hover:bg-white/[0.045] hover:text-white',
                          collapsed && 'justify-center px-0',
                        )
                      }
                    >
                      <item.icon
                        className="size-[18px] shrink-0 transition-transform group-hover:scale-110"
                        aria-hidden
                      />
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </NavLink>
                  )

                  return collapsed ? (
                    <Tooltip key={item.label} side="right" content={item.label}>
                      {link}
                    </Tooltip>
                  ) : (
                    link
                  )
                })}
              </div>
            )
          })}
        </nav>

        <div className="border-t border-white/[0.06] py-3">
          <BattlePass collapsed={collapsed} />
          <button
            type="button"
            onClick={onToggle}
            className={cn(
              'mx-3 mt-2 flex min-h-10 items-center gap-2 rounded-xl px-3 text-xs font-semibold text-slate-500 transition hover:bg-white/5 hover:text-white',
              collapsed && 'mx-auto justify-center px-0',
            )}
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4" />
            ) : (
              <PanelLeftClose className="size-4" />
            )}
            {!collapsed && <span>Recolher menu</span>}
          </button>
        </div>
      </aside>

      <nav className="fixed inset-x-3 bottom-3 z-50 flex h-[68px] items-center justify-around rounded-2xl border border-white/10 bg-[#090d1c]/95 px-1 shadow-[0_18px_60px_rgb(0_0_0/0.55)] backdrop-blur-xl lg:hidden">
        {mobileNavigation.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex min-w-14 flex-col items-center gap-1 rounded-xl px-2 py-2 text-[10px] font-bold transition',
                isActive ? 'bg-game-purple/20 text-game-purple-light' : 'text-slate-500',
              )
            }
          >
            <item.icon className="size-5" aria-hidden />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </>
  )
}
