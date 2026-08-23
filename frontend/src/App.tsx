import { RouterProvider } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { Toaster } from 'sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/providers/auth-provider'
import { ThemeProvider } from '@/providers/theme-provider'
import { queryClient } from '@/lib/query-client'
import { router } from '@/routes'

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider>
          <TooltipProvider delayDuration={200}>
            <RouterProvider router={router} />
            <Toaster
              position="top-right"
              closeButton
              toastOptions={{
                classNames: {
                  toast: 'card-surface text-sm',
                },
              }}
            />
          </TooltipProvider>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
