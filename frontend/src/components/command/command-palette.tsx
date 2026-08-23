import * as React from 'react'
import { Command } from 'cmdk'
import { useNavigate } from 'react-router-dom'
import { LayoutDashboard, LogOut, Moon, Shield, Sun, User, Monitor } from 'lucide-react'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { useAuth } from '@/providers/auth-provider'
import { useTheme } from '@/providers/theme-provider'

interface Action {
  id: string
  label: string
  hint?: string
  icon: React.ComponentType<{ className?: string }>
  run: () => void | Promise<void>
  group: string
  visible?: boolean
}

/**
 * Paleta de comandos (Ctrl/⌘+K). Só expõe ações que realmente existem hoje —
 * novos módulos entram aqui conforme as fases forem entregues.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const { logout, hasPermission } = useAuth()
  const { setTheme } = useTheme()

  React.useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        onOpenChange(!open)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onOpenChange])

  const actions: Action[] = [
    {
      id: 'hoje',
      label: 'Ir para Hoje',
      hint: 'sua missão do dia',
      icon: LayoutDashboard,
      group: 'Navegação',
      run: () => navigate('/hoje'),
    },
    {
      id: 'conta',
      label: 'Minha conta',
      hint: 'perfil, senha e dispositivos',
      icon: User,
      group: 'Navegação',
      run: () => navigate('/conta'),
    },
    {
      id: 'admin',
      label: 'Painel administrativo',
      icon: Shield,
      group: 'Navegação',
      visible: hasPermission('admin_dashboard:read'),
      run: () => navigate('/admin'),
    },
    {
      id: 'tema-claro',
      label: 'Tema claro',
      icon: Sun,
      group: 'Preferências',
      run: () => setTheme('light'),
    },
    {
      id: 'tema-escuro',
      label: 'Tema escuro',
      icon: Moon,
      group: 'Preferências',
      run: () => setTheme('dark'),
    },
    {
      id: 'tema-sistema',
      label: 'Tema do sistema',
      icon: Monitor,
      group: 'Preferências',
      run: () => setTheme('system'),
    },
    {
      id: 'sair',
      label: 'Sair da conta',
      icon: LogOut,
      group: 'Conta',
      run: async () => {
        await logout()
        navigate('/entrar', { replace: true })
      },
    },
  ]

  const visible = actions.filter((action) => action.visible !== false)
  const groups = Array.from(new Set(visible.map((action) => action.group)))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="top-[15%] max-w-xl translate-y-0 p-0">
        <Command
          label="Paleta de comandos"
          className="overflow-hidden rounded-lg"
          loop
        >
          <Command.Input
            autoFocus
            placeholder="Buscar telas e ações…"
            className="h-12 w-full border-b border-border bg-transparent px-4 text-sm outline-none placeholder:text-subtle"
          />
          <Command.List className="max-h-80 overflow-y-auto p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-muted">
              Nada encontrado para esta busca.
            </Command.Empty>
            {groups.map((group) => (
              <Command.Group
                key={group}
                heading={group}
                className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-subtle [&_[cmdk-group-heading]]:uppercase"
              >
                {visible
                  .filter((action) => action.group === group)
                  .map((action) => (
                    <Command.Item
                      key={action.id}
                      value={`${action.label} ${action.hint ?? ''}`}
                      onSelect={async () => {
                        onOpenChange(false)
                        await action.run()
                      }}
                      className="flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 text-sm data-[selected=true]:bg-surface-muted"
                    >
                      <action.icon className="size-4 text-muted" />
                      <span>{action.label}</span>
                      {action.hint && (
                        <span className="ml-auto text-xs text-subtle">{action.hint}</span>
                      )}
                    </Command.Item>
                  ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </DialogContent>
    </Dialog>
  )
}
