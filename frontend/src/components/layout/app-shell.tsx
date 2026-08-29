import * as React from 'react'
import { Outlet } from 'react-router-dom'
import { Sidebar } from './sidebar'
import { Topbar } from './topbar'
import { CommandPalette } from '@/components/command/command-palette'

const STORAGE_KEY = 'mestre.sidebar_collapsed'

export function AppShell() {
  const [collapsed, setCollapsed] = React.useState(
    () => localStorage.getItem(STORAGE_KEY) === 'true',
  )
  const [commandOpen, setCommandOpen] = React.useState(false)

  const toggleSidebar = React.useCallback(() => {
    setCollapsed((previous) => {
      localStorage.setItem(STORAGE_KEY, String(!previous))
      return !previous
    })
  }, [])

  return (
    <div className="game-shell dark relative flex min-h-dvh bg-background text-foreground">
      <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />
      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <Topbar onOpenCommand={() => setCommandOpen(true)} />
        <main className="mx-auto w-full max-w-[1780px] flex-1 px-4 pt-5 pb-28 lg:px-6 lg:py-7">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  )
}
