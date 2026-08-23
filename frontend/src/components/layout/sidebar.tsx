import { NavLink } from 'react-router-dom'
import { GraduationCap, Lock, PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { navigation } from './navigation'
import { useAuth } from '@/providers/auth-provider'
import { Tooltip } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean
  onToggle: () => void
}) {
  const { hasPermission } = useAuth()

  return (
    <aside
      className={cn(
        'sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200 lg:flex',
        collapsed ? 'w-[76px]' : 'w-[264px]',
      )}
    >
      <div className="flex h-16 items-center gap-2.5 px-4">
        <span className="ai-gradient grid size-9 shrink-0 place-items-center rounded-md text-white">
          <GraduationCap className="size-5" aria-hidden />
        </span>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">Concurso Mestre</p>
            <p className="ai-text truncate text-xs font-semibold">IA</p>
          </div>
        )}
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {navigation.map((group) => {
          const items = group.items.filter(
            (item) => !item.permission || hasPermission(item.permission),
          )
          if (items.length === 0) return null

          return (
            <div key={group.title} className="space-y-1">
              {!collapsed && (
                <p className="px-2.5 pb-1 text-[11px] font-semibold tracking-wider text-subtle uppercase">
                  {group.title}
                </p>
              )}
              {items.map((item) => {
                const content = (
                  <span className="flex items-center gap-3">
                    <item.icon className="size-4 shrink-0" aria-hidden />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </span>
                )

                if (!item.to) {
                  return (
                    <Tooltip
                      key={item.label}
                      side="right"
                      content={`Disponível na ${item.phase}`}
                    >
                      <div
                        aria-disabled
                        className="flex cursor-not-allowed items-center justify-between rounded-md px-2.5 py-2 text-sm text-subtle/70"
                      >
                        {content}
                        {!collapsed && <Lock className="size-3.5" aria-hidden />}
                      </div>
                    </Tooltip>
                  )
                }

                return (
                  <NavLink
                    key={item.label}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center rounded-md px-2.5 py-2 text-sm font-medium transition',
                        isActive
                          ? 'bg-primary-soft text-primary'
                          : 'text-muted hover:bg-surface-muted hover:text-foreground',
                      )
                    }
                  >
                    {content}
                  </NavLink>
                )
              })}
            </div>
          )
        })}
      </nav>

      <button
        type="button"
        onClick={onToggle}
        className="m-3 flex items-center gap-2 rounded-md px-2.5 py-2 text-sm text-muted transition hover:bg-surface-muted hover:text-foreground"
        aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}
      >
        {collapsed ? (
          <PanelLeftOpen className="size-4" aria-hidden />
        ) : (
          <>
            <PanelLeftClose className="size-4" aria-hidden />
            <span>Recolher</span>
          </>
        )}
      </button>
    </aside>
  )
}
