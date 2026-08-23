import { Monitor, Moon, Sun } from 'lucide-react'
import { useTheme } from '@/providers/theme-provider'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Alternar tema">
          {resolvedTheme === 'dark' ? <Moon /> : <Sun />}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onSelect={() => setTheme('light')} data-active={theme === 'light'}>
          <Sun /> Claro
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme('dark')} data-active={theme === 'dark'}>
          <Moon /> Escuro
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme('system')} data-active={theme === 'system'}>
          <Monitor /> Sistema
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
