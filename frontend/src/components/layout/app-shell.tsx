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
    <div className="flex min-h-dvh bg-background">
      <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenCommand={() => setCommandOpen(true)} />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  )
}
